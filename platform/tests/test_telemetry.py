"""Span export readiness for AgentCore Observability: no message content leaves the runtime on spans, every agent is
named so traces can tell them apart, the API's correlation id reaches the runtime, and the OTel distro is packaged."""

import json
from pathlib import Path

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from navigator.agents import telemetry
from navigator.agents.meter import UsageMeter, clamp_limits
from navigator.agents.orchestrator import build_orchestrator, build_specialists
from navigator.agents.safety import Observed

ROOT = Path(__file__).resolve().parents[1]
SECRET = "my-secret-prompt-text-12345"


def provider_with_exporter():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))  # synchronous: exports inside on_end, like the worst case
    return provider, exporter


def emit_content_span(provider):
    tracer = provider.get_tracer("t")
    with tracer.start_as_current_span("invoke_agent orchestrator") as span:
        span.set_attribute("gen_ai.agent.name", "orchestrator")
        span.set_attribute("gen_ai.usage.input_tokens", 123)
        span.set_attribute("gen_ai.usage.output_tokens", 45)
        span.set_attribute("gen_ai.request.model", "us.amazon.nova-lite-v1:0")
        span.set_attribute("gen_ai.input.messages", json.dumps([{"role": "user", "content": SECRET}]))
        span.set_attribute("gen_ai.output.messages", SECRET)
        span.set_attribute("gen_ai.tool.call.arguments", SECRET)
        span.set_attribute("gen_ai.prompt.0.content", SECRET)
        span.set_attribute("gen_ai.completion", SECRET)
        span.add_event("gen_ai.user.message", {"content": SECRET})
        span.add_event("gen_ai.choice", {"message": SECRET, "finish_reason": "stop"})
        span.add_event("gen_ai.tool.message", {"content": SECRET, "id": "t1"})
        span.add_event("exception", {"exception.type": "ValueError", "exception.message": f"bad input {SECRET}", "exception.stacktrace": f"... {SECRET}"})
        span.add_event("harmless", {"detail": "kept"})


def dump(exporter):
    return json.dumps([{"name": s.name, "attrs": dict(s.attributes), "events": [(e.name, dict(e.attributes)) for e in s.events]} for s in exporter.get_finished_spans()], default=str)


def test_without_the_scrubber_content_would_leave_the_runtime(monkeypatch):
    provider, exporter = provider_with_exporter()
    emit_content_span(provider)
    assert SECRET in dump(exporter)  # the problem this module exists to prevent


def test_scrubber_removes_message_and_tool_content_before_export_even_when_installed_after_the_exporter():
    provider, exporter = provider_with_exporter()
    assert telemetry.install_span_scrubber(provider) is True  # installed AFTER the exporting processor
    emit_content_span(provider)
    out = dump(exporter)
    assert SECRET not in out
    span = exporter.get_finished_spans()[0]
    # useful, non-sensitive telemetry is untouched
    assert span.attributes["gen_ai.agent.name"] == "orchestrator"
    assert span.attributes["gen_ai.usage.input_tokens"] == 123 and span.attributes["gen_ai.usage.output_tokens"] == 45
    assert span.attributes["gen_ai.request.model"] == "us.amazon.nova-lite-v1:0"
    names = [e.name for e in span.events]
    assert "harmless" in names and "exception" in names
    assert not any(n.startswith("gen_ai.") for n in names)  # content events dropped entirely
    exc = next(e for e in span.events if e.name == "exception")
    assert exc.attributes["exception.type"] == "ValueError" and "exception.message" not in exc.attributes and "exception.stacktrace" not in exc.attributes


def test_scrubber_installed_twice_is_harmless():
    provider, exporter = provider_with_exporter()
    assert telemetry.install_span_scrubber(provider) and telemetry.install_span_scrubber(provider)
    emit_content_span(provider)
    assert SECRET not in dump(exporter)


def test_install_does_nothing_without_an_sdk_provider():
    class NotAnSdkProvider:
        pass

    assert telemetry.install_span_scrubber(NotAnSdkProvider()) is False  # reported, never raises


def test_credential_identifiers_are_scrubbed_but_routing_details_are_kept():
    # The AWS SDK instrumentation records the role session's temporary access key ID on every DynamoDB span.
    assert telemetry.is_sensitive_attribute("aws.auth.account.access_key")
    provider, exporter = provider_with_exporter()
    assert telemetry.install_span_scrubber(provider)
    with provider.get_tracer("t").start_as_current_span("DynamoDB.GetItem") as span:
        span.set_attribute("aws.auth.account.access_key", "ASIAEXAMPLEKEYID1234")
        span.set_attribute("aws.dynamodb.table_names", ["navigator-data-pilot"])
        span.set_attribute("db.operation", "GetItem")
    out = exporter.get_finished_spans()[0]
    assert "aws.auth.account.access_key" not in out.attributes and "ASIAEXAMPLEKEYID1234" not in dump(exporter)
    assert out.attributes["db.operation"] == "GetItem" and out.attributes["aws.dynamodb.table_names"] == ("navigator-data-pilot",)


def test_scrub_attribute_rules():
    assert telemetry.is_content_attribute("gen_ai.input.messages")
    assert telemetry.is_content_attribute("gen_ai.prompt.0.content")
    assert telemetry.is_content_attribute("gen_ai.completion.0.content")
    assert telemetry.is_content_attribute("gen_ai.tool.call.arguments") and telemetry.is_content_attribute("gen_ai.tool.call.result")
    assert telemetry.is_content_attribute("gen_ai.system_instructions") and telemetry.is_content_attribute("system_prompt")
    for ok in ("gen_ai.usage.input_tokens", "gen_ai.agent.name", "gen_ai.tool.name", "gen_ai.operation.name", "correlation.id", "gen_ai.request.max_tokens"):
        assert not telemetry.is_content_attribute(ok), ok


def test_correlation_id_is_attached_to_the_current_span():
    provider, exporter = provider_with_exporter()
    tracer = provider.get_tracer("t")
    from opentelemetry import trace

    with tracer.start_as_current_span("request") as span:
        assert telemetry.tag_current_span(correlation_id="abc123def456", span=span)
    assert exporter.get_finished_spans()[0].attributes["correlation.id"] == "abc123def456"
    assert telemetry.tag_current_span(correlation_id="x") in (True, False)  # never raises without an active span
    assert trace is not None


# ---- agents are named so traces can distinguish them ----

class Spy:
    instances: list = []

    def __init__(self, **kw):
        self.kw = kw
        self.metrics = None
        Spy.instances.append(self)

    def __call__(self, *a, **k):
        return "specialist answer"


def _factory(max_tokens):
    return object()


def test_orchestrator_and_each_specialist_are_named():
    Spy.instances = []
    box = object()
    orch = build_orchestrator(box, UsageMeter(clamp_limits({})), _factory, "m", agent_cls=Spy)
    assert orch.kw["name"] == "orchestrator"
    for tool_name, expected in {
        "resource_discovery_agent": "resource_discovery",
        "inventory_agent": "inventory",
        "capacity_agent": "capacity",
        "location_agent": "location",
    }.items():
        Spy.instances = []
        # a fresh meter each time: one request may call at most 3 specialists
        tools = {t.tool_name: t for t in build_specialists(box, UsageMeter(clamp_limits({})), _factory, "m", [orch], Spy)}
        tools[tool_name](task="do the thing")
        assert [i.kw["name"] for i in Spy.instances] == [expected]


# ---- correlation id from the API to the runtime, and structured runtime logs ----

class _Capture:
    def __init__(self):
        import logging

        self.lines: list[str] = []
        outer = self

        class H(logging.Handler):
            def emit(self, record):
                outer.lines.append(record.getMessage())

        self.handler = H()
        self.logger = logging.getLogger("navigator")

    def __enter__(self):
        self.logger.addHandler(self.handler)
        return self

    def __exit__(self, *a):
        self.logger.removeHandler(self.handler)

    def events(self):
        return [json.loads(l) for l in self.lines if l.startswith("{")]


def test_runtime_payload_accepts_a_bounded_correlation_id_and_logs_it(monkeypatch):
    from navigator.agents import runtime

    monkeypatch.setattr(runtime, "_components", lambda: (None, None, None))
    monkeypatch.setattr(runtime, "answer", lambda payload, *a, **k: {"response": "ok", "citations": [], "uncertainty": [], "usage": {"modelInvocations": 2, "specialistCalls": 1, "byModel": [{"modelId": "us.amazon.nova-lite-v1:0", "inputTokens": 100, "outputTokens": 20}]}})
    with _Capture() as cap:
        out = runtime.run({"prompt": f"find food {SECRET}", "correlationId": "corr-0123456789abcdef"})
    assert out["response"] == "ok"
    logged = cap.events()
    ev = next(e for e in logged if e.get("event") == "agent_invocation")
    assert ev["correlationId"] == "corr-0123456789abcdef" and ev["status"] == "ok" and ev["agentName"] == "orchestrator"
    assert ev["inputTokens"] == 100 and ev["outputTokens"] == 20 and ev["specialistCalls"] == 1 and isinstance(ev["durationMs"], int)
    assert SECRET not in json.dumps(logged)  # the prompt is never logged


@pytest.mark.parametrize("bad", ["x" * 200, "has spaces and !!", 12345, ""])
def test_malformed_correlation_ids_are_ignored_not_trusted(monkeypatch, bad):
    from navigator.agents import runtime

    monkeypatch.setattr(runtime, "_components", lambda: (None, None, None))
    monkeypatch.setattr(runtime, "answer", lambda payload, *a, **k: {"response": "ok", "citations": [], "uncertainty": [], "usage": None})
    with _Capture() as cap:
        out = runtime.run({"prompt": "find food", "correlationId": bad})
    assert out["response"] == "ok"
    ev = next(e for e in cap.events() if e.get("event") == "agent_invocation")
    assert ev.get("correlationId") in (None, "")


def test_gateway_sends_its_correlation_id_to_the_runtime():
    from test_gateway import ME  # reuse the gateway test identity

    assert ME is not None
    from navigator.gateway.pipeline import AssistantPipeline

    assert "correlation_id" in AssistantPipeline._payload.__code__.co_varnames


# ---- packaging ----

def test_runtime_package_includes_the_aws_otel_distro():
    pyproject = (ROOT / "agentcore" / "app" / "community_navigator" / "pyproject.toml").read_text()
    assert "aws-opentelemetry-distro>=0.18" in pyproject  # required for spans to be delivered (AgentCore docs)


def test_runtime_is_started_through_the_otel_wrapper():
    cfg = json.loads((ROOT / "agentcore" / "agentcore" / "agentcore.json").read_text())
    assert cfg["runtimes"][0]["entrypoint"] == "main.py"  # the CLI wraps it with opentelemetry-instrument at deploy


# ---- fail-closed behaviour ----

def test_ensure_content_safe_tracing_reports_each_outcome():
    provider, _ = provider_with_exporter()
    assert telemetry.ensure_content_safe_tracing(provider) == "scrubbing"

    class NotAnSdkProvider:
        pass

    assert telemetry.ensure_content_safe_tracing(NotAnSdkProvider()) == "no_sdk_provider"

    broken, _ = provider_with_exporter()
    original = broken._active_span_processor
    broken._active_span_processor = object()  # internals we cannot reorder: must not export unscrubbed spans
    try:
        assert telemetry.ensure_content_safe_tracing(broken) == "disabled_unsafe"
    finally:
        broken._active_span_processor = original  # the provider's atexit shutdown needs the real one


# ---- end to end with the REAL Strands agent loop: names present, content absent ----

def test_real_strands_spans_carry_agent_names_and_no_message_content():
    from opentelemetry import trace

    from test_orchestrator import MID, ScriptedModel
    from navigator.agents.service import answer
    from navigator.agents.tools import ToolBox

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    try:
        trace.set_tracer_provider(provider)
    except Exception:
        pass
    active = trace.get_tracer_provider()
    if not isinstance(active, TracerProvider):
        pytest.skip("a non-SDK tracer provider is already installed in this process")
    if active is not provider:  # another test installed one first: attach our exporter to it instead
        active.add_span_processor(SimpleSpanProcessor(exporter))
    assert telemetry.install_span_scrubber(active)

    class Search:
        def search(self, *a, **k):
            raise AssertionError("not used")

    steps = [("tool", "capacity_agent", {"task": f"summarize {SECRET}"}), ("text", f"Done: {SECRET}")]
    spec = [[("text", f"Specialist reply {SECRET}")]]
    models = []

    def factory(max_tokens):
        m = ScriptedModel(steps if not models else spec.pop(0), (400, 40))
        models.append(m)
        return m

    out = answer({"prompt": f"help me {SECRET}"}, lambda meter, obs: ToolBox(None, Search(), None, meter, obs), factory, MID)
    assert SECRET in out["response"]  # the user still gets the answer; only telemetry is scrubbed
    spans = exporter.get_finished_spans()
    blob = dump(exporter)
    assert spans, "Strands emitted no spans (tracer not wired)"
    assert SECRET not in blob
    agent_names = {s.attributes.get("gen_ai.agent.name") for s in spans} - {None}
    assert {"orchestrator", "capacity"} <= agent_names
