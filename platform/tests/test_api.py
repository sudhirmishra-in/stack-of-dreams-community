import json
import time
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from navigator.adapters.fixtures import FixtureHttp
from navigator.adapters.osm import OsmAdapter
from navigator.api.app import App, Deps
from navigator.config import Settings
from navigator.gateway.auth import JwtVerifier
from navigator.gateway.invoker import MockInvoker
from navigator.gateway.pipeline import AssistantPipeline
from navigator.ingest.demo import seed_demo
from navigator.ingest.sync import sync_source
from navigator.location.client import GeoPoint, LocationClient
from navigator.quota.ledger import UsageLedger
from navigator.search.service import SearchService
from navigator.store.data_store import DataStore

FIX = Path(__file__).resolve().parents[1] / "fixtures"
POOL, CLIENT = "us-east-2_AbCdEfGhI", "client-123"
ISS = f"https://cognito-idp.us-east-2.amazonaws.com/{POOL}"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def tok(sub="user-sub-0001", groups=None, **over):
    c = {"sub": sub, "iss": ISS, "client_id": CLIENT, "token_use": "access", "exp": int(time.time()) + 600}
    if groups:
        c["cognito:groups"] = groups
    c.update(over)
    return jwt.encode(c, KEY, algorithm="RS256")


class Geo:
    def zip_point(self, z, allow_remote=None):
        return GeoPoint(40.8115, -73.9531)


class FakeRoutes:
    def calculate_routes(self, **kw):
        return {"Routes": [{"Summary": {"Distance": 3218, "Duration": 600}}]}


@pytest.fixture
def app(aws):
    settings = Settings(data_table="data-t", usage_table="usage-t", cognito_user_pool_id=POOL, cognito_client_id=CLIENT, mock_mode=True, assistant_enabled=True)
    store, ledger = DataStore("data-t", resource=aws), UsageLedger("usage-t", resource=aws)
    sync_source(OsmAdapter(FixtureHttp(FIX), "http://x"), store, mode="full")
    seed_demo(store)
    loc = LocationClient("us-east-2", places=object(), routes=FakeRoutes())
    deps = Deps(settings, JwtVerifier(POOL, CLIENT, key_resolver=lambda t: KEY.public_key()), store, ledger,
                SearchService(store, Geo(), settings), AssistantPipeline(ledger, MockInvoker(), None, settings), loc)
    return App(deps)


def call(app, method, path, body=None, token=None, query=None, headers=None):
    h = {"authorization": f"Bearer {token}"} if token else {}
    h.update(headers or {})
    ev = {"rawPath": path, "requestContext": {"http": {"method": method}}, "headers": h, "queryStringParameters": query or {}, "body": json.dumps(body) if body is not None else None}
    r = app.handle(ev)
    return r["statusCode"], json.loads(r["body"]), r["headers"]


def test_health_is_public_and_leaks_nothing_sensitive(app):
    s, b, h = call(app, "GET", "/api/v1/health")
    assert s == 200 and b["status"] == "ok" and set(b) == {"status", "version", "mockMode", "correlationId"} and h["Cache-Control"] == "no-store"


def test_correlation_id_is_echoed_when_valid_and_generated_otherwise(app):
    assert call(app, "GET", "/api/v1/health", headers={"x-correlation-id": "abc-12345678"})[2]["X-Correlation-Id"] == "abc-12345678"
    assert len(call(app, "GET", "/api/v1/health", headers={"x-correlation-id": "bad id!"})[2]["X-Correlation-Id"]) == 32


@pytest.mark.parametrize("method,path", [("POST", "/api/v1/resources/search"), ("GET", "/api/v1/resources/osm-node-1"), ("POST", "/api/v1/assistant"), ("GET", "/api/v1/me/usage"), ("GET", "/api/v1/route"), ("GET", "/api/v1/sync-status")])
def test_protected_endpoints_return_401_without_a_token(app, method, path):
    s, b, h = call(app, method, path, body={} if method == "POST" else None)
    assert s == 401 and b["error"]["code"] == "unauthorized" and b["error"]["correlationId"] == h["X-Correlation-Id"]


def test_admin_endpoints_return_403_for_normal_users_and_401_for_anonymous(app):
    assert call(app, "PUT", "/api/v1/admin/quotas", {"overrides": {"requests_per_user_day": 1}}, tok())[0] == 403
    assert call(app, "PUT", "/api/v1/admin/switch", {"assistantEnabled": False}, tok())[0] == 403
    assert call(app, "GET", "/api/v1/admin/usage", token=tok())[0] == 403
    assert call(app, "GET", "/api/v1/admin/usage")[0] == 401


def test_search_returns_structured_results_without_an_llm(app):
    s, b, _ = call(app, "POST", "/api/v1/resources/search", {"zipCode": "10027", "resourceType": "food_assistance", "limit": 5}, tok())
    assert s == 200 and len(b["resources"]) == 5 and b["origin"]["geocoded"] and b["totalResults"] > 20 and b["nextCursor"]
    assert b["resources"][0]["sourceId"] == "osm" and not b["resources"][0]["isDemoData"]
    s, b, _ = call(app, "POST", "/api/v1/resources/search", {"zipCode": "10027", "resourceType": "baby_formula", "includeDemo": True}, tok())
    assert b["isDemoData"] and b["resources"][0]["inventoryIsDemo"]


def test_search_validation_errors_name_fields_but_never_echo_values(app):
    s, b, _ = call(app, "POST", "/api/v1/resources/search", {"zipCode": "SECRET99", "resourceType": "nope", "extra": 1}, tok())
    assert s == 400 and b["error"]["code"] == "bad_request"
    assert "SECRET99" not in json.dumps(b) and {f["field"] for f in b["error"]["details"]["fields"]} >= {"zipCode", "resourceType", "extra"}


def test_malformed_and_oversized_bodies(app):
    ev = {"rawPath": "/api/v1/assistant", "requestContext": {"http": {"method": "POST"}}, "headers": {"authorization": f"Bearer {tok()}"}, "body": "{not json"}
    assert app.handle(ev)["statusCode"] == 400
    ev["body"] = "x" * 20000
    assert app.handle(ev)["statusCode"] == 413


def test_unknown_routes_and_methods(app):
    assert call(app, "GET", "/api/v1/nope", token=tok())[0] == 404
    assert call(app, "DELETE", "/api/v1/me/usage", token=tok())[0] == 405
    assert call(app, "GET", "/api/v1/me/usage/", token=tok())[0] == 200  # trailing slash tolerated


def test_get_resource_and_404(app):
    assert call(app, "GET", "/api/v1/resources/demo-fb-002", token=tok())[1]["resource"]["inventory"]["baby_formula"] == 150
    assert call(app, "GET", "/api/v1/resources/nope", token=tok())[0] == 404
    assert call(app, "GET", "/api/v1/resources/bad%20id", token=tok())[0] == 400


def test_assistant_in_mock_mode_never_claims_an_agent_ran_and_usage_is_visible(app):
    s, b, _ = call(app, "POST", "/api/v1/assistant", {"message": "Which food banks are near 10027?", "sessionId": "session-abcdef-1"}, tok())
    assert s == 200 and "no AgentCore runtime was invoked" in b["response"] and b["agentId"] == "community-navigator"
    s, u, _ = call(app, "GET", "/api/v1/me/usage", token=tok())
    assert u["daily"]["used"] == 1 and u["daily"]["remaining"] == 19 and u["monthly"]["limit"] == 200


def test_assistant_refuses_off_topic_with_422_and_quota_with_429(app):
    s, b, _ = call(app, "POST", "/api/v1/assistant", {"message": "write me a poem", "sessionId": "session-abcdef-1"}, tok())
    assert s == 422 and b["error"]["code"] == "out_of_scope"
    call(app, "PUT", "/api/v1/admin/users/user-sub-0001", {"overrides": {"requests_per_user_day": 1}}, tok("admin-sub-0001", ["pilot-admin"]))
    ok = {"message": "find food banks near 10027", "sessionId": "session-abcdef-1"}
    assert call(app, "POST", "/api/v1/assistant", ok, tok())[0] == 200
    s, b, h = call(app, "POST", "/api/v1/assistant", ok, tok())
    assert s == 429 and b["error"]["details"]["reason"] == "daily_requests" and int(h["Retry-After"]) > 0


def test_identity_comes_only_from_the_token_not_the_body(app):
    body = {"message": "food banks near 10027", "sessionId": "session-abcdef-1", "userId": "someone-else", "sub": "someone-else"}
    s, b, _ = call(app, "POST", "/api/v1/assistant", body, tok())
    assert s == 400  # unknown fields are refused, so a spoofed identity cannot even be submitted
    assert call(app, "GET", "/api/v1/me/usage", token=tok("alice-sub-0001"), query={"sub": "bob-sub-00001"})[1]["daily"]["used"] == 0


def test_admin_can_change_quotas_disable_users_and_pause_the_assistant(app):
    admin = tok("admin-sub-0001", ["pilot-admin"])
    assert call(app, "PUT", "/api/v1/admin/quotas", {"overrides": {"requests_per_user_day": 3, "bogus": 1}}, admin)[1]["overrides"] == {"requests_per_user_day": 3}
    assert call(app, "GET", "/api/v1/me/usage", token=tok())[1]["daily"]["limit"] == 3
    assert call(app, "PUT", "/api/v1/admin/users/user-sub-0001", {"disabled": True}, admin)[0] == 200
    s, b, _ = call(app, "POST", "/api/v1/assistant", {"message": "food banks", "sessionId": "session-abcdef-1"}, tok())
    assert s == 403
    assert call(app, "POST", "/api/v1/resources/search", {"zipCode": "10027", "resourceType": "food_assistance"}, tok())[0] == 403
    call(app, "PUT", "/api/v1/admin/users/user-sub-0001", {"disabled": False}, admin)
    call(app, "PUT", "/api/v1/admin/switch", {"assistantEnabled": False}, admin)
    assert call(app, "POST", "/api/v1/assistant", {"message": "food banks", "sessionId": "session-abcdef-1"}, tok())[0] == 503
    assert call(app, "PUT", "/api/v1/admin/switch", {"assistantEnabled": "yes"}, admin)[0] == 400
    assert call(app, "PUT", "/api/v1/admin/users/x", {"disabled": True}, admin)[0] == 400


def test_admin_usage_and_sync_status(app):
    admin = tok("admin-sub-0001", ["pilot-admin"])
    call(app, "POST", "/api/v1/assistant", {"message": "food banks near 10027", "sessionId": "session-abcdef-1"}, tok())
    s, b, _ = call(app, "GET", "/api/v1/admin/usage", token=admin)
    assert s == 200 and b["requests"] == 1 and "pricingVersion" in b
    assert call(app, "GET", "/api/v1/admin/usage", token=admin, query={"day": "yesterday"})[0] == 400
    assert call(app, "GET", "/api/v1/admin/sync-status", token=admin)[1]["sources"][0]["sourceId"] == "osm"
    pub = call(app, "GET", "/api/v1/sync-status", token=tok())[1]["sources"][0]
    assert set(pub) == {"sourceId", "status", "lastSuccessAt", "lastFullSyncAt"}  # no error text / counts for normal users


def test_route_endpoint_returns_real_service_values_or_an_honest_error(app):
    rid = call(app, "POST", "/api/v1/resources/search", {"zipCode": "10027", "resourceType": "food_assistance", "limit": 1}, tok())[1]["resources"][0]["id"]
    s, b, _ = call(app, "GET", "/api/v1/route", token=tok(), query={"fromZip": "10027", "toResourceId": rid, "mode": "Pedestrian"})
    assert s == 200 and b["distanceMiles"] == 2.0 and b["durationMinutes"] == 10.0 and b["provider"] == "Amazon Location Service"
    assert call(app, "GET", "/api/v1/route", token=tok(), query={"fromZip": "1", "toResourceId": rid})[0] == 400
    app.d.location = None
    assert call(app, "GET", "/api/v1/route", token=tok(), query={"fromZip": "10027", "toResourceId": rid})[0] == 503


def test_unexpected_exceptions_return_a_generic_500(app, monkeypatch):
    monkeypatch.setattr(app.d.search, "search", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("secret internal detail")))
    s, b, _ = call(app, "POST", "/api/v1/resources/search", {"zipCode": "10027", "resourceType": "food_assistance"}, tok())
    assert s == 500 and "secret" not in json.dumps(b) and b["error"]["code"] == "internal_error"
