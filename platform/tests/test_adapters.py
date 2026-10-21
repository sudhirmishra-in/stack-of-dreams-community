import json
import urllib.error
from io import BytesIO
from pathlib import Path

import pytest

from navigator.adapters.base import AdapterNotConfigured
from navigator.adapters.csv_partner import CsvPartnerAdapter
from navigator.adapters.fixtures import FixtureHttp
from navigator.adapters.http import HttpClient, HttpError
from navigator.adapters.nyc_cfc import NycCfcAdapter, map_row
from navigator.adapters.osm import ATTRIBUTION, OsmAdapter, build_query, map_element
from navigator.adapters.twoone_one import TwoOneOneAdapter

FIX = Path(__file__).resolve().parents[1] / "fixtures"
OSM = json.loads((FIX / "overpass_nyc.json").read_text())


def test_osm_maps_real_fixture_with_attribution_and_no_verification():
    cands = [c for el in OSM["elements"] if (c := map_element(el, "2026-10-19T00:00:00Z"))]
    assert 20 < len(cands) <= len(OSM["elements"])  # unnamed points are dropped, not guessed
    for c in cands:
        assert c.name and c.ref.attribution == ATTRIBUTION and c.ref.license == "ODbL 1.0"
        assert c.ref.lastVerifiedAt is None
        assert c.ref.sourceUrl.startswith("https://www.openstreetmap.org/")
        assert c.zip_code is None or (len(c.zip_code) == 5 and c.zip_code.isdigit())
    assert any(c.zip_code == "10026" and c.address == "252 West 116th Street" for c in cands)


def test_osm_rejects_unnamed_and_bad_coordinates_and_unsafe_urls():
    assert map_element({"type": "node", "id": 1, "lat": 40.7, "lon": -73.9, "tags": {"amenity": "food_bank"}}, "t") is None
    c = map_element({"type": "node", "id": 2, "lat": 0, "lon": 0, "tags": {"name": "X", "website": "javascript:alert(1)", "addr:postcode": "10027-1234"}}, "t")
    assert c.latitude is None and c.website is None and c.zip_code == "10027"


def test_osm_incremental_query_uses_newer_filter():
    assert "newer:" not in build_query()
    assert '(newer:"2026-10-01T00:00:00Z")' in build_query(newer_than="2026-10-01T00:00:00Z")


def test_osm_full_vs_incremental_completeness():
    adapter = OsmAdapter(FixtureHttp(FIX), "http://x")
    full = list(adapter.fetch(None, True))
    assert full[0].complete is True
    inc = list(adapter.fetch("2026-10-01T00:00:00Z", False))
    assert inc[0].complete is False  # an incremental run can never prove absence


def test_osm_rejects_unexpected_shape():
    class Bad:
        def post_form_json(self, *a, **k):
            return {"nope": 1}

    with pytest.raises(ValueError):
        list(OsmAdapter(Bad(), "http://x").fetch(None, True))


def test_cfc_na_is_missing_not_zero_and_meaning_is_preserved():
    rows = json.loads((FIX / "nyc_cfc.json").read_text())
    mapped = [m for r in rows if (m := map_row(r))]
    assert len(mapped) == len(rows) - 8  # the 8 "N/A" rows are dropped, never stored as 0
    assert all(m.value > 0 for m in mapped)
    pantry = next(m for m in mapped if m.program == "food_pantry")
    assert pantry.metric == "individuals_served" and "duplicated" in pantry.meaning and pantry.scope == "citywide"
    soup = next(m for m in mapped if m.program == "soup_kitchen")
    assert soup.metric == "meals_served"
    assert pantry.periodStart < pantry.periodEnd


def test_cfc_paginates_and_checkpoints():
    pages = list(NycCfcAdapter(FixtureHttp(FIX)).fetch(None, True))
    assert pages[-1].complete
    assert sum(len(p.activities) for p in pages) == 110
    inc = list(NycCfcAdapter(FixtureHttp(FIX)).fetch("2026-01-01", False))
    assert all(a.periodEnd > "2026-01-01" for p in inc for a in p.activities)


def test_cfc_multi_page_requests():
    calls = []

    class Http:
        def get_json(self, url, params):
            calls.append(params["$offset"])
            return [{"facility": "Food Pantries (Individuals Served)", "report_start_date": "2020-01-01T00:00:00.000", "report_end_date": "2020-03-31T00:00:00.000", "number": "5"}] * (500 if params["$offset"] == 0 else 3)

    pages = list(NycCfcAdapter(Http()).fetch(None, True))
    assert calls == [0, 500] and pages[0].complete is False and pages[1].complete is True


def test_211_is_disabled_by_default_and_never_calls_out():
    with pytest.raises(AdapterNotConfigured, match="disabled"):
        list(TwoOneOneAdapter().fetch(None, True))
    with pytest.raises(AdapterNotConfigured, match="API_KEY_PARAM"):
        list(TwoOneOneAdapter(enabled=True).fetch(None, True))


def test_partner_csv_adapter_maps_rows_and_rejects_bad_ones():
    text = "id,name,zip,lat,lon,types,phone\np1,Helpful Pantry,10027,40.81,-73.95,baby_formula;bogus,\n,No Id,10027,,,\n"
    page = next(CsvPartnerAdapter("partner-x", lambda: text).fetch(None, True))
    assert len(page.resources) == 1 and page.rejected == 1
    assert page.resources[0].resource_types == ["baby_formula"] and page.complete


# ---- HTTP client ----


class Resp:
    def __init__(self, body: bytes):
        self.b = BytesIO(body)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n=-1):
        return self.b.read(n)


def http_error(code, headers=None):
    return urllib.error.HTTPError("http://x", code, "err", headers or {}, BytesIO(b""))


def test_http_retries_with_backoff_then_succeeds():
    seq = [http_error(503), http_error(429, {"Retry-After": "7"}), Resp(b'{"ok": true}')]
    sleeps = []

    def opener(req, timeout):
        r = seq.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    client = HttpClient("ua", sleep=sleeps.append, opener=opener)
    assert client.get_json("http://x") == {"ok": True}
    assert len(sleeps) == 2 and sleeps[1] == 7.0  # honors Retry-After


def test_http_treats_overpass_overload_page_as_retryable_and_gives_up():
    client = HttpClient("ua", max_attempts=3, sleep=lambda s: None, opener=lambda r, timeout: Resp(b"# 502 Gateway Timeout"))
    with pytest.raises(HttpError):
        client.post_form_json("http://x", {"data": "q"})


def test_http_does_not_retry_client_errors():
    calls = []

    def opener(req, timeout):
        calls.append(1)
        raise http_error(404)

    with pytest.raises(HttpError) as e:
        HttpClient("ua", sleep=lambda s: None, opener=opener).get_json("http://x")
    assert e.value.status == 404 and len(calls) == 1


def test_http_per_request_timeout_and_attempts_override_defaults():
    seen = []

    def opener(req, timeout):
        seen.append(timeout)
        raise TimeoutError("The read operation timed out")

    client = HttpClient("ua", timeout=30, max_attempts=4, sleep=lambda s: None, opener=opener)
    with pytest.raises(HttpError):
        client.post_form_json("http://x", {"data": "q"}, timeout=75, max_attempts=2)
    assert seen == [75, 75]


def test_osm_waits_longer_than_the_overpass_query_and_fits_the_lambda_budget():
    from navigator.adapters import osm

    seen = {}

    class Spy:
        def post_form_json(self, url, form, **kw):
            seen.update(kw, query=form["data"])
            return {"elements": []}

    list(OsmAdapter(Spy(), "http://x").fetch(None, True))
    assert f"[timeout:{osm.QUERY_TIMEOUT_S}]" in seen["query"]
    # A healthy Overpass query may run for its full server-side timeout; the client must outwait it.
    assert seen["timeout"] > osm.QUERY_TIMEOUT_S
    # Worst case (every attempt times out, plus backoff) must stay under the 300 s ingest Lambda timeout.
    assert seen["max_attempts"] * seen["timeout"] + 30 < 300
