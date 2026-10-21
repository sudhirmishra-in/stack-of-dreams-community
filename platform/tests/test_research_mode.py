"""The general assistant ("research" agent) behind the pilot API: same server-side controls as the AI for Good
assistant (sign-in, pending-approval gate, kill switch, per-user daily/monthly quota, shared pilot-wide cap, real token
accounting), but no community-resources topic filter and its own per-user counters."""

import pytest
from test_api import app, call, tok  # noqa: F401  (fixtures/helpers reused)

from navigator.gateway.invoker import InvokerError, ModelUsage, RuntimeResult, RuntimeUsage

ME = "invited-user-0001"
GOOGLE_SUB = "google-sub-0001-aaaa"
POOL = "us-east-2_AbCdEfGhI"
SID = "session-abcdef-1234"


class FakeHarness:
    def __init__(self, text="Agentic AI means models that plan and use tools.", usage=(120, 45), fail=False):
        self.calls, self.text, self.usage, self.fail = [], text, usage, fail

    def invoke(self, payload, session_key, user_key, timeout):
        self.calls.append(payload)
        if self.fail:
            raise InvokerError("harness down")
        usage = RuntimeUsage(modelInvocations=1, byModel=[ModelUsage(modelId="us.amazon.nova-lite-v1:0", inputTokens=self.usage[0], outputTokens=self.usage[1])]) if self.usage else None
        return RuntimeResult(response=self.text, usage=usage)


@pytest.fixture
def research(app):
    h = FakeHarness()
    app.d.pipeline.research_invoker = h
    return app, h


def ask(app, token, message="What is agentic AI?", agent="research", **extra):
    return call(app, "POST", "/api/v1/assistant", body={"message": message, "sessionId": SID, "agent": agent, **extra}, token=token)


def usage(app, token, agent=None):
    return call(app, "GET", "/api/v1/me/usage", token=token, query={"agent": agent} if agent else None)[1]


def google(sub=GOOGLE_SUB):
    return tok(sub=sub, groups=[f"{POOL}_Google"], username=f"google_{sub}")


def test_research_answers_a_general_question_the_navigator_would_refuse(research):
    app, h = research
    q = "write me a python script to sort a list"  # clearly off-topic for the navigator
    s, b, _ = ask(app, tok(sub=ME), message=q)
    assert s == 200 and b["response"].startswith("Agentic AI") and b["agentId"] == "research"
    assert b["citations"] == [] and h.calls and h.calls[0]["prompt"] == q
    # the same question to the navigator is out of scope (it only helps with community resources)
    s2, b2, _ = ask(app, tok(sub=ME), message=q, agent="navigator")
    assert s2 == 422 and b2["error"]["code"] == "out_of_scope"


def test_history_is_passed_to_the_harness_bounded(research):
    app, h = research
    hist = [{"role": "user", "content": f"q{i}"} if i % 2 == 0 else {"role": "assistant", "content": f"a{i}"} for i in range(8)]
    assert ask(app, tok(sub=ME), message="and then?", history=hist)[0] == 200
    sent = h.calls[0]["history"]
    assert 0 < len(sent) <= 4 and sent[-1]["content"] == "a7"  # only the most recent turns


def test_unknown_agent_value_is_rejected(research):
    app, h = research
    s, _, _ = ask(app, tok(sub=ME), agent="testagent")
    assert s == 400 and h.calls == []


def test_unauthenticated_research_requests_are_refused_without_invoking(research):
    app, h = research
    assert ask(app, None)[0] == 401 and h.calls == []


def test_pending_google_user_cannot_use_research_and_the_harness_is_never_called(research):
    app, h = research
    s, b, _ = ask(app, google())
    assert s == 403 and b["error"]["code"] == "pending_approval" and h.calls == []


def test_approved_google_user_can_use_research(research):
    app, h = research
    admin = tok(sub="admin-sub-0001", groups=["pilot-admin"])
    call(app, "PUT", f"/api/v1/admin/users/{GOOGLE_SUB}", body={"approved": True}, token=admin)
    assert ask(app, google())[0] == 200 and len(h.calls) == 1


def test_kill_switch_stops_research_before_the_harness(research):
    app, h = research
    admin = tok(sub="admin-sub-0001", groups=["pilot-admin"])
    call(app, "PUT", "/api/v1/admin/switch", body={"assistantEnabled": False}, token=admin)
    s, _, _ = ask(app, tok(sub=ME))
    assert s == 503 and h.calls == []


def test_disabled_user_is_blocked(research):
    app, h = research
    admin = tok(sub="admin-sub-0001", groups=["pilot-admin"])
    call(app, "PUT", f"/api/v1/admin/users/{ME}", body={"disabled": True}, token=admin)
    assert ask(app, tok(sub=ME))[0] == 403 and h.calls == []


def test_research_has_its_own_per_user_daily_limit_separate_from_the_navigator(research):
    app, h = research
    admin = tok(sub="admin-sub-0001", groups=["pilot-admin"])
    call(app, "PUT", f"/api/v1/admin/users/{ME}", body={"overrides": {"requests_per_user_day": 1}}, token=admin)
    assert ask(app, tok(sub=ME))[0] == 200
    s, b, _ = ask(app, tok(sub=ME), message="Another question about AWS.")
    assert s == 429 and b["error"]["details"]["reason"] == "daily_requests" and len(h.calls) == 1  # blocked BEFORE the harness
    # the navigator allowance is untouched: it still has its own 1 request
    assert ask(app, tok(sub=ME), message="baby formula near 10027", agent="navigator")[0] == 200


def test_pilot_wide_daily_cap_is_shared_by_both_assistants(research):
    app, h = research
    admin = tok(sub="admin-sub-0001", groups=["pilot-admin"])
    call(app, "PUT", "/api/v1/admin/quotas", body={"overrides": {"requests_per_app_day": 1}}, token=admin)
    assert ask(app, tok(sub=ME))[0] == 200
    s, b, _ = ask(app, tok(sub="invited-user-0002"), message="baby formula near 10027", agent="navigator")
    assert s == 429 and b["error"]["details"]["reason"] == "application_daily"


def test_real_token_usage_from_the_harness_is_settled_into_the_research_counters(research):
    app, h = research
    s, b, _ = ask(app, tok(sub=ME))
    assert b["usage"]["inputTokens"] == 120 and b["usage"]["outputTokens"] == 45
    u = usage(app, tok(sub=ME), "research")
    assert u["daily"]["used"] == 1 and u["tokensToday"]["used"] == 165  # actual, not the reservation estimate
    n = usage(app, tok(sub=ME))  # default = navigator: untouched
    assert n["daily"]["used"] == 0 and n["tokensToday"]["used"] == 0


def test_me_usage_agent_parameter_is_validated(research):
    app, _ = research
    s, _, _ = call(app, "GET", "/api/v1/me/usage", token=tok(sub=ME), query={"agent": "bogus"})
    assert s == 400


def test_harness_failure_returns_503_and_releases_the_reservation(app):
    app.d.pipeline.research_invoker = FakeHarness(fail=True)
    assert ask(app, tok(sub=ME))[0] == 503
    assert usage(app, tok(sub=ME), "research")["daily"]["used"] == 0  # never charged


def test_research_unavailable_when_no_harness_is_configured(app):
    app.d.pipeline.research_invoker = None
    s, b, _ = ask(app, tok(sub=ME))
    assert s == 503 and usage(app, tok(sub=ME), "research")["daily"]["used"] == 0


def test_missing_usage_from_the_harness_charges_the_reservation_not_zero(app):
    app.d.pipeline.research_invoker = FakeHarness(usage=None)
    assert ask(app, tok(sub=ME))[0] == 200
    assert usage(app, tok(sub=ME), "research")["tokensToday"]["used"] > 0


def test_replay_with_the_same_idempotency_key_is_not_charged_twice(research):
    app, h = research
    k = "idem-key-0001"
    a = ask(app, tok(sub=ME), idempotencyKey=k)
    b = ask(app, tok(sub=ME), idempotencyKey=k)
    assert a[0] == b[0] == 200 and len(h.calls) == 1 and usage(app, tok(sub=ME), "research")["daily"]["used"] == 1


def test_overlong_research_message_is_rejected_before_any_cost(research):
    app, h = research
    s, _, _ = ask(app, tok(sub=ME), message="x" * 5000)
    assert s in (400, 422) and h.calls == [] and usage(app, tok(sub=ME), "research")["daily"]["used"] == 0


# ---- the boto3 adapter, tested with a fake client (real stream event shapes) ----

def _events(text_parts, usage=None, error=None):
    ev = [{"messageStart": {"role": "assistant"}}]
    ev += [{"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": t}}} for t in text_parts]
    if error:
        ev.append({error: {"message": "boom"}})
    ev += [{"messageStop": {"stopReason": "end_turn"}}]
    if usage:
        ev.append({"metadata": {"usage": {"inputTokens": usage[0], "outputTokens": usage[1], "totalTokens": sum(usage)}}})
    return ev


class FakeClient:
    def __init__(self, events):
        self.events, self.kwargs = events, None

    def invoke_harness(self, **kw):
        self.kwargs = kw
        return {"stream": iter(self.events)}


def test_harness_invoker_parses_text_usage_and_sends_bounded_messages():
    from navigator.gateway.invoker import HarnessInvoker

    c = FakeClient(_events(["Hello ", "<thinking>hidden</thinking>world"], usage=(10, 4)))
    inv = HarnessInvoker("us-east-1", "arn:aws:bedrock-agentcore:us-east-1:123456789012:harness/h-1", client=c)
    r = inv.invoke({"prompt": "hi", "history": [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]}, "s" * 64, "u" * 32, 25)
    assert r.response == "Hello world"  # scratch reasoning removed
    assert r.usage.byModel[0].inputTokens == 10 and r.usage.byModel[0].outputTokens == 4 and r.usage.modelInvocations == 1
    msgs = c.kwargs["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"] and msgs[-1]["content"] == [{"text": "hi"}]
    assert c.kwargs["runtimeSessionId"] == "s" * 64 and c.kwargs["runtimeUserId"] == "u" * 32
    assert c.kwargs["timeoutSeconds"] == 25 and c.kwargs["maxIterations"] <= 6  # per-call caps, in addition to the harness's own


@pytest.mark.parametrize("event", ["internalServerException", "validationException", "runtimeClientError"])
def test_harness_invoker_turns_stream_errors_into_invoker_errors(event):
    from navigator.gateway.invoker import HarnessInvoker

    inv = HarnessInvoker("us-east-1", "arn:aws:bedrock-agentcore:us-east-1:123456789012:harness/h-1", client=FakeClient(_events(["x"], error=event)))
    with pytest.raises(InvokerError):
        inv.invoke({"prompt": "hi", "history": []}, "s" * 64, "u" * 32, 25)


def test_harness_invoker_empty_reply_is_an_error_not_a_blank_answer():
    from navigator.gateway.invoker import HarnessInvoker

    inv = HarnessInvoker("us-east-1", "arn:aws:bedrock-agentcore:us-east-1:123456789012:harness/h-1", client=FakeClient(_events([])))
    with pytest.raises(InvokerError):
        inv.invoke({"prompt": "hi", "history": []}, "s" * 64, "u" * 32, 25)
