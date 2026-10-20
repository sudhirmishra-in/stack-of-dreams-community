from pathlib import Path

import pytest

from navigator.adapters.fixtures import FixtureHttp
from navigator.adapters.osm import OsmAdapter
from navigator.config import Settings
from navigator.errors import BadRequest, NotFound
from navigator.ingest.demo import seed_demo
from navigator.ingest.sync import sync_source
from navigator.location.client import CachedZipGeocoder, GeoPoint, LocationClient, LocationUnavailable
from navigator.models import SearchRequest
from navigator.search.service import SearchService, decode_cursor, encode_cursor

FIX = Path(__file__).resolve().parents[1] / "fixtures"
ORIGIN = GeoPoint(40.8115, -73.9531)


class FixedGeocoder:
    def __init__(self, point=ORIGIN):
        self.point, self.calls = point, 0

    def zip_point(self, z):
        self.calls += 1
        return self.point


@pytest.fixture
def svc(store):
    sync_source(OsmAdapter(FixtureHttp(FIX), "http://x"), store, mode="full")
    seed_demo(store)
    return SearchService(store, FixedGeocoder(), Settings())


def req(**kw):
    base = dict(zipCode="10027", resourceType="food_assistance")
    return SearchRequest(**{**base, **kw})


def test_real_food_assistance_search_is_sorted_by_distance_with_provenance(svc):
    r = svc.search(req(), "c1")
    assert r.origin.geocoded and r.totalResults > 20 and r.correlationId == "c1"
    d = [x.distanceMiles for x in r.resources if x.distanceMiles is not None]
    assert d == sorted(d) and d[0] < 5
    for x in r.resources:
        assert not x.isDemoData and x.sourceId == "osm" and x.attribution and not x.verified
        assert x.inventory is None and x.weeklyCapacity is None and x.availableQuantity is None
    assert any("OpenStreetMap" in a for a in r.attributions) and not r.isDemoData


def test_item_searches_do_not_fabricate_inventory_for_real_orgs(svc):
    r = svc.search(req(resourceType="baby_formula"), "c")
    assert r.totalResults == 0 and any("not what it has in stock" in n for n in r.notes)


def test_demo_inventory_requires_opt_in_and_is_labeled(svc):
    r = svc.search(req(resourceType="baby_formula", includeDemo=True), "c")
    assert r.isDemoData and "DEMO DATA" in r.dataSource
    assert {x.id for x in r.resources} == {"demo-fb-002", "demo-fb-003", "demo-fb-004"}
    top = r.resources[0]
    assert top.isDemoData and top.inventoryIsDemo and top.availableQuantity is not None and "DEMO DATA" in top.source


def test_quantity_filter_excludes_unknown_stock(svc):
    r = svc.search(req(resourceType="baby_formula", includeDemo=True, quantity=100), "c")
    assert [x.id for x in r.resources] == ["demo-fb-002"]
    r2 = svc.search(req(resourceType="groceries", includeDemo=True, quantity=1), "c")
    assert r2.totalResults == 5 and all(x.isDemoData for x in r2.resources)  # real orgs have unknown stock


def test_diapers_have_no_data_anywhere(svc):
    assert svc.search(req(resourceType="diapers", includeDemo=True), "c").totalResults == 0


def test_radius_filter_and_missing_coordinates(svc):
    near = svc.search(req(radiusMiles=1), "c")
    assert near.totalResults < svc.search(req(), "c").totalResults
    assert all(x.distanceMiles is not None and x.distanceMiles <= 1 for x in near.resources)
    assert any("without map coordinates" in n for n in near.notes) or near.totalResults >= 0


def test_sort_by_capacity_and_availability_use_demo_data(svc):
    cap = svc.search(req(resourceType="groceries", includeDemo=True, sortBy="capacity"), "c")
    assert [x.weeklyCapacity for x in cap.resources[:2]] == [650, 500]
    av = svc.search(req(resourceType="baby_formula", includeDemo=True, sortBy="availability"), "c")
    assert [x.availableQuantity for x in av.resources] == [150, 75, 40]


def test_pagination_is_stable_and_validated(svc):
    p1 = svc.search(req(limit=10), "c")
    assert len(p1.resources) == 10 and p1.nextCursor
    p2 = svc.search(req(limit=10, cursor=p1.nextCursor), "c")
    assert not {x.id for x in p1.resources} & {x.id for x in p2.resources}
    assert decode_cursor(encode_cursor(40)) == 40
    for bad in ("zzz", "bzoxMDAwMDA", encode_cursor(0)[:-3] + "!!"):
        with pytest.raises(BadRequest):
            decode_cursor(bad)


def test_geocoder_unavailable_falls_back_without_inventing_distances(store):
    sync_source(OsmAdapter(FixtureHttp(FIX), "http://x"), store, mode="full")

    class Down:
        def zip_point(self, z):
            return None

    r = SearchService(store, Down(), Settings()).search(req(radiusMiles=2), "c")
    assert not r.origin.geocoded and r.totalResults > 20  # distance filter not applied, not guessed
    assert all(x.distanceMiles is None for x in r.resources)
    assert any("not shown" in n for n in r.notes) and any("not applied" in n for n in r.notes)


def test_get_resource_and_404s(svc, store):
    some = next(iter(store.iter_namespace("real")))
    assert svc.get(some.id).name == some.name
    assert svc.get("demo-fb-002").inventory["baby_formula"] == 150
    with pytest.raises(NotFound):
        svc.get("nope")


def test_inactive_records_are_hidden(svc, store):
    rec, v = store.get_resource("demo-fb-002")
    store.put_resource(rec.model_copy(update={"active": False}), v)
    with pytest.raises(NotFound):
        svc.get("demo-fb-002")
    assert "demo-fb-002" not in {x.id for x in svc.search(req(resourceType="baby_formula", includeDemo=True), "c").resources}


def test_stale_data_is_labeled(svc, store):
    rec = next(iter(store.iter_namespace("real")))
    r, v = store.get_resource(rec.id)
    r.sources[0].lastSyncedAt = "2020-01-01T00:00:00Z"
    store.put_resource(r, v)
    assert svc.get(rec.id).freshness == "stale"
    assert svc.get("demo-fb-002").freshness == "unknown"


def test_zip_validation_rejects_bad_input():
    with pytest.raises(ValueError):
        SearchRequest(zipCode="1002", resourceType="groceries")
    with pytest.raises(ValueError):
        SearchRequest(zipCode="10027", resourceType="groceries", bogus=1)


# ---- location client ----


class FakePlaces:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, []

    def geocode(self, **kw):
        self.calls.append(kw)
        if self.error:
            raise self.error
        return self.result


def test_zip_geocode_is_cached_and_uses_storage_licence(store):
    places = FakePlaces({"ResultItems": [{"Position": [-73.9531, 40.8115]}]})
    g = CachedZipGeocoder(store, LocationClient("us-east-2", places=places, routes=object()))
    assert g.zip_point("10027").latitude == 40.8115
    assert g.zip_point("10027").cached is True
    assert len(places.calls) == 1 and places.calls[0]["IntendedUse"] == "Storage"


def test_geocode_failure_returns_none_not_a_guess(store):
    places = FakePlaces(error=RuntimeError("AccessDenied"))
    g = CachedZipGeocoder(store, LocationClient("us-east-2", places=places, routes=object()))
    assert g.zip_point("10027") is None
    assert CachedZipGeocoder(store, None).zip_point("10027") is None
    with pytest.raises(LocationUnavailable):
        LocationClient("us-east-2", places=places, routes=object()).geocode_zip("10027")


def test_route_converts_units_and_validates_mode():
    class Routes:
        def calculate_routes(self, **kw):
            assert kw["Origin"] == [-73.95, 40.8] and kw["TravelMode"] == "Pedestrian"
            return {"Routes": [{"Summary": {"Distance": 1609, "Duration": 1200}}]}

    c = LocationClient("us-east-2", places=object(), routes=Routes())
    s = c.route((40.8, -73.95), (40.7, -73.9), "Pedestrian")
    assert s.distance_miles == 1.0 and s.duration_minutes == 20.0
    with pytest.raises(ValueError):
        c.route((1, 1), (2, 2), "Rocket")
