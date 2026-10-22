"""Request-level metrics for the assistants (CommunityNavigator namespace). Called from ONE place per outcome so nothing is
counted twice: the pipeline's success path, its agent-failure path, and the API's single error handler.

Tokens and costs come only from usage the agent actually reported. If usage is missing, `UsageUnreported` is counted
instead and no token or cost value is invented; a model without a price emits `ModelCostUnavailable`, not a guessed cost."""

from __future__ import annotations

from typing import Any

from navigator.ingest import appmetrics
from navigator.quota.pricing import estimate_usd

TOP_LEVEL_AGENT = {"navigator": "orchestrator", "research": "research"}


def emit_failure(agent_type: str) -> None:
    """The agent was invoked and failed (timeout, runtime or harness error). No usage is known, so no tokens or cost."""
    appmetrics.emit({"AgentInvocations": 1}, AgentType=agent_type, AgentName=TOP_LEVEL_AGENT[agent_type])
    appmetrics.emit({"AgentErrors": 1}, AgentType=agent_type)


def emit_success(
    agent_type: str,
    *,
    usage: Any,
    latency_ms: int,
    classifier_model: str | None = None,
    classifier_tokens: tuple[int, int] = (0, 0),
    model_invocations: int | None = None,
) -> None:
    top = TOP_LEVEL_AGENT[agent_type]
    appmetrics.emit({"AgentInvocations": 1}, AgentType=agent_type, AgentName=top)
    for name, count in sorted((getattr(usage, "specialists", None) or {}).items()):
        if isinstance(count, int) and count > 0:
            appmetrics.emit({"AgentInvocations": count}, AgentType=agent_type, AgentName=name)  # unknown names are bucketed as "other"
    appmetrics.emit({"AgentLatency": max(0, int(latency_ms))}, AgentType=agent_type)

    if usage is None:
        appmetrics.emit({"UsageUnreported": 1}, AgentType=agent_type)
        return
    appmetrics.emit({"ModelInvocations": model_invocations if model_invocations is not None else usage.modelInvocations}, AgentType=agent_type)
    if getattr(usage, "toolCalls", 0):
        appmetrics.emit({"ToolInvocations": usage.toolCalls}, AgentType=agent_type)
    if getattr(usage, "toolErrors", 0):
        appmetrics.emit({"ToolErrors": usage.toolErrors}, AgentType=agent_type)

    per_model: dict[str, list[int]] = {}
    for m in usage.byModel:
        cur = per_model.setdefault(m.modelId, [0, 0])
        cur[0] += m.inputTokens
        cur[1] += m.outputTokens
    if classifier_model and any(classifier_tokens):
        cur = per_model.setdefault(classifier_model, [0, 0])
        cur[0] += classifier_tokens[0]
        cur[1] += classifier_tokens[1]
    unavailable = False
    for model_id, (tok_in, tok_out) in sorted(per_model.items()):
        appmetrics.emit({"ModelInputTokens": tok_in, "ModelOutputTokens": tok_out}, AgentType=agent_type, ModelId=model_id)
        cost = estimate_usd(model_id, tok_in, tok_out)
        if cost is None:
            unavailable = True
        else:
            appmetrics.emit({"EstimatedModelCost": cost}, AgentType=agent_type, ModelId=model_id)
    if unavailable:
        appmetrics.emit({"ModelCostUnavailable": 1}, AgentType=agent_type)
