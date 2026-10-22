"""Invocation of the community-navigator AgentCore runtime, plus a local mock."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol

import boto3
from botocore.config import Config
from pydantic import BaseModel, Field, ValidationError

from navigator.gateway.invoker_text import strip_thinking
from navigator.models import Citation


class ModelUsage(BaseModel):
    modelId: str
    inputTokens: int = Field(ge=0)
    outputTokens: int = Field(ge=0)


class RuntimeUsage(BaseModel):
    modelInvocations: int = 0
    specialistCalls: int = 0
    byModel: list[ModelUsage] = Field(default_factory=list)
    # Newer runtimes also report these; an older runtime simply omits them (the defaults keep it working).
    toolCalls: int = Field(default=0, ge=0, le=1000)
    toolErrors: int = Field(default=0, ge=0, le=1000)
    specialists: dict[str, int] = Field(default_factory=dict)


class RuntimeResult(BaseModel):
    response: str
    citations: list[Citation] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    usage: RuntimeUsage | None = None  # None = runtime did not report: caller settles at the reservation


class InvokerError(Exception):
    pass


class AgentInvoker(Protocol):
    def invoke(self, payload: dict[str, Any], session_key: str, user_key: str, timeout: int) -> RuntimeResult: ...


def runtime_session_id(sub: str, session_id: str) -> str:
    """AgentCore needs 33+ chars. Hashing with the user id means one user can never join another's session."""
    return hashlib.sha256(f"{sub}:{session_id}".encode()).hexdigest()


class AgentCoreInvoker:
    def __init__(self, region: str, runtime_arn: str, client: Any = None):
        self.runtime_arn = runtime_arn
        self._client = client or boto3.client(
            "bedrock-agentcore", region_name=region, config=Config(retries={"max_attempts": 1}, connect_timeout=3, read_timeout=45)
        )

    def invoke(self, payload: dict[str, Any], session_key: str, user_key: str, timeout: int) -> RuntimeResult:
        if not self.runtime_arn:
            raise InvokerError("runtime ARN not configured")
        try:
            resp = self._client.invoke_agent_runtime(
                agentRuntimeArn=self.runtime_arn,
                runtimeSessionId=session_key,
                runtimeUserId=user_key,
                contentType="application/json",
                accept="application/json",
                payload=json.dumps(payload).encode(),
            )
            body = resp["response"].read() if hasattr(resp["response"], "read") else resp["response"]
            return RuntimeResult.model_validate(json.loads(body))
        except (ValidationError, json.JSONDecodeError) as e:
            raise InvokerError("runtime returned an unexpected response") from e
        except Exception as e:
            # Keep the AWS error code/message (never the request) so operators can see WHY in the logs.
            detail = getattr(e, "response", {}).get("Error", {}) if hasattr(e, "response") else {}
            raise InvokerError(f"{type(e).__name__}: {detail.get('Message') or e}"[:300]) from e


HARNESS_MAX_ITERATIONS = 6  # per-call cap, in addition to the limits configured on the harness itself
HARNESS_MAX_TOKENS = 8000


class HarnessInvoker:
    """The general ("research") assistant: an AgentCore *harness* (declarative agent, no custom code).

    Sends the bounded history plus the new question as messages (the harness keeps no memory of its own), enforces
    per-call caps on top of the harness's own, and returns the harness's REAL token usage from the stream metadata so
    quotas are settled on actual use."""

    def __init__(self, region: str, harness_arn: str, client: Any = None, model_id: str = "us.amazon.nova-lite-v1:0"):
        self.harness_arn, self.model_id = harness_arn, model_id  # model_id only labels usage for spend estimates
        self._client = client or boto3.client(
            "bedrock-agentcore", region_name=region, config=Config(retries={"max_attempts": 1}, connect_timeout=3, read_timeout=70)
        )

    def invoke(self, payload: dict[str, Any], session_key: str, user_key: str, timeout: int) -> RuntimeResult:
        if not self.harness_arn:
            raise InvokerError("harness ARN not configured")
        messages = [{"role": m["role"], "content": [{"text": m["content"]}]} for m in payload.get("history", [])]
        messages.append({"role": "user", "content": [{"text": str(payload["prompt"])}]})
        try:
            resp = self._client.invoke_harness(
                harnessArn=self.harness_arn,
                runtimeSessionId=session_key,
                runtimeUserId=user_key,
                messages=messages,
                maxIterations=HARNESS_MAX_ITERATIONS,
                maxTokens=HARNESS_MAX_TOKENS,
                timeoutSeconds=max(5, int(timeout)),
            )
            text, in_tok, out_tok = "", None, None
            for event in resp.get("stream") or []:
                delta = (event.get("contentBlockDelta") or {}).get("delta") or {}
                if "text" in delta:
                    text += delta["text"] or ""
                usage = (event.get("metadata") or {}).get("usage")
                if usage:
                    in_tok, out_tok = int(usage.get("inputTokens", 0)), int(usage.get("outputTokens", 0))
                if any(k in event for k in ("internalServerException", "validationException", "runtimeClientError")):
                    raise InvokerError("the agent reported an error")
        except InvokerError:
            raise
        except Exception as e:
            detail = getattr(e, "response", {}).get("Error", {}) if hasattr(e, "response") else {}
            raise InvokerError(f"{type(e).__name__}: {detail.get('Message') or e}"[:300]) from e
        answer = strip_thinking(text)
        if not answer:
            raise InvokerError("the agent returned an empty reply")
        usage_out = None
        if in_tok is not None:
            usage_out = RuntimeUsage(modelInvocations=1, byModel=[ModelUsage(modelId=self.model_id, inputTokens=in_tok, outputTokens=out_tok or 0)])
        return RuntimeResult(response=answer, usage=usage_out)


class MockInvoker:
    """MOCK_MODE: deterministic local answer. Never implies an agent ran."""

    def invoke(self, payload: dict[str, Any], session_key: str, user_key: str, timeout: int) -> RuntimeResult:
        return RuntimeResult(
            response="**Mock mode:** no AgentCore runtime was invoked. In production this answer would be grounded in "
            "directory records returned by the resource tools, with sources and uncertainty listed.",
            uncertainty=["Mock response: nothing here is real data."],
            usage=RuntimeUsage(modelInvocations=0, specialistCalls=0, byModel=[]),
        )
