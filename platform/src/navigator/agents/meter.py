"""Per-request usage meter: counts every model invocation and token across the orchestrator AND specialists,
and enforces the hard per-request limits the gateway passed in (clamped to absolute caps here)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

# Absolute ceilings. A caller-supplied limit can lower these but never raise them.
HARD_MAX = {"maxModelInvocations": 12, "maxToolIterations": 10, "maxSpecialistCalls": 4, "maxTokensPerRequest": 20_000, "mainMaxOutputTokens": 600, "timeoutSeconds": 40}
DEFAULTS = {"maxModelInvocations": 8, "maxToolIterations": 6, "maxSpecialistCalls": 3, "maxTokensPerRequest": 12_000, "mainMaxOutputTokens": 600, "timeoutSeconds": 25}


class LimitExceeded(Exception):
    pass


def clamp_limits(requested: dict[str, Any] | None) -> dict[str, int]:
    out = {}
    for k, hard in HARD_MAX.items():
        v = (requested or {}).get(k, DEFAULTS[k])
        out[k] = max(1, min(int(v), hard)) if isinstance(v, (int, float)) and not isinstance(v, bool) else DEFAULTS[k]
    return out


@dataclass
class UsageMeter:
    limits: dict[str, int]
    started: float = field(default_factory=time.monotonic)
    by_model: dict[str, list[int]] = field(default_factory=dict)
    model_invocations: int = 0
    specialist_calls: int = 0
    tool_calls: int = 0
    tripped: str | None = None
    _inflight_tokens: int = 0

    @property
    def deadline_passed(self) -> bool:
        return time.monotonic() - self.started > self.limits["timeoutSeconds"]

    def total_tokens(self) -> int:
        return sum(i + o for i, o in self.by_model.values())

    def add_usage(self, model_id: str, input_tokens: int, output_tokens: int) -> None:
        cur = self.by_model.setdefault(model_id, [0, 0])
        cur[0] += int(input_tokens)
        cur[1] += int(output_tokens)

    def set_inflight(self, tokens: int) -> None:
        self._inflight_tokens = tokens

    def block_model_call(self, projected_input: int = 0) -> str | None:
        """Called BEFORE each model call. Returns a reason to cancel it, or None."""
        if self.tripped:
            return self.tripped
        reason = None
        if self.model_invocations >= self.limits["maxModelInvocations"]:
            reason = "model invocation limit"
        elif self.deadline_passed:
            reason = "time limit"
        elif self.total_tokens() + self._inflight_tokens + projected_input > self.limits["maxTokensPerRequest"]:
            reason = "token limit"
        if reason:
            self.tripped = reason
            return reason
        self.model_invocations += 1
        return None

    def block_tool_call(self) -> str | None:
        if self.tool_calls >= self.limits["maxToolIterations"]:
            self.tripped = self.tripped or "tool call limit"
            return "tool call limit"
        self.tool_calls += 1
        return None

    def take_specialist(self) -> None:
        if self.specialist_calls >= self.limits["maxSpecialistCalls"]:
            raise LimitExceeded("specialist call limit reached")
        self.specialist_calls += 1

    def usage_payload(self) -> dict[str, Any]:
        return {
            "modelInvocations": self.model_invocations,
            "specialistCalls": self.specialist_calls,
            "byModel": [{"modelId": m, "inputTokens": i, "outputTokens": o} for m, (i, o) in self.by_model.items()],
        }
