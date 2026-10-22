"""Per-source sync metrics in the CommunityNavigator namespace, emitted once per run by the ingest handler.
Skipped and disabled runs did nothing and emit nothing; a failed run writes no record counts."""

from __future__ import annotations

from navigator.ingest import appmetrics
from navigator.ingest.sync import SyncResult


def emit_sync_metrics(result: SyncResult) -> None:
    if result.status in ("skipped", "disabled"):
        return
    failed = result.status == "failed"
    values: dict[str, float] = {
        "DataSyncSuccess": 1 if result.status == "success" else 0,
        "DataSyncFailures": 1 if result.status in ("failed", "partial") else 0,
        "DataSyncDuration": result.duration_s,
        "SourceApiErrors": 1 if failed and (result.error or "").startswith("HttpError") else 0,
    }
    if not failed:
        values.update(
            RecordsInserted=result.counts.created,
            RecordsUpdated=result.counts.updated,
            RecordsRejected=result.counts.rejected,
        )
    appmetrics.emit(values, Source=result.source_id)
