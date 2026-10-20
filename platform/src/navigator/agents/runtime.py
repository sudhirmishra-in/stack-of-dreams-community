"""AgentCore Runtime entrypoint for `community-navigator`. Deployed with the AgentCore CLI (see ../../agentcore).

The runtime role is READ-ONLY on the data table and has no write access to the usage ledger: quota
enforcement happens in the gateway before this code runs, and the runtime only reports what it used.
"""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from navigator.config import Settings
from navigator.location.client import CachedZipGeocoder, LocationClient
from navigator.search.service import SearchService
from navigator.store.data_store import DataStore

from .service import answer
from .tools import ToolBox

MODEL_ID = os.environ.get("ORCHESTRATOR_MODEL_ID", "us.amazon.nova-lite-v1:0")


class Payload(BaseModel):
    prompt: str = Field(min_length=1, max_length=600)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=6)
    context: dict[str, str] = Field(default_factory=dict)
    limits: dict[str, Any] = Field(default_factory=dict)


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


def run(raw: dict[str, Any]) -> dict[str, Any]:
    try:
        p = Payload.model_validate(raw)
    except ValidationError:
        return {"response": "Invalid request.", "citations": [], "uncertainty": ["Request payload was invalid."], "usage": {"modelInvocations": 0, "specialistCalls": 0, "byModel": []}}
    store, search, location = _components()
    return answer(p.model_dump(), lambda meter, obs: ToolBox(store, search, location, meter, obs), model_factory, MODEL_ID)


def create_app():
    from bedrock_agentcore.runtime import BedrockAgentCoreApp

    app = BedrockAgentCoreApp()

    @app.entrypoint
    def invoke(payload: dict[str, Any], context: Any = None) -> dict[str, Any]:
        return run(payload)

    return app


if __name__ == "__main__":  # `agentcore dev` / container entry
    create_app().run()
