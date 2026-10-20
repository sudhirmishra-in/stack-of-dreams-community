"""Ingestion Lambda: invoked by EventBridge Scheduler (or manually) -> sync enabled sources."""

from __future__ import annotations

import os
from typing import Any

from navigator.adapters.fixtures import FixtureHttp
from navigator.adapters.registry import build_adapters
from navigator.config import get_settings
from navigator.logging_util import log
from navigator.store.data_store import DataStore

from .demo import seed_demo
from .sync import sync_all


def handler(event: dict[str, Any] | None, context: Any = None) -> dict[str, Any]:
    event = event or {}
    s = get_settings()
    store = DataStore(s.data_table, s.region)
    http = FixtureHttp(os.environ["FIXTURE_DIR"]) if os.environ.get("FIXTURE_MODE") == "true" else None
    adapters = build_adapters(s, http)  # type: ignore[arg-type]
    mode = event.get("mode", "auto")
    if mode not in ("auto", "full", "incremental"):
        mode = "auto"
    only = [x for x in event.get("sources", []) if isinstance(x, str)] or None
    results = sync_all(adapters, store, only=only, mode=mode)
    seeded = seed_demo(store) if (s.seed_demo_enabled and event.get("seedDemo", True)) else 0
    summary = [{"source": r.source_id, "status": r.status, "mode": r.mode, "counts": r.counts.as_dict(), "error": r.error} for r in results]
    log("sync_complete", results=summary, demoSeeded=seeded)
    return {"results": summary, "demoSeeded": seeded}
