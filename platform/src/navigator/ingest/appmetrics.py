"""Application metrics in the CommunityNavigator namespace (CloudWatch Embedded Metric Format on stdout).

Design rules (each is enforced here and tested):
 * Only metric names listed in UNITS may be emitted, so a typo cannot create a new billable series.
 * Dimensions are a fixed, low-cardinality set. Identifiers (user, session, request, trace, email) are refused outright:
   they would both explode cost and expose pilot identities in shared dashboards.
 * Dimension VALUES come from known sets (or a model-id pattern); anything else is bucketed as "other".
 * Values must be finite and non-negative; invalid values are dropped, never guessed.
 * emit() never raises into the request path.
The pre-existing `Navigator` namespace (ingest/metrics.py) is unchanged and independent.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from typing import Any

from navigator.logging_util import log

DEFAULT_NAMESPACE = "CommunityNavigator/Production"

UNITS: dict[str, str] = {
    "AgentInvocations": "Count",
    "ModelInvocations": "Count",
    "AgentErrors": "Count",
    "AgentLatency": "Milliseconds",
    "ModelInputTokens": "Count",
    "ModelOutputTokens": "Count",
    "EstimatedModelCost": "None",  # estimated USD; the name says "Estimated" on purpose
    "ModelCostUnavailable": "Count",
    "UsageUnreported": "Count",
    "ToolInvocations": "Count",
    "ToolErrors": "Count",
    "QuotaRejections": "Count",
    "AuthenticationFailures": "Count",
    "ResourceSearches": "Count",
    "ResourceSearchNoResults": "Count",
    "DataSyncSuccess": "Count",
    "DataSyncFailures": "Count",
    "DataSyncAge": "Hours",
    "DataSyncDuration": "Seconds",
    "RecordsInserted": "Count",
    "RecordsUpdated": "Count",
    "RecordsRejected": "Count",
    "SourceApiErrors": "Count",
}

# Environment is added automatically; callers may pass only these.
ALLOWED_DIMENSIONS = frozenset({"AgentType", "AgentName", "ModelId", "Reason", "Source"})

KNOWN_VALUES: dict[str, frozenset[str]] = {
    "AgentType": frozenset({"navigator", "research"}),
    "AgentName": frozenset({"orchestrator", "resource_discovery", "inventory", "capacity", "location", "research"}),
    "Reason": frozenset(
        {
            "daily_requests", "monthly_requests", "daily_tokens", "application_daily", "concurrent_request", "duplicate_request",
            "search", "routes", "map", "geocode", "rejections", "unauthorized", "pending_approval", "forbidden",
        }
    ),
    "Source": frozenset({"osm", "nyc-cfc", "211"}),
}
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,79}$")
_ENV = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
OTHER = "other"


def namespace() -> str:
    ns = os.environ.get("METRICS_NAMESPACE", "").strip()
    return ns if re.fullmatch(r"[A-Za-z0-9_./#:-]{1,255}", ns) else DEFAULT_NAMESPACE


def environment() -> str:
    env = os.environ.get("ENV_NAME", "pilot")
    return env if _ENV.match(env) else OTHER


def _clean_value(dim: str, value: Any) -> str:
    v = str(value)
    if dim == "ModelId":
        return v if _MODEL_ID.match(v) else OTHER
    return v if v in KNOWN_VALUES[dim] else OTHER


def emit(metrics: dict[str, Any], **dimensions: Any) -> bool:
    """Print one EMF record holding every metric in `metrics` under one dimension set. True if something was written."""
    try:
        bad = sorted(set(dimensions) - ALLOWED_DIMENSIONS)
        if bad:
            log("metric_dimension_rejected", dimensions=bad)  # names only, never values
            return False
        clean: dict[str, float] = {}
        for name, value in metrics.items():
            if name not in UNITS:
                log("metric_name_rejected", metric=name if isinstance(name, str) and len(name) < 64 else "?")
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                continue
            clean[name] = value
        if not clean:
            return False
        dims = {"Environment": environment(), **{k: _clean_value(k, v) for k, v in dimensions.items()}}
        record: dict[str, Any] = {
            "_aws": {
                "Timestamp": int(time.time() * 1000),
                "CloudWatchMetrics": [
                    {"Namespace": namespace(), "Dimensions": [list(dims)], "Metrics": [{"Name": n, "Unit": UNITS[n]} for n in clean]}
                ],
            },
            **dims,
            **clean,
        }
        print(json.dumps(record))
        return True
    except Exception:
        return False
