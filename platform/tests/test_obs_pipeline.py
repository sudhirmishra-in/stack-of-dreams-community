"""Metrics from the runtime (per-agent/tool counts), the ingest Lambda (sync detail) and the hourly freshness Lambda."""

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from test_app_metrics import NS, emf, mine  # noqa: F401
from test_orchestrator import MID, ScriptedModel, run, world  # noqa: F401

from navigator.ingest.sync import SyncCounts, SyncResult

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "infra" / "template.yaml").read_text()


# ---------------- runtime: usage now includes tool counts, tool errors and specialist names ----------------

def test_runtime_usage_reports_tool_calls_and_specialists_by_name(world):
    steps = [("tool", "capacity_agent", {"task": "compare capacity"}), ("text", "Done.")]
    spec = [[("tool", "get_capacity_context", {"resource_id": "demo-fb-002"}), ("text", "Demo capacity 650.")]]
    out, _ = run(world, steps, spec)
    u = out["usage"]
    assert u["specialistCalls"] == 1 and u["specialists"] == {"capacity": 1}
    assert u["toolCalls"] == 1 and u["toolErrors"] == 0  # the data tool the specialist ran


def test_runtime_usage_counts_failed_tool_calls(world):
    steps = [("tool", "get_resource_details", {"resource_id": "does-not-exist"}), ("text", "I could not find it.")]
    out, _ = run(world, steps)
    assert out["usage"]["toolCalls"] == 1 and out["usage"]["toolErrors"] == 1
    assert out["usage"]["specialists"] == {}


def test_each_specialist_is_counted_under_its_own_name(world):
    steps = [("tool", "inventory_agent", {"task": "a"}), ("tool", "location_agent", {"task": "b"}), ("text", "ok")]
    spec = [[("text", "inv")], [("text", "loc")]]
    out, _ = run(world, steps, spec)
    assert out["usage"]["specialists"] == {"inventory": 1, "location": 1}


# ---------------- ingest: sync detail metrics ----------------

def result(status="success", **counts):
    return SyncResult("osm", status, "incremental", SyncCounts(**counts), None, 4.2)


def test_sync_result_carries_a_real_duration(store):
    from test_sync import osm
    from navigator.ingest.sync import sync_source

    r = sync_source(osm(), store, mode="full")
    assert isinstance(r.duration_s, float) and r.duration_s >= 0


def test_sync_metrics_success(capsys):
    from navigator.ingest.sync_metrics import emit_sync_metrics

    capsys.readouterr()
    emit_sync_metrics(result("success", created=7, updated=3, rejected=2))
    rows = mine(emf(capsys))
    val = {r[1]: (r[2], r[4]) for r in rows}
    assert val["DataSyncSuccess"] == (1, {"Environment": "pilot", "Source": "osm"})
    assert val["DataSyncFailures"][0] == 0
    assert val["RecordsInserted"][0] == 7 and val["RecordsUpdated"][0] == 3 and val["RecordsRejected"][0] == 2
    assert val["DataSyncDuration"][0] == 4.2
    assert val["SourceApiErrors"][0] == 0
    assert all(r[4]["Source"] == "osm" for r in rows)


def test_sync_metrics_failure_from_the_source_api(capsys):
    from navigator.ingest.sync_metrics import emit_sync_metrics

    r = SyncResult("osm", "failed", "incremental", SyncCounts(), "HttpError: network error: The read operation timed out", 61.0)
    capsys.readouterr()
    emit_sync_metrics(r)
    val = {x[1]: x[2] for x in mine(emf(capsys))}
    assert val["DataSyncFailures"] == 1 and val["DataSyncSuccess"] == 0 and val["SourceApiErrors"] == 1
    assert "RecordsInserted" not in val  # nothing was written by a failed run


@pytest.mark.parametrize("status", ["skipped", "disabled"])
def test_skipped_and_disabled_runs_emit_nothing(capsys, status):
    from navigator.ingest.sync_metrics import emit_sync_metrics

    capsys.readouterr()
    emit_sync_metrics(SyncResult("osm", status))
    assert mine(emf(capsys)) == []


def test_partial_runs_count_as_a_failure_but_keep_the_record_detail(capsys):
    from navigator.ingest.sync_metrics import emit_sync_metrics

    capsys.readouterr()
    emit_sync_metrics(result("partial", created=1, errors=2))
    val = {x[1]: x[2] for x in mine(emf(capsys))}
    assert val["DataSyncSuccess"] == 0 and val["DataSyncFailures"] == 1 and val["RecordsInserted"] == 1


def test_ingest_handler_emits_sync_metrics_once_per_source(capsys, monkeypatch, aws):
    from navigator.ingest import handler as h

    monkeypatch.setattr(h, "sync_all", lambda *a, **k: [result("success", created=1), SyncResult("nyc-cfc", "success", "full", SyncCounts(created=5), None, 1.0)])
    monkeypatch.setattr(h, "build_adapters", lambda *a, **k: {})
    monkeypatch.setenv("DATA_TABLE", "data-t")
    monkeypatch.setattr(h, "DataStore", lambda *a, **k: object())
    monkeypatch.setattr(h, "seed_demo", lambda store: 0)
    capsys.readouterr()
    h.handler({"sources": ["osm", "nyc-cfc"]})
    succ = [(r[4]["Source"], r[2]) for r in mine(emf(capsys), "DataSyncSuccess")]
    assert sorted(succ) == [("nyc-cfc", 1), ("osm", 1)]


# ---------------- hourly freshness Lambda ----------------

def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_freshness_reports_age_in_hours_per_source(store, capsys):
    from navigator.ingest.freshness import make_handler

    now = datetime.now(timezone.utc)
    store.put_sync_state("osm", {"status": "success", "lastSuccessAt": iso(now - timedelta(hours=3, minutes=30))})
    store.put_sync_state("nyc-cfc", {"status": "success", "lastSuccessAt": iso(now - timedelta(days=10))})
    capsys.readouterr()
    out = make_handler(store, clock=lambda: now)({}, None)
    ages = {r[4]["Source"]: r[2] for r in mine(emf(capsys), "DataSyncAge")}
    assert ages["osm"] == pytest.approx(3.5, abs=0.1) and ages["nyc-cfc"] == pytest.approx(240.0, abs=0.1)
    assert all(r[3] == "Hours" for r in mine(emf(capsys)))
    assert out["emitted"] == 2


def test_freshness_does_not_invent_an_age_for_a_source_that_never_succeeded(store, capsys):
    from navigator.ingest.freshness import make_handler

    store.put_sync_state("osm", {"status": "failed"})  # no lastSuccessAt
    capsys.readouterr()
    out = make_handler(store)({}, None)
    assert mine(emf(capsys), "DataSyncAge") == [] and out["unknown"] == ["osm", "nyc-cfc"]


def test_freshness_is_read_only(store):
    from navigator.ingest.freshness import make_handler

    now = datetime.now(timezone.utc)
    store.put_sync_state("osm", {"status": "success", "lastSuccessAt": iso(now)})
    before = store.get_sync_state("osm")
    make_handler(store, clock=lambda: now)({}, None)
    assert store.get_sync_state("osm") == before


def test_freshness_surfaces_store_failures_so_the_lambda_error_alarm_fires(capsys):
    from navigator.ingest.freshness import make_handler

    class Broken:
        def get_sync_state(self, sid):
            raise RuntimeError("dynamodb down")

    with pytest.raises(RuntimeError):
        make_handler(Broken())({}, None)


# ---------------- infrastructure ----------------

def _block(name, nxt):
    s = TEMPLATE.index(f"\n  {name}:")
    e = TEMPLATE.find(f"\n  {nxt}:", s + 1)
    return TEMPLATE[s:e]


def test_metrics_namespace_parameter_reaches_every_emitting_function():
    assert "MetricsNamespace:" in TEMPLATE and "Default: CommunityNavigator/Production" in TEMPLATE
    assert TEMPLATE.count("METRICS_NAMESPACE: !Ref MetricsNamespace") >= 3  # api, ingest, freshness


def test_freshness_function_is_read_only_and_minimal():
    block = "\n".join(l for l in _block("FreshnessFunction", "FreshnessLogGroup").splitlines() if not l.strip().startswith("#"))
    assert "navigator.ingest.freshness.handler" in block
    assert "ReservedConcurrentExecutions: 1" in block
    assert "dynamodb:GetItem" in block and "dynamodb:PutItem" not in block and "dynamodb:UpdateItem" not in block
    assert "UsageTable" not in block and "bedrock" not in block.lower() and "cloudwatch:PutMetricData" not in block


def test_freshness_runs_hourly_and_the_scheduler_may_invoke_it():
    assert "FreshnessSchedule:" in TEMPLATE
    sched = _block("FreshnessSchedule", "CfcMonthlySchedule") if "CfcMonthlySchedule" in TEMPLATE[TEMPLATE.index("FreshnessSchedule:"):] else TEMPLATE[TEMPLATE.index("FreshnessSchedule:"):][:900]
    assert "rate(1 hour)" in sched
    role = TEMPLATE[TEMPLATE.index("SchedulerRole:"):][:1400]
    assert "FreshnessFunction.Arn" in role
