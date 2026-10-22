"""Hourly data-freshness reporter: emits DataSyncAge (hours since each source's last SUCCESSFUL sync).

It exists because the ingest Lambda cannot report that it has stopped running: only a separate, regularly scheduled
function can notice a silent gap. Read-only: it reads the sync state records and writes nothing. A source with no recorded
success gets no age (never an invented one) and is listed as unknown in the logs."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Callable

from navigator.config import get_settings
from navigator.logging_util import log
from navigator.store.data_store import DataStore

from . import appmetrics

MONITORED_SOURCES = ("osm", "nyc-cfc")  # 211 is disabled until authorized


def _parse(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def make_handler(store: Any, clock: Callable[[], datetime] | None = None):
    def handler(event: dict[str, Any] | None = None, context: Any = None) -> dict[str, Any]:
        now = clock() if clock else datetime.now(timezone.utc)
        emitted, unknown = 0, []
        for sid in MONITORED_SOURCES:
            state = store.get_sync_state(sid)  # a store failure propagates: the Lambda errors and its alarm fires
            ts = state.get("lastSuccessAt") if state else None
            try:
                age_h = round((now - _parse(ts)).total_seconds() / 3600, 1) if ts else None
            except (ValueError, TypeError):
                age_h = None
            if age_h is None:
                unknown.append(sid)
                continue
            if appmetrics.emit({"DataSyncAge": max(0.0, age_h)}, Source=sid):
                emitted += 1
        log("freshness_checked", emitted=emitted, unknown=unknown)
        return {"emitted": emitted, "unknown": unknown}

    return handler


def handler(event: dict[str, Any] | None = None, context: Any = None) -> dict[str, Any]:
    s = get_settings()
    return make_handler(DataStore(s.data_table, s.region))(event, context)
