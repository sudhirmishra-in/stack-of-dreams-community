import time
from pathlib import Path

import pytest

from navigator.adapters.base import Page, ResourceCandidate
from navigator.adapters.csv_partner import CsvPartnerAdapter
from navigator.adapters.fixtures import FixtureHttp
from navigator.adapters.nyc_cfc import NycCfcAdapter
from navigator.adapters.osm import OsmAdapter
from navigator.ingest.demo import seed_demo
from navigator.ingest.normalize import RejectedRecord, normalize
from navigator.ingest.sync import sync_all, sync_source
from navigator.models import SourceRef
from navigator.store.data_store import VersionConflict

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def osm():
    return OsmAdapter(FixtureHttp(FIX), "http://x")


def real(store):
    return list(store.iter_namespace("real", include_inactive=True))


class Scripted:
    """An adapter that yields scripted pages (or raises) so failure modes can be tested precisely."""

    supports_deactivation = True

    def __init__(self, source_id, pages, raise_after=None):
        self.source_id, self.pages, self.raise_after = source_id, pages, raise_after

    def fetch(self, checkpoint, full):
        for i, p in enumerate(self.pages):
            if self.raise_after is not None and i == self.raise_after:
                raise RuntimeError("boom")
            yield p


def cand(i, name=None, zip_code="10027", sid="osm"):
    return ResourceCandidate(sid, f"node/{i}", name or f"Pantry {i}", zip_code=zip_code, ref=SourceRef(sourceId=sid, sourceRecordId=f"node/{i}"))


def test_first_sync_creates_unverified_real_records(store):
    r = sync_source(osm(), store, mode="full")
    assert r.status == "success" and r.counts.created > 20 and r.counts.errors == 0
    recs = real(store)
    assert len(recs) == r.counts.created
    assert all(not x.isDemoData and x.verification == "unverified" and x.weeklyCapacity is None for x in recs)
    assert store.get_sync_state("osm")["status"] == "success"


def test_sync_is_idempotent(store):
    first = sync_source(osm(), store, mode="full")
    n = len(real(store))
    second = sync_source(osm(), store, mode="full")
    assert second.counts.created == 0 and second.counts.updated == first.counts.created
    assert len(real(store)) == n


def test_activity_sync_preserves_reporting_period_and_is_idempotent(store):
    adapter = NycCfcAdapter(FixtureHttp(FIX))
    r = sync_source(adapter, store, mode="full")
    assert r.counts.activity_written == 110 and r.counts.rejected == 8
    again = sync_source(adapter, store, mode="full")
    acts = store.list_activity("nyc-cfc", "food_pantry", limit=100)
    assert len(acts) == 55 and again.counts.activity_written == 110
    assert acts[0].periodEnd > acts[-1].periodEnd  # newest first
    assert store.get_sync_state("nyc-cfc")["checkpoint"] == acts[0].periodEnd


def test_partial_failure_keeps_last_success_and_never_deactivates(store):
    sync_source(osm(), store, mode="full")
    before = {x.id for x in real(store) if x.active}
    prev = store.get_sync_state("osm")
    failing = Scripted("osm", [Page(resources=[cand(1)], complete=False), Page(resources=[cand(2)], complete=True)], raise_after=1)
    r = sync_source(failing, store, mode="full")
    assert r.status == "failed"
    after = store.get_sync_state("osm")
    assert after["status"] == "failed" and after["lastSuccessAt"] == prev["lastSuccessAt"]
    assert after["checkpoint"] == prev["checkpoint"] and after["lastFullSyncAt"] == prev["lastFullSyncAt"]
    assert {x.id for x in real(store) if x.active} >= before  # nothing deactivated


def test_incomplete_sync_never_deactivates(store):
    pages = [Page(resources=[cand(i) for i in range(12)], complete=True)]
    sync_source(Scripted("osm", pages), store, mode="full")
    incomplete = Scripted("osm", [Page(resources=[cand(0)], complete=False)])
    r = sync_source(incomplete, store, mode="full")
    assert r.counts.deactivated == 0 and all(x.active for x in real(store))


def test_complete_full_sync_deactivates_missing_records_softly(store):
    sync_source(Scripted("osm", [Page(resources=[cand(i) for i in range(12)], complete=True)]), store, mode="full")
    r = sync_source(Scripted("osm", [Page(resources=[cand(i) for i in range(11)], complete=True)]), store, mode="full")
    assert r.counts.deactivated == 1
    recs = {x.id: x for x in real(store)}
    assert len(recs) == 12 and recs["osm-node-11"].active is False  # kept, just inactive


def test_suspiciously_empty_full_sync_does_not_wipe_the_directory(store):
    sync_source(Scripted("osm", [Page(resources=[cand(i) for i in range(12)], complete=True)]), store, mode="full")
    r = sync_source(Scripted("osm", [Page(resources=[cand(0)], complete=True)]), store, mode="full")
    assert r.status == "partial" and r.counts.deactivated == 0
    assert sum(x.active for x in real(store)) == 12


def test_reappearing_record_is_reactivated(store):
    sync_source(Scripted("osm", [Page(resources=[cand(i) for i in range(12)], complete=True)]), store, mode="full")
    sync_source(Scripted("osm", [Page(resources=[cand(i) for i in range(11)], complete=True)]), store, mode="full")
    sync_source(Scripted("osm", [Page(resources=[cand(i) for i in range(12)], complete=True)]), store, mode="full")
    assert all(x.active for x in real(store))


def test_source_isolation_one_failure_does_not_block_others(store):
    bad = Scripted("bad", [], raise_after=0)
    bad.fetch = lambda c, f: (_ for _ in ()).throw(RuntimeError("down"))
    results = sync_all({"bad": bad, "osm": osm()}, store, mode="full")
    status = {r.source_id: r.status for r in results}
    assert status == {"bad": "failed", "osm": "success"}
    assert store.get_sync_state("bad")["status"] == "failed"


def test_disabled_source_is_reported_not_failed(store):
    from navigator.adapters.twoone_one import TwoOneOneAdapter

    r = sync_source(TwoOneOneAdapter(), store, mode="full")
    assert r.status == "disabled" and store.get_sync_state("211")["status"] == "disabled"


def test_overlapping_runs_are_prevented(store):
    assert store.acquire_sync_lock("osm", int(time.time()), 600)
    r = sync_source(osm(), store, mode="full")
    assert r.status == "skipped"
    store.release_sync_lock("osm")
    assert sync_source(osm(), store, mode="full").status == "success"


def test_expired_lock_is_taken_over(store):
    assert store.acquire_sync_lock("osm", int(time.time()) - 1000, 10)
    assert store.acquire_sync_lock("osm", int(time.time()), 600)


def test_missing_data_is_rejected_not_invented(store):
    nothing_to_locate = ResourceCandidate("osm", "node/1", "No Place", ref=SourceRef(sourceId="osm", sourceRecordId="node/1"))
    with pytest.raises(RejectedRecord):
        normalize(nothing_to_locate)
    with pytest.raises(RejectedRecord):
        normalize(ResourceCandidate("osm", "node/2", None, zip_code="10027"))
    r = sync_source(Scripted("osm", [Page(resources=[nothing_to_locate, cand(3)], complete=True)]), store, mode="full")
    assert r.counts.rejected == 1 and r.counts.created == 1


def test_bad_phone_numbers_are_dropped():
    c = cand(5)
    c.phone = "call us!!!"
    assert normalize(c).phone is None
    c.phone = "(212) 555-0100"
    assert normalize(c).phone == "(212) 555-0100"


def test_cross_source_duplicate_is_merged_not_duplicated(store):
    sync_source(Scripted("osm", [Page(resources=[cand(1, name="Riverside Food Share", zip_code="10027")], complete=True)]), store, mode="full")
    csv_text = "id,name,zip,phone,hours\nr1,Riverside  Food Share!,10027,(212) 555-0100,Tue 9-5\n"
    r = sync_source(CsvPartnerAdapter("partner-x", lambda: csv_text), store, mode="full")
    assert r.counts.merged_duplicates == 1 and r.counts.created == 0
    recs = real(store)
    assert len(recs) == 1
    rec = recs[0]
    assert {s.sourceId for s in rec.sources} == {"osm", "partner-x"}
    assert rec.phone == "(212) 555-0100" and rec.hours == "Tue 9-5"  # gaps filled, not overwritten


def test_resync_never_erases_human_verification(store):
    sync_source(Scripted("osm", [Page(resources=[cand(1)], complete=True)]), store, mode="full")
    rec, version = store.get_resource("osm-node-1")
    rec.sources[0].lastVerifiedAt = "2026-10-01T00:00:00Z"
    store.put_resource(rec.model_copy(update={"verification": "verified"}), version)
    sync_source(Scripted("osm", [Page(resources=[cand(1)], complete=True)]), store, mode="full")
    after, _ = store.get_resource("osm-node-1")
    assert after.verification == "verified" and after.sources[0].lastVerifiedAt == "2026-10-01T00:00:00Z"


def test_optimistic_locking_detects_concurrent_writers(store):
    sync_source(Scripted("osm", [Page(resources=[cand(1)], complete=True)]), store, mode="full")
    rec, version = store.get_resource("osm-node-1")
    store.put_resource(rec, version)
    with pytest.raises(VersionConflict):
        store.put_resource(rec, version)  # stale version
    with pytest.raises(VersionConflict):
        store.put_resource(rec, None)  # "must not exist"


def test_demo_seed_is_isolated_and_labeled(store):
    sync_source(osm(), store, mode="full")
    assert seed_demo(store) == 5 and seed_demo(store) == 5  # idempotent
    demo = list(store.iter_namespace("demo"))
    assert len(demo) == 5 and all(d.isDemoData and d.id.startswith("demo-") for d in demo)
    inv = store.get_inventory([d.id for d in demo])
    assert inv["demo-fb-002"]["baby_formula"].quantity == 150 and inv["demo-fb-002"]["baby_formula"].isDemoData
    assert "diapers" not in inv["demo-fb-002"]
    # Real organizations never get inventory.
    real_ids = [x.id for x in real(store)][:5]
    assert all(v == {} for v in store.get_inventory(real_ids).values())


def test_zip_geocode_cache_roundtrip(store):
    assert store.get_zip_geo("10027") is None
    store.put_zip_geo("10027", 40.8115, -73.9531, "test")
    g = store.get_zip_geo("10027")
    assert g["latitude"] == 40.8115 and g["provider"] == "test"
