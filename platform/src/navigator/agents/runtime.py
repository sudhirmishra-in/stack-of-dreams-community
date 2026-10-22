"""AgentCore Runtime entrypoint for `community-navigator`. Deployed with the AgentCore CLI (see ../../agentcore).

The runtime role is READ-ONLY on the data table and has no write access to the usage ledger: quota
enforcement happens in the gateway before this code runs, and the runtime only reports what it used.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from navigator.config import Settings
from navigator.logging_util import log
from navigator.location.client import CachedZipGeocoder, LocationClient
from navigator.search.service import SearchService
from navigator.store.data_store import DataStore

from .service import answer
from .telemetry import ensure_content_safe_tracing, tag_current_span
from .tools import ToolBox

MODEL_ID = os.environ.get("ORCHESTRATOR_MODEL_ID", "us.amazon.nova-lite-v1:0")


class Payload(BaseModel):
    prompt: str = Field(min_length=1, max_length=600)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=6)
    context: dict[str, str] = Field(default_factory=dict)
    limits: dict[str, Any] = Field(default_factory=dict)
    correlationId: Any = None  # from the API; validated by hand so a bad value can never reject a request


_COMPONENTS: dict[str, Any] = {}


def _components() -> tuple[DataStore, SearchService, LocationClient | None]:
    if not _COMPONENTS:
        s = Settings()
        store = DataStore(s.data_table, s.region)
        location = LocationClient(s.region)
        _COMPONENTS.update(store=store, search=SearchService(store, CachedZipGeocoder(store, location), s), location=location)
    return _COMPONENTS["store"], _COMPONENTS["search"], _COMPONENTS["location"]


def model_factory(max_tokens: int):
    from strands.models import BedrockModel

    return BedrockModel(model_id=MODEL_ID, max_tokens=max_tokens, temperature=0.2, region_name=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION", "us-east-2"))


_CORRELATION_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def _correlation_id(value: Any) -> str | None:
    return value if isinstance(value, str) and _CORRELATION_ID.match(value) else None


def run(raw: dict[str, Any]) -> dict[str, Any]:
    try:
        p = Payload.model_validate(raw)
    except ValidationError:
        return {"response": "Invalid request.", "citations": [], "uncertainty": ["Request payload was invalid."], "usage": {"modelInvocations": 0, "specialistCalls": 0, "byModel": []}}
    cid = _correlation_id(p.correlationId)
    if cid:
        tag_current_span(cid)
    started = time.monotonic()
    store, search, location = _components()
    try:
        result = answer(p.model_dump(), lambda meter, obs: ToolBox(store, search, location, meter, obs), model_factory, MODEL_ID)
    except Exception as e:
        _log_invocation(cid, "error", started, None, type(e).__name__)
        raise
    _log_invocation(cid, "ok", started, result.get("usage"), None)
    return result


def _log_invocation(cid: str | None, status: str, started: float, usage: dict[str, Any] | None, error_type: str | None) -> None:
    """One structured line per invocation. Never contains the prompt, the answer or any user identifier."""
    by_model = (usage or {}).get("byModel") or []
    log(
        "agent_invocation",
        service="community-navigator-runtime",
        environment=os.environ.get("ENV_NAME", "pilot"),
        agentName="orchestrator",
        correlationId=cid,
        status=status,
        errorType=error_type,
        durationMs=int((time.monotonic() - started) * 1000),
        modelId=MODEL_ID,
        modelInvocations=(usage or {}).get("modelInvocations"),
        specialistCalls=(usage or {}).get("specialistCalls"),
        inputTokens=sum(m.get("inputTokens", 0) for m in by_model) if usage else None,
        outputTokens=sum(m.get("outputTokens", 0) for m in by_model) if usage else None,
    )


def create_app():
    from bedrock_agentcore.runtime import BedrockAgentCoreApp

    # Spans must never carry prompts or tool payloads: scrub before export (or shut tracing down if that cannot be guaranteed).
    log("tracing_content_safety", status=ensure_content_safe_tracing())
    app = BedrockAgentCoreApp()

    @app.entrypoint
    def invoke(payload: dict[str, Any], context: Any = None) -> dict[str, Any]:
        return run(payload)

    return app


if __name__ == "__main__":  # `agentcore dev` / container entry
    create_app().run()
