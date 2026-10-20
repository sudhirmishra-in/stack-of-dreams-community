"""Runtime configuration. Everything comes from environment variables; nothing is secret here."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields, replace
from typing import Any


@dataclass(frozen=True)
class QuotaLimits:
    """Pilot limits. Defaults match the pilot brief; admins can override them in DynamoDB."""

    requests_per_user_day: int = 20
    requests_per_user_month: int = 200
    max_query_chars: int = 500
    history_messages: int = 4
    main_max_output_tokens: int = 400
    classifier_max_output_tokens: int = 50
    max_specialist_calls: int = 3
    est_tokens_per_user_day: int = 30_000
    max_concurrent_per_user: int = 1
    requests_per_app_day: int = 300
    # Per-request guardrails enforced inside the agent runtime.
    max_model_invocations: int = 8
    max_tool_iterations: int = 6
    max_tokens_per_request: int = 12_000
    request_timeout_seconds: int = 25
    # What is reserved up front per request. Settled to actual usage afterwards.
    reserve_tokens_per_request: int = 3_000
    # Cheap, deterministic rejections are bounded too so they cannot be used to hammer the API.
    rejections_per_user_day: int = 60
    routes_per_user_day: int = 30
    searches_per_user_day: int = 400
    map_requests_per_user_day: int = 6000
    # Cost ceilings for the whole pilot (counted under a shared "__app__" key).
    map_requests_per_app_day: int = 30_000
    routes_per_app_day: int = 500
    # Geocoding a ZIP is a paid, storage-licensed lookup. Results are cached forever, so only misses count.
    geocodes_per_user_day: int = 25
    geocodes_per_app_day: int = 200

    @classmethod
    def with_overrides(cls, overrides: dict[str, Any] | None) -> "QuotaLimits":
        if not overrides:
            return cls()
        known = {f.name: f.type for f in fields(cls)}
        clean: dict[str, int] = {}
        for k, v in overrides.items():
            if k in known and isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0:
                clean[k] = int(v)
        return replace(cls(), **clean)


QUOTA_FIELD_NAMES = tuple(f.name for f in fields(QuotaLimits))


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    env_name: str = field(default_factory=lambda: _env("ENV_NAME", "pilot"))
    region: str = field(default_factory=lambda: _env("AWS_REGION", _env("AWS_DEFAULT_REGION", "us-east-2")))
    data_table: str = field(default_factory=lambda: _env("DATA_TABLE", "navigator-data-pilot"))
    usage_table: str = field(default_factory=lambda: _env("USAGE_TABLE", "navigator-usage-pilot"))
    cognito_user_pool_id: str = field(default_factory=lambda: _env("COGNITO_USER_POOL_ID"))
    cognito_client_id: str = field(default_factory=lambda: _env("COGNITO_CLIENT_ID"))
    admin_group: str = field(default_factory=lambda: _env("ADMIN_GROUP", "pilot-admin"))
    allowed_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(o.strip() for o in _env("ALLOWED_ORIGINS").split(",") if o.strip())
    )
    agent_runtime_arn: str = field(default_factory=lambda: _env("AGENT_RUNTIME_ARN"))
    agent_region: str = field(default_factory=lambda: _env("AGENT_REGION", _env("AWS_REGION", "us-east-2")))
    classifier_model_id: str = field(default_factory=lambda: _env("CLASSIFIER_MODEL_ID", "us.amazon.nova-micro-v1:0"))
    orchestrator_model_id: str = field(default_factory=lambda: _env("ORCHESTRATOR_MODEL_ID", "us.amazon.nova-lite-v1:0"))
    # Master switches. The assistant kill switch also exists in DynamoDB (admin-controlled).
    assistant_enabled: bool = field(default_factory=lambda: _env("ASSISTANT_ENABLED", "true").lower() == "true")
    mock_mode: bool = field(default_factory=lambda: _env("MOCK_MODE", "false").lower() == "true")
    seed_demo_enabled: bool = field(default_factory=lambda: _env("SEED_DEMO", "true").lower() == "true")
    osm_enabled: bool = field(default_factory=lambda: _env("SOURCE_OSM_ENABLED", "true").lower() == "true")
    nyc_cfc_enabled: bool = field(default_factory=lambda: _env("SOURCE_NYC_CFC_ENABLED", "true").lower() == "true")
    twoone_one_enabled: bool = field(default_factory=lambda: _env("SOURCE_211_ENABLED", "false").lower() == "true")
    twoone_one_api_key_param: str = field(default_factory=lambda: _env("SOURCE_211_API_KEY_PARAM"))
    overpass_url: str = field(default_factory=lambda: _env("OVERPASS_URL", "https://overpass-api.de/api/interpreter"))
    contact_for_user_agent: str = field(default_factory=lambda: _env("INGEST_CONTACT", "pilot@example.invalid"))
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO"))
    # Stale-data thresholds (days) used when labeling freshness.
    stale_after_days: int = field(default_factory=lambda: int(_env("STALE_AFTER_DAYS", "45")))


def get_settings() -> Settings:
    return Settings()
