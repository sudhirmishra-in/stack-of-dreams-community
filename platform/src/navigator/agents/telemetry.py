"""Span hygiene for AgentCore Observability.

Strands (and the model SDK) put message CONTENT on spans: user prompts, model replies, system prompts and tool
inputs/outputs. Spans are exported to CloudWatch Logs, and the public Privacy Policy says message text is not logged. So
before any span leaves the process we strip that content (and the temporary access-key ID the AWS SDK instrumentation records)
and keep only operational telemetry: agent and tool names,
model id, token counts, durations, status and error TYPES.

`SpanScrubber` runs as the FIRST span processor (before the exporting one) and edits each finished span in place.
`install_span_scrubber` puts it first even when exporters were registered earlier, and `ensure_content_safe_tracing`
fails CLOSED: if the scrubber cannot be guaranteed, tracing is shut down rather than exported unscrubbed.
"""

from __future__ import annotations

import re
from typing import Any

from navigator.logging_util import log

try:  # the OpenTelemetry SDK ships with the Strands runtime; the API Lambda never imports this module
    from opentelemetry import trace
    from opentelemetry.sdk.trace import Event, SpanProcessor, TracerProvider
    from opentelemetry.trace import Status
except ImportError:  # pragma: no cover - only when run without the agent extras
    trace = None  # type: ignore[assignment]
    SpanProcessor = object  # type: ignore[assignment,misc]
    TracerProvider = None  # type: ignore[assignment,misc]

CONTENT_KEYS = frozenset(
    {
        "gen_ai.input.messages",
        "gen_ai.output.messages",
        "gen_ai.system_instructions",
        "gen_ai.tool.call.arguments",
        "gen_ai.tool.call.result",
        "system_prompt",
        "input.value",
        "output.value",
        "traceloop.entity.input",
        "traceloop.entity.output",
        "error.message",
    }
)
# Credential identifiers the AWS SDK instrumentation adds automatically. Not secrets, but nothing in telemetry needs them.
CREDENTIAL_KEYS = frozenset({"aws.auth.account.access_key"})
# Prefixes/segments that carry text: gen_ai.prompt.0.content, gen_ai.completion.0.content, llm.input_messages.0..., etc.
_CONTENT_PATTERN = re.compile(r"(^|\.)(prompt|completion|content|input_messages|output_messages)(\.|$)")


def is_content_attribute(key: str) -> bool:
    return key in CONTENT_KEYS or bool(_CONTENT_PATTERN.search(key))


def is_sensitive_attribute(key: str) -> bool:
    """Message content or a credential identifier: removed from every span before export."""
    return is_content_attribute(key) or key in CREDENTIAL_KEYS


def _clean_attributes(attrs: Any) -> dict[str, Any]:
    return {k: v for k, v in dict(attrs or {}).items() if not is_sensitive_attribute(k)}


class SpanScrubber(SpanProcessor):  # type: ignore[misc,valid-type]
    def on_start(self, span: Any, parent_context: Any = None) -> None:
        return None

    def on_end(self, span: Any) -> None:
        try:
            span._attributes = _clean_attributes(span.attributes)
            kept = []
            for ev in span.events:
                if ev.name.startswith("gen_ai."):
                    continue  # content-bearing events (user/system/tool messages, choices): dropped whole
                attrs = _clean_attributes(ev.attributes)
                if ev.name == "exception":  # the TYPE is useful; the message and stack can quote the prompt
                    attrs.pop("exception.message", None)
                    attrs.pop("exception.stacktrace", None)
                kept.append(Event(ev.name, attrs, ev.timestamp))
            span._events = kept
            if span.status is not None and getattr(span.status, "description", None):
                span._status = Status(span.status.status_code)  # description may carry exception text
        except Exception as e:  # never break the request path; the post-deploy canary check catches a failure here
            log("span_scrub_error", error=type(e).__name__)

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def install_span_scrubber(provider: Any = None) -> bool:
    """Make the scrubber the first processor on an SDK tracer provider. True only when it is guaranteed to run before
    any exporter; False when there is no SDK provider or its internals are not as expected."""
    if TracerProvider is None:
        return False
    provider = provider if provider is not None else trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        return False
    multi = getattr(provider, "_active_span_processor", None)
    procs = getattr(multi, "_span_processors", None)
    if procs is None:
        return False
    existing = next((p for p in procs if isinstance(p, SpanScrubber)), None)
    scrubber = existing or SpanScrubber()
    lock = getattr(multi, "_lock", None)
    rest = tuple(p for p in procs if p is not scrubber)
    if lock is not None:
        with lock:
            multi._span_processors = (scrubber, *rest)
    else:
        multi._span_processors = (scrubber, *rest)
    return True


def ensure_content_safe_tracing(provider: Any = None) -> str:
    """Called once at runtime start. Returns "scrubbing", "no_sdk_provider" (nothing is being exported) or
    "disabled_unsafe" (an exporter exists but the scrubber could not be installed, so tracing was shut down)."""
    if TracerProvider is None:
        return "no_sdk_provider"
    provider = provider if provider is not None else trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        return "no_sdk_provider"
    if install_span_scrubber(provider):
        return "scrubbing"
    try:
        provider.shutdown()
    except Exception:
        pass
    return "disabled_unsafe"


def tag_current_span(correlation_id: str, span: Any = None) -> bool:
    """Attach the API's correlation id to the active span so a Lambda log line can be matched to its trace."""
    if trace is None:
        return False
    try:
        span = span or trace.get_current_span()
        if span is None or not span.is_recording():
            return False
        span.set_attribute("correlation.id", correlation_id)
        return True
    except Exception:
        return False
