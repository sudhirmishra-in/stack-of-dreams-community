"""Invocation of the community-navigator AgentCore runtime, plus a local mock."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol

import boto3
from botocore.config import Config
from pydantic import BaseModel, Field, ValidationError

from navigator.models import Citation


class ModelUsage(BaseModel):
    modelId: str
    inputTokens: int = Field(ge=0)
    outputTokens: int = Field(ge=0)


class RuntimeUsage(BaseModel):
    modelInvocations: int = 0
    specialistCalls: int = 0
    byModel: list[ModelUsage] = Field(default_factory=list)


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


class MockInvoker:
    """MOCK_MODE: deterministic local answer. Never implies an agent ran."""

    def invoke(self, payload: dict[str, Any], session_key: str, user_key: str, timeout: int) -> RuntimeResult:
        return RuntimeResult(
            response="**Mock mode:** no AgentCore runtime was invoked. In production this answer would be grounded in "
            "directory records returned by the resource tools, with sources and uncertainty listed.",
            uncertainty=["Mock response: nothing here is real data."],
            usage=RuntimeUsage(modelInvocations=0, specialistCalls=0, byModel=[]),
        )
