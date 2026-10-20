"""Cost guards: every paid or metered path has a bound that does not depend on user behavior."""

import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from navigator.adapters.fixtures import FixtureHttp
from navigator.adapters.osm import OsmAdapter
from navigator.api.app import App, Deps
from navigator.config import QuotaLimits, Settings
from navigator.gateway.auth import JwtVerifier
from navigator.gateway.invoker import MockInvoker
from navigator.gateway.pipeline import AssistantPipeline
from navigator.ingest.sync import sync_source
from navigator.location.client import CachedZipGeocoder, LocationClient, in_pilot_area
from navigator.location.maps import MapsClient
from navigator.quota.ledger import UsageLedger
from navigator.search.service import SearchService
from navigator.store.data_store import DataStore
from pathlib import Path

FIX = Path(__file__).resolve().parents[1] / "fixtures"
POOL, CLIENT = "us-east-2_AbCdEfGhI", "client-123"
ISS = f"https://cognito-idp.us-east-2.amazonaws.com/{POOL}"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def tok(sub="user-sub-0001"):
    return jwt.encode({"sub": sub, "iss": ISS, "client_id": CLIENT, "token_use": "access", "exp": int(time.time()) + 600}, KEY, algorithm="RS256")


class CountingPlaces:
    def __init__(self):
        self.calls = []

    def geocode(self, **kw):
        self.calls.append(kw["QueryComponents"]["PostalCode"])
        return {"ResultItems": [{"Position": [-73.95, 40.81]}]}


class Blob:
    def read(self):
        return b"x"


class CountingMaps:
    def __init__(self):
        self.calls = 0

    def get_tile(self, **kw):
        self.calls += 1
        return {"Blob": Blob(), "ContentType": "application/x-protobuf"}


class Routes:
    def calculate_routes(self, **kw):
        return {"Routes": [{"Summary": {"Distance": 1609, "Duration": 600}}]}


@pytest.fixture
def world(aws):
    s = Settings(data_table="data-t", usage_table="usage-t", cognito_user_pool_id=POOL, cognito_client_id=CLIENT, mock_mode=True)
    store, ledger = DataStore("data-t", resource=aws), UsageLedger("usage-t", resource=aws)
    sync_source(OsmAdapter(FixtureHttp(FIX), "http://x"), store, mode="full")
    places, maps = CountingPlaces(), CountingMaps()
    loc = LocationClient("us-east-2", places=places, routes=Routes())
    search = SearchService(store, CachedZipGeocoder(store, loc), s)
    app = App(Deps(s, JwtVerifier(POOL, CLIENT, key_resolver=lambda t: KEY.public_key()), store, ledger, search,
                   AssistantPipeline(ledger, MockInvoker(), None, s), loc, MapsClient("us-east-2", client=maps)))
    return app, ledger, places, maps


def call(app, method, path, body=None, token=None, query=None):
    ev = {"rawPath": path, "requestContext": {"http": {"method": method}, "domainName": "abc123.lambda-url.us-east-2.on.aws"},
          "headers": {"authorization": f"Bearer {token or tok()}"}, "queryStringParameters": query or {}, "body": json.dumps(body) if body is not None else None}
    r = app.handle(ev)
    return r["statusCode"], json.loads(r["body"]) if r["headers"]["Content-Type"] == "application/json" else r


def search(app, zip_code, token=None):
    return call(app, "POST", "/api/v1/resources/search", {"zipCode": zip_code, "resourceType": "food_assistance", "limit": 3}, token)


def test_pilot_area_is_new_york_city_and_overridable(monkeypatch):
    assert all(in_pilot_area(z) for z in ("10027", "11201", "10301", "10451", "11375", "11691"))
    assert not any(in_pilot_area(z) for z in ("90210", "60601", "02134", "33101", "94105"))
    monkeypatch.setenv("GEOCODE_ZIP_PREFIXES", "")
    assert in_pilot_area("90210")  # explicit expansion: empty = no restriction
    monkeypatch.setenv("GEOCODE_ZIP_PREFIXES", "021, 022")
    assert in_pilot_area("02134") and not in_pilot_area("10027")


def test_zips_outside_the_pilot_area_never_trigger_a_paid_lookup(world):
    app, _, places, _ = world
    s, b = search(app, "90210")
    assert s == 200 and b["origin"]["geocoded"] is False and places.calls == []
    assert any("New York City pilot area" in n for n in b["notes"])


def test_each_nyc_zip_is_looked_up_once_then_served_from_the_cache(world):
    app, _, places, _ = world
    for _ in range(5):
        assert search(app, "10027")[1]["origin"]["geocoded"] is True
    assert places.calls == ["10027"]  # one paid call, four cache hits


def test_per_user_geocode_budget_stops_paid_lookups_but_not_search(world):
    app, ledger, places, _ = world
    ledger.set_user_profile("user-sub-0001", disabled=None, overrides={"geocodes_per_user_day": 2}, actor="a")
    zips = ["10001", "10002", "10003", "10004"]
    results = [search(app, z) for z in zips]
    assert [r[0] for r in results] == [200] * 4  # search keeps working
    assert [r[1]["origin"]["geocoded"] for r in results] == [True, True, False, False]
    assert places.calls == ["10001", "10002"]
    assert any("Distances are not shown" in n for n in results[3][1]["notes"])


def test_app_wide_geocode_budget_applies_across_users(world):
    app, ledger, places, _ = world
    ledger.set_quota_overrides({"geocodes_per_app_day": 3}, "a")
    for i, z in enumerate(["10001", "10002", "10003", "10004", "10005"]):
        search(app, z, tok(f"user-sub-000{i}"))
    assert len(places.calls) == 3


def test_app_wide_map_cap_protects_the_whole_pilot(world):
    app, ledger, _, maps = world
    ledger.set_quota_overrides({"map_requests_per_app_day": 3}, "a")
    path = "/api/v1/maps/tiles/vector.basemap/10/301/385"
    codes = [call(app, "GET", path, token=tok(f"user-sub-000{i}"))[0] for i in range(5)]
    assert codes == [200, 200, 200, 429, 429] and maps.calls == 3  # nothing reached AWS past the cap


def test_app_wide_route_cap(world):
    app, ledger, _, _ = world
    ledger.set_quota_overrides({"routes_per_app_day": 1}, "a")
    rid = search(app, "10027")[1]["resources"][0]["id"]
    q = {"fromZip": "10027", "toResourceId": rid, "mode": "Car"}
    assert call(app, "GET", "/api/v1/route", token=tok("user-sub-0001"), query=q)[0] == 200
    assert call(app, "GET", "/api/v1/route", token=tok("user-sub-0002"), query=q)[0] == 429


def test_try_count_event_degrades_instead_of_raising(aws):
    led = UsageLedger("usage-t", resource=aws)
    assert led.try_count_event("u1", "geocode", 1) is True
    assert led.try_count_event("u1", "geocode", 1) is False
    assert UsageLedger("missing", resource=aws).try_count_event("u1", "geocode", 5) is False  # fails closed


def test_documented_defaults_bound_the_worst_case():
    q = QuotaLimits()
    assert q.geocodes_per_app_day <= 200 and q.map_requests_per_app_day <= 30_000 and q.routes_per_app_day <= 500
    assert q.requests_per_app_day <= 300 and q.max_tokens_per_request <= 12_000
