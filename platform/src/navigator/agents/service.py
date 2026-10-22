"""Turns one validated payload into a grounded, structured answer. Used by the AgentCore entrypoint."""

from __future__ import annotations

import re
from typing import Any, Callable

from navigator.logging_util import log

from navigator.gateway.invoker_text import strip_thinking

from .meter import UsageMeter, clamp_limits
from .orchestrator import ModelFactory, _usage_of, build_orchestrator
from .safety import Observed, guard_response, untrusted
from .tools import ToolBox

LIMIT_MESSAGE = "I reached my per-request processing limit, so this answer may be incomplete."
FAILURE_MESSAGE = "I couldn't finish looking that up. Please try again in a moment."
# The hooks cancel calls with "Stopped: <reason> reached."; a model sometimes repeats that as its whole reply.
_BARE_STOP = re.compile(r"^\s*Stopped: [\w -]+ reached\.?\s*$", re.I)
FALLBACK_LIST_MAX = 5


def fallback_answer(observed: Observed) -> str | None:
    """A plain, tool-grounded list of the providers already retrieved, for when the model produced no usable text."""
    rows = [r for r in observed.resources.values() if r.get("name")][:FALLBACK_LIST_MAX]
    if not rows:
        return None
    lines = []
    for i, r in enumerate(rows, 1):
        detail = ", ".join(x for x in (r.get("address"), f"{r['distanceMiles']} miles away" if r.get("distanceMiles") is not None else None) if x)
        lines.append(f"{i}. {r['name']}" + (f" ({detail})" if detail else "") + (" [demo data]" if r["isDemoData"] else ""))
    return "Here is what I found (the full answer could not be completed):\n" + "\n".join(lines) + "\nPlease confirm availability with the provider before traveling."


def build_prompt(prompt: str, history: list[dict[str, str]], context: dict[str, str]) -> str:
    parts = []
    if history:
        lines = "\n".join(f"{h['role']}: {untrusted(h['content'], 500)}" for h in history[-4:])
        parts.append(f"<earlier_conversation untrusted='true'>\n{lines}\n</earlier_conversation>")
    if context:
        parts.append("<context>" + ", ".join(f"{k}={untrusted(v, 40)}" for k, v in context.items()) + "</context>")
    parts.append(f"<question>{untrusted(prompt, 500)}</question>")
    return "\n".join(parts)


def build_uncertainty(observed: Observed, meter: UsageMeter, guard_notes: list[str]) -> list[str]:
    u: list[str] = []
    if observed.tool_calls == 0:
        u.append("Not grounded in retrieved data: no directory lookup was performed for this answer.")
    if any(r["isDemoData"] for r in observed.resources.values()):
        u.append("Some results are DEMO DATA (fictional sample records), not real inventory.")
    real = [r for r in observed.resources.values() if not r["isDemoData"]]
    if real:
        u.append("Real directory records are community-sourced and unverified; they do not include inventory. Confirm with the provider before traveling.")
        if any(r["freshness"] != "fresh" for r in real):
            u.append("Some provider records are stale or of unknown freshness.")
    if observed.activity_used:
        u.append("Service activity figures are historical citywide counts, not capacity or inventory.")
    if meter.tripped:
        u.append(LIMIT_MESSAGE)
    u.extend(f"Safety check: {n}." for n in guard_notes)
    return u


def answer(payload: dict[str, Any], box_factory: Callable[[UsageMeter, Observed], ToolBox], model_factory: ModelFactory, model_id: str, agent_cls: type | None = None) -> dict[str, Any]:
    limits = clamp_limits(payload.get("limits"))
    meter, observed = UsageMeter(limits), Observed()
    box = box_factory(meter, observed)
    kwargs = {"agent_cls": agent_cls} if agent_cls else {}
    text = FAILURE_MESSAGE
    try:
        agent = build_orchestrator(box, meter, model_factory, model_id, **kwargs)
        result = agent(build_prompt(str(payload.get("prompt", "")), payload.get("history") or [], payload.get("context") or {}))
        meter.add_usage(model_id, *_usage_of(result))
        text = str(result).strip() or FAILURE_MESSAGE
    except Exception as e:
        log("orchestrator_error", error=type(e).__name__, tripped=meter.tripped)
        if meter.tripped:
            text = LIMIT_MESSAGE
        try:  # tokens spent before the failure still count
            meter.add_usage(model_id, *_usage_of(agent))  # type: ignore[name-defined]
        except Exception:
            pass
    # Some models emit their scratch reasoning inline; it is not part of the answer.
    text = strip_thinking(text)
    if not text or text == FAILURE_MESSAGE or _BARE_STOP.match(text):
        text = fallback_answer(observed) or (LIMIT_MESSAGE if meter.tripped else FAILURE_MESSAGE)
    safe, notes = guard_response(text, observed)
    citations = [
        {"sourceId": r["sourceId"], "resourceId": rid, "isDemoData": r["isDemoData"], "verification": r["verification"], "freshness": r["freshness"]}
        for rid, r in observed.resources.items()
    ]
    return {"response": safe, "citations": citations, "uncertainty": build_uncertainty(observed, meter, notes), "usage": {**meter.usage_payload(), "toolCalls": observed.tool_calls, "toolErrors": observed.tool_errors}}
