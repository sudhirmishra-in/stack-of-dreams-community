"""The query-validation gateway: everything that must happen BEFORE the orchestrator runs, then settlement.

Order (each step can stop the request, and nothing later runs):
  1. admin kill switches / disabled user         -> 503 / 403
  2. size + sanitation of message and history     -> 400
  3. idempotent replay of a completed request     -> cached answer, no charge
  4. deterministic domain rules                   -> fixed 422 refusal (counts toward a small rejection cap)
  5. atomic quota + concurrency reservation       -> 429 / 409 / 503 (fail closed)
  6. cheap LLM classifier, ambiguous cases only   -> 422 (charged tokens, not a quota request) / 503
  7. orchestrator runtime invocation              -> 503 on failure (reservation refunded)
  8. settlement with ACTUAL usage from every model call; estimated USD tracked
"""

from __future__ import annotations

import json
import uuid
from dataclasses import replace
from typing import Any

from navigator.config import QuotaLimits, Settings
from navigator.errors import Forbidden, OutOfScope, PendingApproval, ServiceUnavailable
from navigator.logging_util import log
from navigator.ingest import metrics
from navigator.models import AgentUsage, AssistantRequest, AssistantResponse, UsageLimitView, UsageResponse
from navigator.quota.ledger import UsageLedger, next_day_reset, next_month_reset
from navigator.quota.pricing import estimate_usd

from .auth import Identity
from .classifier import ClassifierError, IntentClassifier
from .invoker import AgentInvoker, InvokerError, RuntimeResult, runtime_session_id
from .validate import REFUSAL_OUT_OF_SCOPE, clean_history, clean_message, decide


def usage_view(limit: int, used: int, resets_at: str) -> UsageLimitView:
    return UsageLimitView(limit=limit, used=used, remaining=max(0, limit - used), resetsAt=resets_at)


def build_usage(ledger: UsageLedger, sub: str, correlation_id: str, eff=None, federated: bool = False) -> UsageResponse:
    eff = eff or ledger.effective(sub)
    snap = ledger.snapshot(sub, eff.limits)
    lim = eff.limits
    return UsageResponse(
        daily=usage_view(lim.requests_per_user_day, snap.daily_requests, next_day_reset(snap.now)),
        monthly=usage_view(lim.requests_per_user_month, snap.monthly_requests, next_month_reset(snap.now)),
        tokensToday=usage_view(lim.est_tokens_per_user_day, snap.daily_tokens, next_day_reset(snap.now)),
        maxQueryChars=lim.max_query_chars,
        concurrentLimit=lim.max_concurrent_per_user,
        applicationDaily=usage_view(lim.requests_per_app_day, snap.app_daily_requests, next_day_reset(snap.now)),
        disabled=eff.disabled,
        accountStatus="disabled" if eff.disabled else ("pending" if federated and not eff.approved else "approved"),
        correlationId=correlation_id,
    )


class AssistantPipeline:
    def __init__(self, ledger: UsageLedger, invoker: AgentInvoker, classifier: IntentClassifier | None, settings: Settings,
                 research_invoker: AgentInvoker | None = None):
        self.ledger, self.invoker, self.classifier, self.settings = ledger, invoker, classifier, settings
        self.research_invoker = research_invoker  # the general assistant; None = not configured

    def handle(self, identity: Identity, req: AssistantRequest, correlation_id: str) -> AssistantResponse:
        if req.agent == "research":
            return self._handle_research(identity, req, correlation_id)
        return self._handle_navigator(identity, req, correlation_id)

    def _handle_navigator(self, identity: Identity, req: AssistantRequest, correlation_id: str) -> AssistantResponse:
        sub = identity.sub
        eff = self.ledger.effective(sub)  # 503 if the ledger is unreachable: fail closed
        if identity.federated and not eff.approved:  # defense in depth: the API layer already refuses these
            raise PendingApproval("Your account is waiting for approval.")
        if not self.settings.assistant_enabled or not eff.assistant_enabled:
            raise ServiceUnavailable("The assistant is temporarily paused.", headers={"Retry-After": "300"})
        if eff.disabled:
            raise Forbidden("Pilot access is disabled for this account.")
        limits = eff.limits

        message = clean_message(req.message, limits)
        history = clean_history(req.history, limits)

        key = req.idempotencyKey or uuid.uuid4().hex
        if req.idempotencyKey:
            cached = self.ledger.cached_response(sub, key)
            if cached:
                log("assistant_replay", correlationId=correlation_id)
                return AssistantResponse.model_validate({**json.loads(cached), "correlationId": correlation_id})

        verdict = decide(message, history)
        if verdict.decision == "reject":
            self.ledger.count_rejection(sub, limits)
            log("assistant_rejected", correlationId=correlation_id, stage="deterministic", reason=verdict.reason)
            raise OutOfScope(REFUSAL_OUT_OF_SCOPE, details={"stage": "deterministic"})

        reservation = self.ledger.reserve(sub, key, limits)  # atomic quota + concurrency, or 429/409/503
        classifier_in = classifier_out = 0
        classifier_usd = 0.0
        try:
            if verdict.decision == "ambiguous":
                if self.classifier is None:
                    raise ClassifierError("no classifier configured")
                cls = self.classifier.classify(message, limits)
                classifier_in, classifier_out = cls.input_tokens, cls.output_tokens
                classifier_usd = estimate_usd(cls.model_id, classifier_in, classifier_out) or 0.0
                if not cls.allowed:
                    # The classifier ran (tokens are real) but this is not an AI request for quota purposes.
                    self.ledger.settle(reservation, input_tokens=classifier_in, output_tokens=classifier_out,
                                       usd=classifier_usd, count_request=False)
                    self.ledger.count_rejection(sub, limits)
                    log("assistant_rejected", correlationId=correlation_id, stage="classifier")
                    raise OutOfScope(REFUSAL_OUT_OF_SCOPE, details={"stage": "classifier"})
            payload = self._payload(message, history, req, limits, correlation_id)
            result = self.invoker.invoke(payload, runtime_session_id(sub, req.sessionId), _user_key(sub), limits.request_timeout_seconds)
        except OutOfScope:
            raise
        except ClassifierError as e:
            self._safe_release(reservation, classifier_in)
            log("classifier_error", correlationId=correlation_id, error=str(e))
            raise ServiceUnavailable("We couldn't check your request right now. Please try again.", headers={"Retry-After": "5"}) from e
        except InvokerError as e:
            self._safe_release(reservation, classifier_in)
            metrics.emit("AgentInvokeFailed", 1)
            log("agent_error", correlationId=correlation_id, error=str(e))
            raise ServiceUnavailable("The assistant is unavailable right now. Please try again.", headers={"Retry-After": "10"}) from e
        except Exception:
            self._safe_release(reservation, classifier_in)
            raise

        return self._finish(sub, reservation, req, result, classifier_in, classifier_out, classifier_usd, limits, correlation_id)

    def _handle_research(self, identity: Identity, req: AssistantRequest, correlation_id: str) -> AssistantResponse:
        """The general assistant: the SAME gates as the navigator (pending approval, kill switch, disabled user, atomic
        per-user daily/monthly quota, shared pilot-wide cap, one request at a time, settle on real tokens), minus the
        community-resources topic filter, with its own per-user counters."""
        sub = identity.sub
        ledger = self.ledger.scoped("research")
        eff = self.ledger.effective(sub)
        if identity.federated and not eff.approved:
            raise PendingApproval("Your account is waiting for approval.")
        if not self.settings.assistant_enabled or not eff.assistant_enabled:
            raise ServiceUnavailable("The assistant is temporarily paused.", headers={"Retry-After": "300"})
        if eff.disabled:
            raise Forbidden("Pilot access is disabled for this account.")
        if self.research_invoker is None:
            raise ServiceUnavailable("The general assistant is not available right now.", headers={"Retry-After": "60"})
        limits = eff.limits
        text_limits = replace(limits, max_query_chars=limits.research_max_query_chars)
        message = clean_message(req.message, text_limits)
        history = clean_history(req.history, text_limits)

        key = req.idempotencyKey or uuid.uuid4().hex
        if req.idempotencyKey:
            cached = ledger.cached_response(sub, key)
            if cached:
                log("assistant_replay", correlationId=correlation_id, agent="research")
                return AssistantResponse.model_validate({**json.loads(cached), "correlationId": correlation_id})

        reservation = ledger.reserve(sub, key, limits)  # atomic quota + concurrency, or 429/409/503; nothing is spent yet
        try:
            result = self.research_invoker.invoke({"prompt": message, "history": history}, runtime_session_id(sub, "research:" + req.sessionId), _user_key(sub), limits.request_timeout_seconds)
        except InvokerError as e:
            self._safe_release(reservation, 0, ledger)
            metrics.emit("AgentInvokeFailed", 1)
            log("agent_error", correlationId=correlation_id, agent="research", error=str(e))
            raise ServiceUnavailable("The assistant is unavailable right now. Please try again.", headers={"Retry-After": "10"}) from e
        except Exception:
            self._safe_release(reservation, 0, ledger)
            raise
        return self._finish(sub, reservation, req, result, 0, 0, 0.0, limits, correlation_id, ledger=ledger, agent_id="research")

    # ---------- helpers ----------

    def _payload(self, message: str, history: list[dict[str, str]], req: AssistantRequest, limits: QuotaLimits, correlation_id: str = "") -> dict[str, Any]:
        ctx = {k: v[:40] for k, v in (req.context or {}).items() if k in ("zipCode", "resourceId") and isinstance(v, str)}
        return {
            "prompt": message,
            "history": history,
            "context": ctx,
            "correlationId": correlation_id,  # lets one request be followed from the API log into the runtime log and trace
            "limits": {
                "maxModelInvocations": limits.max_model_invocations,
                "maxToolIterations": limits.max_tool_iterations,
                "maxSpecialistCalls": limits.max_specialist_calls,
                "maxTokensPerRequest": limits.max_tokens_per_request,
                "mainMaxOutputTokens": limits.main_max_output_tokens,
                "timeoutSeconds": limits.request_timeout_seconds,
            },
        }

    def _safe_release(self, reservation, classifier_tokens: int, ledger: UsageLedger | None = None) -> None:
        try:
            (ledger or self.ledger).release(reservation)
        except Exception as e:  # conservative: leave the estimate charged rather than crash the error path
            metrics.emit("ReleaseFailed", 1)
            log("release_failed", error=type(e).__name__)

    def _finish(self, sub, reservation, req, result: RuntimeResult, c_in, c_out, c_usd, limits, correlation_id,
                ledger: UsageLedger | None = None, agent_id: str = "community-navigator") -> AssistantResponse:
        ledger = ledger or self.ledger
        usage = result.usage
        if usage is None:
            # The runtime did not report usage: charge the reservation rather than assume zero.
            in_tok, out_tok = reservation.est_tokens, 0
            usd = None
            invocations = specialists = 0
            log("usage_unreported", correlationId=correlation_id)
        else:
            in_tok = sum(m.inputTokens for m in usage.byModel) + c_in
            out_tok = sum(m.outputTokens for m in usage.byModel) + c_out
            parts = [estimate_usd(m.modelId, m.inputTokens, m.outputTokens) for m in usage.byModel]
            usd = (sum(p for p in parts if p is not None) + c_usd) if all(p is not None for p in parts) else None
            invocations, specialists = usage.modelInvocations + (1 if c_in or c_out else 0), usage.specialistCalls
            if usage.modelInvocations > limits.max_model_invocations or usage.specialistCalls > limits.max_specialist_calls:
                metrics.emit("RuntimeLimitExceeded", 1)  # the runtime should have stopped itself: alarm on this

        body = AssistantResponse(
            response=result.response,
            sessionId=req.sessionId,
            agentId=agent_id,
            citations=result.citations,
            uncertainty=result.uncertainty,
            usage=AgentUsage(inputTokens=in_tok, outputTokens=out_tok, modelInvocations=invocations, specialistCalls=specialists, estimatedUsd=usd),
            correlationId=correlation_id,
        )
        try:
            ledger.settle(
                reservation, input_tokens=in_tok, output_tokens=out_tok, usd=usd or 0.0,
                response_json=body.model_dump_json(exclude={"correlationId", "remaining"}),
            )
        except ServiceUnavailable:
            metrics.emit("SettleFailed", 1)  # work is done; the reservation stays charged (conservative)
        metrics.emit("AssistantRequests", 1)
        metrics.emit("ModelTokens", in_tok + out_tok)
        if usd is not None:
            metrics.emit("EstimatedSpendUsd", usd, unit="None")
        try:
            body.remaining = build_usage(ledger, sub, correlation_id)
        except ServiceUnavailable:
            body.remaining = None
        return body


def _user_key(sub: str) -> str:
    import hashlib

    return hashlib.sha256(sub.encode()).hexdigest()[:32]
