"""CommunityNavigator-Production-Observability: the dashboard must only reference metrics that are really emitted, with the
exact dimension sets they are emitted with (CloudWatch treats a different dimension set as a different, empty metric)."""

import json
import re
from collections import defaultdict
from pathlib import Path

import pytest
from test_api import app, call, tok  # noqa: F401
from test_app_metrics import NS, emf
from test_research_mode import FakeHarness, ask  # noqa: F401

from navigator.gateway import request_metrics
from navigator.gateway.invoker import ModelUsage, RuntimeUsage
from navigator.ingest import appmetrics
from navigator.ingest.freshness import make_handler
from navigator.ingest.sync import SyncCounts, SyncResult
from navigator.ingest.sync_metrics import emit_sync_metrics

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "infra" / "template.yaml").read_text()
DASHBOARD_NAME = "CommunityNavigator-Production-Observability"
VARS = {
    "${AWS::Region}": "us-east-2",
    "${MetricsNamespace}": NS,
    "${EnvName}": "pilot",
    "${ApiFunction}": "navigator-api-pilot",
    "${IngestFunction}": "navigator-ingest-pilot",
    "${FreshnessFunction}": "navigator-freshness-pilot",
}
AWS_METRICS = {
    "AWS/Lambda": {"Errors", "Throttles", "Duration", "ConcurrentExecutions", "Invocations"},
    "AWS/Bedrock": {"InputTokenCount", "OutputTokenCount", "Invocations"},
    "AWS/Bedrock-AgentCore": {"Invocations", "Latency", "Errors", "SystemErrors", "UserErrors", "Throttles", "Sessions", "ActiveSessionCount"},
}
STATS = {"Sum", "Average", "Maximum", "Minimum", "SampleCount", "p50", "p90", "p95", "p99"}
IDENTIFYING = {"userid", "user", "sub", "email", "requestid", "traceid", "sessionid", "correlationid", "username"}


# ---------------- load the dashboard exactly as CloudFormation would render it ----------------

def _body_text() -> str:
    start = TEMPLATE.index("\n  ObservabilityDashboard:")
    block = TEMPLATE[start:]
    m = re.search(r"DashboardBody: !Sub \|\n((?:        .*\n|\n)+)", block)
    assert m, "ObservabilityDashboard has no DashboardBody"
    return "\n".join(line[8:] for line in m.group(1).splitlines())


def dashboard() -> dict:
    text = _body_text()
    for k, v in VARS.items():
        text = text.replace(k, v)
    assert "${" not in text, "unresolved template variable in the dashboard body: " + re.findall(r"\$\{[^}]*\}", text)[0]
    return json.loads(text)


def widgets():
    return dashboard()["widgets"]


def metric_rows():
    """Yield (widget, [row...]) for every metric widget; rows are the raw metric arrays."""
    for w in widgets():
        if w["type"] == "metric":
            yield w, w["properties"]["metrics"]


def custom_refs():
    """All references into the application namespace: (metric, {dim: value}, widget title)."""
    refs = []
    for w, rows in metric_rows():
        for row in rows:
            if not row or isinstance(row[0], dict) or row[0] != NS:
                continue
            body = [x for x in row[2:] if not isinstance(x, dict)]
            assert len(body) % 2 == 0, f"odd dimension list in {w['properties']['title']}: {row}"
            refs.append((row[1], dict(zip(body[0::2], body[1::2])), w["properties"]["title"]))
    return refs


# ---------------- what is REALLY emitted (run the real code paths) ----------------

@pytest.fixture
def emitted(app, capsys):
    capsys.readouterr()
    usage = RuntimeUsage(modelInvocations=3, specialistCalls=1, toolCalls=2, toolErrors=1, specialists={"capacity": 1},
                         byModel=[ModelUsage(modelId="us.amazon.nova-lite-v1:0", inputTokens=100, outputTokens=20)])
    for agent in ("navigator", "research"):
        request_metrics.emit_success(agent, usage=usage, latency_ms=900, classifier_model="us.amazon.nova-micro-v1:0", classifier_tokens=(10, 2))
        request_metrics.emit_success(agent, usage=None, latency_ms=900)  # UsageUnreported
        request_metrics.emit_failure(agent)
    request_metrics.emit_success("research", usage=RuntimeUsage(modelInvocations=1, byModel=[ModelUsage(modelId="vendor.unpriced-v1:0", inputTokens=1, outputTokens=1)]), latency_ms=5)  # ModelCostUnavailable
    for src in ("osm", "nyc-cfc"):
        emit_sync_metrics(SyncResult(src, "success", "incremental", SyncCounts(created=1, updated=1, rejected=1), None, 3.0))
        emit_sync_metrics(SyncResult(src, "failed", "incremental", SyncCounts(), "HttpError: boom", 2.0))

    class Store:
        def get_sync_state(self, sid):
            return {"lastSuccessAt": "2026-10-20T00:00:00Z"}

    make_handler(Store())({}, None)
    # API choke points: sign-in refusal, quota rejection, search
    call(app, "GET", "/api/v1/me/usage")
    app.d.pipeline.research_invoker = FakeHarness()
    admin = tok(sub="admin-sub-0001", groups=["pilot-admin"])
    call(app, "PUT", "/api/v1/admin/users/invited-user-0001", body={"overrides": {"requests_per_user_day": 1}}, token=admin)
    ask(app, tok(sub="invited-user-0001"))
    ask(app, tok(sub="invited-user-0001"), message="again")
    call(app, "POST", "/api/v1/resources/search", body={"zipCode": "10027", "resourceType": "food_assistance"}, token=tok(sub="invited-user-0001"))
    real = app.d.search.search
    app.d.search.search = lambda *a, **k: real(*a, **k).model_copy(update={"totalResults": 0, "resources": []})
    call(app, "POST", "/api/v1/resources/search", body={"zipCode": "10027", "resourceType": "food_assistance"}, token=tok(sub="invited-user-0001"))
    sets: dict[str, set[frozenset[str]]] = defaultdict(set)
    for ns, name, _v, _u, dims in emf(capsys):
        if ns == NS:
            sets[name].add(frozenset(dims))
    return sets


# ---------------- tests ----------------

def test_dashboard_is_defined_in_the_stack_with_the_requested_name():
    assert f"DashboardName: {DASHBOARD_NAME}" in TEMPLATE
    assert "ObservabilityDashboardUrl:" in TEMPLATE  # a ready-made link in the stack outputs


def test_body_is_valid_json_and_fits_cloudwatch_limits():
    body = dashboard()
    assert 10 <= len(body["widgets"]) <= 100
    assert len(_body_text().encode()) < 900_000  # the API limit is 1 MB


def test_every_widget_has_a_title_a_valid_position_and_nothing_overlaps():
    taken: set[tuple[int, int]] = set()
    for w in widgets():
        title = w["properties"].get("title") or w["properties"].get("markdown", "")[:30]
        assert title, "widget without a title"
        x, y, wd, ht = w["x"], w["y"], w["width"], w["height"]
        assert 0 <= x and x + wd <= 24 and wd >= 3 and ht >= 1, (title, x, wd)
        cells = {(cx, cy) for cx in range(x, x + wd) for cy in range(y, y + ht)}
        assert not (cells & taken), f"overlap: {title}"
        taken |= cells


def test_required_topics_are_covered():
    titles = " | ".join(w["properties"].get("title", "") for w in widgets()).lower()
    for topic in ("latency", "token", "cost", "error", "quota", "sign-in", "freshness", "search", "agent"):
        assert topic in titles, f"no widget about {topic}"


def test_application_metrics_are_real_metric_names():
    refs = custom_refs()
    assert len(refs) >= 25
    for name, _dims, title in refs:
        assert name in appmetrics.UNITS, f"{name} (in '{title}') is not a metric this application emits"


def test_every_application_reference_uses_a_dimension_set_that_is_really_emitted(emitted):
    problems = []
    for name, dims, title in custom_refs():
        got = frozenset(dims)
        if got not in emitted.get(name, set()):
            problems.append(f"{name} {sorted(got)} in '{title}' (emitted sets: {[sorted(s) for s in emitted.get(name, [])]})")
    assert not problems, "\n".join(problems)


def test_dimension_values_are_values_the_code_can_emit():
    for name, dims, title in custom_refs():
        assert dims.get("Environment") == "pilot", (name, title)
        for dim, value in dims.items():
            if dim in appmetrics.KNOWN_VALUES:
                assert value in appmetrics.KNOWN_VALUES[dim], f"{name}: {dim}={value} in '{title}' can never be emitted"
            if dim == "ModelId":
                assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,79}", value)
        assert not ({d.lower() for d in dims} & IDENTIFYING), (name, title)


def test_provider_metrics_are_real_and_other_regions_are_explicit():
    seen_regions = set()
    for w, rows in metric_rows():
        for row in rows:
            if not row or isinstance(row[0], dict):
                continue
            ns, metric = row[0], row[1]
            if ns == NS:
                continue
            assert ns in AWS_METRICS and metric in AWS_METRICS[ns], f"unexpected metric {ns}/{metric} in {w['properties']['title']}"
            opts = [x for x in row if isinstance(x, dict)]
            seen_regions.add(opts[0].get("region") if opts else None)
    # the general assistant's model runs in us-east-1: its Bedrock counts must be read from that region
    assert "us-east-1" in seen_regions


def test_search_expressions_are_limited_to_agentcore_provider_metrics():
    for w, rows in metric_rows():
        for row in rows:
            if row and isinstance(row[0], dict) and "SEARCH(" in row[0].get("expression", ""):
                assert "AWS/Bedrock-AgentCore" in row[0]["expression"], row[0]["expression"]


def test_statistics_are_valid_and_percentiles_come_from_the_latency_samples():
    for w, rows in metric_rows():
        p = w["properties"]
        assert p.get("stat", "Sum") in STATS, p["title"]
        for row in rows:
            for o in [x for x in row if isinstance(x, dict)]:
                if "stat" in o:
                    assert o["stat"] in STATS, (p["title"], o["stat"])
    lat = [(w, r) for w, rows in metric_rows() for r in rows if len(r) > 1 and r[0] == NS and r[1] == "AgentLatency"]
    stats = {o.get("stat") or w["properties"].get("stat") for w, r in lat for o in [next((x for x in r if isinstance(x, dict)), {})]}
    assert {"p50", "p95", "p99"} <= stats


def test_ratio_expressions_cannot_divide_by_zero():
    found = 0
    for w, rows in metric_rows():
        for row in rows:
            if row and isinstance(row[0], dict) and "expression" in row[0]:
                expr = row[0]["expression"]
                if "/" in expr and "SEARCH" not in expr:
                    found += 1
                    assert "IF(" in expr, f"unguarded division in '{w['properties']['title']}': {expr}"
    assert found >= 3  # error rate, model calls per request, cost per successful request


def test_expression_ids_are_unique_and_defined_within_each_widget():
    for w, rows in metric_rows():
        ids, used = [], set()
        for row in rows:
            opts = next((x for x in row if isinstance(x, dict)), {})
            if "id" in opts:
                ids.append(opts["id"])
            if "expression" in opts and "SEARCH(" not in opts["expression"]:  # SEARCH strings contain stat names like p95
                used |= set(re.findall(r"\b([a-z]+\d+)\b", opts["expression"]))
        assert len(ids) == len(set(ids)), f"duplicate ids in {w['properties']['title']}"
        assert used <= set(ids), f"{w['properties']['title']} uses undefined ids {used - set(ids)}"


def test_estimated_cost_is_labelled_as_an_estimate():
    for w in widgets():
        t = w["properties"].get("title", "")
        if "cost" in t.lower():
            assert "estimate" in t.lower() or "est." in t.lower(), t


def test_dashboard_never_exposes_individual_users():
    text = _body_text().lower()
    for bad in IDENTIFYING - {"user"}:
        assert f'"{bad}"' not in text


def test_application_metrics_are_always_read_from_the_stack_region():
    """Our custom metrics live in the region the stack runs in (us-east-2). Only AWS provider metrics may point at another
    region (the general assistant's Bedrock calls run in us-east-1). A custom metric row with another region would read an
    empty namespace and silently show no data."""
    for w, rows in metric_rows():
        for row in rows:
            if row and not isinstance(row[0], dict) and row[0] == NS:
                opts = next((x for x in row if isinstance(x, dict)), {})
                assert opts.get("region", "us-east-2") == "us-east-2", f"{row[1]} in '{w['properties']['title']}' reads region {opts['region']}"
