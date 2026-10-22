"""Lean custom metrics in CommunityNavigator/Production (alongside the unchanged Navigator metrics).

Rules under test: each metric has ONE emission point; dimensions are a fixed low-cardinality set (never user, session,
request or trace ids); tokens/costs are only emitted from usage that was actually reported; replays and blocked requests
never emit model metrics; nothing is double counted."""

import json
import re
from pathlib import Path

import pytest
from test_api import app, call, tok  # noqa: F401
from test_research_mode import FakeHarness, ask, google  # noqa: F401

from navigator.gateway.invoker import InvokerError, ModelUsage, RuntimeResult, RuntimeUsage
from navigator.ingest import appmetrics

ME = "invited-user-0001"
NS = "CommunityNavigator/Production"


def emf(capsys):
    """Flatten the EMF lines printed so far into [(namespace, metric, value, unit, dims)]."""
    out = []
    for line in capsys.readouterr().out.splitlines():
        if not line.startswith("{") or '"_aws"' not in line:
            continue
        d = json.loads(line)
        for cw in d["_aws"]["CloudWatchMetrics"]:
            dim_names = cw["Dimensions"][0]
            for m in cw["Metrics"]:
                out.append((cw["Namespace"], m["Name"], d[m["Name"]], m.get("Unit"), {k: d[k] for k in dim_names}))
    return out


def mine(rows, name=None):
    return [r for r in rows if r[0] == NS and (name is None or r[1] == name)]


# ---------------- emitter ----------------

def test_emitter_writes_one_valid_emf_record_with_environment_and_units(capsys, monkeypatch):
    monkeypatch.setenv("ENV_NAME", "pilot")
    assert appmetrics.emit({"AgentLatency": 812.5, "AgentErrors": 1}, AgentType="research") is True
    rows = emf(capsys)
    assert {(r[1], r[3]) for r in rows} == {("AgentLatency", "Milliseconds"), ("AgentErrors", "Count")}
    assert all(r[0] == NS and r[4] == {"Environment": "pilot", "AgentType": "research"} for r in rows)


def test_namespace_is_configurable(capsys, monkeypatch):
    monkeypatch.setenv("METRICS_NAMESPACE", "CommunityNavigator/Staging")
    appmetrics.emit({"ResourceSearches": 1})
    assert emf(capsys)[0][0] == "CommunityNavigator/Staging"


@pytest.mark.parametrize("dim", ["UserId", "sub", "RequestId", "TraceId", "SessionId", "Email", "CorrelationId"])
def test_identifying_dimensions_are_refused_and_never_printed(capsys, dim):
    assert appmetrics.emit({"AgentErrors": 1}, **{dim: "abc123"}) is False
    assert "abc123" not in capsys.readouterr().out


def test_unknown_metric_names_are_refused(capsys):
    assert appmetrics.emit({"MadeUpMetric": 1}) is False
    assert emf(capsys) == []


def test_dimension_values_are_limited_to_known_sets(capsys):
    appmetrics.emit({"AgentInvocations": 1}, AgentType="navigator", AgentName="not-a-real-agent")
    appmetrics.emit({"QuotaRejections": 1}, Reason="a1b2c3d4e5f60718293a")
    appmetrics.emit({"DataSyncFailures": 1}, Source="some.new.source")
    rows = emf(capsys)
    assert rows[0][4]["AgentName"] == "other" and rows[1][4]["Reason"] == "other" and rows[2][4]["Source"] == "other"


def test_model_id_must_look_like_a_model_id(capsys):
    appmetrics.emit({"ModelInputTokens": 5}, AgentType="research", ModelId="us.amazon.nova-lite-v1:0")
    appmetrics.emit({"ModelInputTokens": 5}, AgentType="research", ModelId="my prompt text: hello there")
    rows = emf(capsys)
    assert rows[0][4]["ModelId"] == "us.amazon.nova-lite-v1:0" and rows[1][4]["ModelId"] == "other"


@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf"), "x", None])
def test_invalid_values_are_dropped_not_emitted(capsys, bad):
    assert appmetrics.emit({"ModelInputTokens": bad}, AgentType="research", ModelId="us.amazon.nova-lite-v1:0") is False
    assert emf(capsys) == []


def test_emitter_never_raises_into_the_request_path(monkeypatch):
    monkeypatch.setattr("builtins.print", lambda *a, **k: (_ for _ in ()).throw(OSError("stdout closed")))
    assert appmetrics.emit({"ResourceSearches": 1}) is False


# ---------------- API request metrics (research) ----------------

@pytest.fixture
def research(app):
    h = FakeHarness()
    app.d.pipeline.research_invoker = h
    return app, h


def test_research_success_emits_each_metric_once_with_real_usage(research, capsys):
    app, h = research
    capsys.readouterr()
    s, b, _ = ask(app, tok(sub=ME))
    assert s == 200
    rows = mine(emf(capsys))
    by = lambda n: [r for r in rows if r[1] == n]
    assert [(r[2], r[4].get("AgentType"), r[4].get("AgentName")) for r in by("AgentInvocations")] == [(1, "research", "research")]
    assert [(r[2], r[4]["AgentType"]) for r in by("ModelInvocations")] == [(1, "research")]
    assert [(r[2], r[4]["ModelId"]) for r in by("ModelInputTokens")] == [(120, "us.amazon.nova-lite-v1:0")]
    assert [(r[2], r[4]["ModelId"]) for r in by("ModelOutputTokens")] == [(45, "us.amazon.nova-lite-v1:0")]
    cost = by("EstimatedModelCost")
    assert len(cost) == 1 and cost[0][2] > 0 and cost[0][4]["ModelId"] == "us.amazon.nova-lite-v1:0"
    lat = by("AgentLatency")
    assert len(lat) == 1 and lat[0][3] == "Milliseconds" and lat[0][2] >= 0
    assert by("AgentErrors") == [] and by("UsageUnreported") == [] and by("ModelCostUnavailable") == []


def test_emitted_tokens_equal_what_the_ledger_charged_no_double_count(research, capsys):
    app, h = research
    capsys.readouterr()
    ask(app, tok(sub=ME))
    rows = mine(emf(capsys))
    emitted = sum(r[2] for r in rows if r[1] in ("ModelInputTokens", "ModelOutputTokens"))
    charged = call(app, "GET", "/api/v1/me/usage", token=tok(sub=ME), query={"agent": "research"})[1]["tokensToday"]["used"]
    assert emitted == charged == 165


def test_existing_navigator_namespace_metrics_are_still_emitted_unchanged(research, capsys):
    app, _ = research
    capsys.readouterr()
    ask(app, tok(sub=ME))
    old = [r for r in emf(capsys) if r[0] == "Navigator"]
    names = {r[1] for r in old}
    assert {"AssistantRequests", "ModelTokens"} <= names
    assert sum(r[2] for r in old if r[1] == "ModelTokens") == 165


def test_unknown_model_price_emits_unavailable_not_an_invented_cost(app, capsys):
    class Weird(FakeHarness):
        def invoke(self, payload, session_key, user_key, timeout):
            return RuntimeResult(response="ok", usage=RuntimeUsage(modelInvocations=1, byModel=[ModelUsage(modelId="vendor.brand-new-model-v1:0", inputTokens=10, outputTokens=5)]))

    app.d.pipeline.research_invoker = Weird()
    capsys.readouterr()
    assert ask(app, tok(sub=ME))[0] == 200
    rows = mine(emf(capsys))
    assert [r for r in rows if r[1] == "EstimatedModelCost"] == []
    assert [r[2] for r in rows if r[1] == "ModelCostUnavailable"] == [1]
    assert sum(r[2] for r in rows if r[1] == "ModelInputTokens") == 10  # tokens are real even when the price is unknown


def test_missing_usage_emits_usage_unreported_and_no_token_or_cost_metrics(app, capsys):
    app.d.pipeline.research_invoker = FakeHarness(usage=None)
    capsys.readouterr()
    assert ask(app, tok(sub=ME))[0] == 200
    rows = mine(emf(capsys))
    assert [r[2] for r in rows if r[1] == "UsageUnreported"] == [1]
    assert not [r for r in rows if r[1] in ("ModelInputTokens", "ModelOutputTokens", "EstimatedModelCost")]
    assert [r[2] for r in rows if r[1] == "AgentInvocations"] == [1]


def test_agent_failure_counts_an_error_and_an_invocation_but_no_tokens(app, capsys):
    app.d.pipeline.research_invoker = FakeHarness(fail=True)
    capsys.readouterr()
    assert ask(app, tok(sub=ME))[0] == 503
    rows = mine(emf(capsys))
    assert [r[2] for r in rows if r[1] == "AgentErrors"] == [1]
    assert [r[2] for r in rows if r[1] == "AgentInvocations"] == [1]
    assert not [r for r in rows if r[1] in ("ModelInputTokens", "ModelOutputTokens", "EstimatedModelCost", "AgentLatency")]


def test_replay_emits_no_model_metrics(research, capsys):
    app, h = research
    k = "idem-key-0001"
    ask(app, tok(sub=ME), idempotencyKey=k)
    capsys.readouterr()
    assert ask(app, tok(sub=ME), idempotencyKey=k)[0] == 200
    assert mine(emf(capsys)) == [] and len(h.calls) == 1


def test_blocked_requests_never_count_as_invocations(research, capsys):
    app, h = research
    admin = tok(sub="admin-sub-0001", groups=["pilot-admin"])
    call(app, "PUT", f"/api/v1/admin/users/{ME}", body={"overrides": {"requests_per_user_day": 1}}, token=admin)
    ask(app, tok(sub=ME))
    capsys.readouterr()
    s, _, _ = ask(app, tok(sub=ME), message="another question")
    assert s == 429
    rows = mine(emf(capsys))
    assert [(r[2], r[4]["Reason"]) for r in rows if r[1] == "QuotaRejections"] == [(1, "daily_requests")]
    assert not [r for r in rows if r[1] in ("AgentInvocations", "ModelInputTokens")]


# ---------------- navigator: specialists and tools come from what the runtime reported ----------------

class NavRuntime:
    def __init__(self, **usage):
        self.usage = usage

    def invoke(self, payload, session_key, user_key, timeout):
        u = RuntimeUsage(modelInvocations=4, specialistCalls=1, byModel=[ModelUsage(modelId="us.amazon.nova-lite-v1:0", inputTokens=900, outputTokens=100)], **self.usage)
        return RuntimeResult(response="Here are some pantries.", usage=u)


def test_navigator_reports_specialists_and_tools_from_the_runtime(app, capsys):
    app.d.pipeline.invoker = NavRuntime(toolCalls=3, toolErrors=1, specialists={"capacity": 1})
    capsys.readouterr()
    assert ask(app, tok(sub=ME), message="find food banks near 10027", agent="navigator")[0] == 200
    rows = mine(emf(capsys))
    inv = {(r[4]["AgentType"], r[4]["AgentName"]): r[2] for r in rows if r[1] == "AgentInvocations"}
    assert inv == {("navigator", "orchestrator"): 1, ("navigator", "capacity"): 1}
    assert [r[2] for r in rows if r[1] == "ModelInvocations"] == [4]
    assert [r[2] for r in rows if r[1] == "ToolInvocations"] == [3] and [r[2] for r in rows if r[1] == "ToolErrors"] == [1]
    assert sum(r[2] for r in rows if r[1] == "ModelInputTokens") == 900


def test_a_runtime_without_the_new_fields_still_works(app, capsys):
    app.d.pipeline.invoker = NavRuntime()  # the currently deployed runtime does not report tools or specialist names
    capsys.readouterr()
    assert ask(app, tok(sub=ME), message="find food banks near 10027", agent="navigator")[0] == 200
    rows = mine(emf(capsys))
    assert {(r[4]["AgentName"]) for r in rows if r[1] == "AgentInvocations"} == {"orchestrator"}
    assert not [r for r in rows if r[1] in ("ToolInvocations", "ToolErrors")]


def test_bogus_specialist_names_from_a_runtime_are_bucketed_not_trusted(app, capsys):
    app.d.pipeline.invoker = NavRuntime(specialists={"capacity": 1, "drop table users": 1, "x" * 80: 2})
    capsys.readouterr()
    ask(app, tok(sub=ME), message="find food banks near 10027", agent="navigator")
    names = {r[4]["AgentName"] for r in mine(emf(capsys), "AgentInvocations")}
    assert names <= {"orchestrator", "capacity", "other"}


# ---------------- auth, quota and search metrics at the single API choke points ----------------

def test_authentication_failures_by_reason(app, capsys):
    capsys.readouterr()
    call(app, "GET", "/api/v1/me/usage")  # no token
    call(app, "GET", "/api/v1/me/usage", token="a.b.c")  # malformed/invalid
    rows = mine(emf(capsys), "AuthenticationFailures")
    assert [(r[2], r[4]["Reason"]) for r in rows] == [(1, "unauthorized"), (1, "unauthorized")]


def test_pending_and_forbidden_are_counted_with_their_own_reasons(research, capsys):
    app, _ = research
    capsys.readouterr()
    ask(app, google())  # pending Google user
    call(app, "PUT", "/api/v1/admin/switch", body={"assistantEnabled": False}, token=tok(sub=ME))  # not an admin
    rows = mine(emf(capsys), "AuthenticationFailures")
    assert sorted(r[4]["Reason"] for r in rows) == ["forbidden", "pending_approval"]


def test_successful_calls_and_off_topic_refusals_are_not_failures(app, capsys):
    capsys.readouterr()
    ask(app, tok(sub=ME), message="write me a python script to sort a list", agent="navigator")  # 422 refusal
    call(app, "GET", "/api/v1/health")
    assert mine(emf(capsys), "AuthenticationFailures") == [] and mine(emf(capsys), "QuotaRejections") == []


def test_resource_searches_and_no_results_are_counted(app, capsys, monkeypatch):
    capsys.readouterr()
    body = {"zipCode": "10027", "resourceType": "food_assistance"}
    assert call(app, "POST", "/api/v1/resources/search", body=body, token=tok(sub=ME))[0] == 200
    rows = mine(emf(capsys))
    assert [r[2] for r in rows if r[1] == "ResourceSearches"] == [1]

    class Empty:
        totalResults = 0

        def model_dump(self, **k):
            return {"resources": [], "totalResults": 0}

    real = app.d.search.search
    monkeypatch.setattr(app.d.search, "search", lambda *a, **k: real(*a, **k).model_copy(update={"totalResults": 0, "resources": []}))
    capsys.readouterr()
    assert call(app, "POST", "/api/v1/resources/search", body=body, token=tok(sub=ME))[0] == 200
    rows = mine(emf(capsys))
    assert [r[2] for r in rows if r[1] == "ResourceSearches"] == [1] and [r[2] for r in rows if r[1] == "ResourceSearchNoResults"] == [1]


def test_no_emitted_dimension_ever_contains_an_identifier(research, capsys):
    app, _ = research
    capsys.readouterr()
    ask(app, tok(sub=ME))
    ask(app, google())
    call(app, "GET", "/api/v1/me/usage")
    text = json.dumps(mine(emf(capsys)))
    assert ME not in text and "google-sub" not in text and not re.search(r"[0-9a-f]{32}", text)
