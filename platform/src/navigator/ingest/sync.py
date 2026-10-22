"""Sync runner: adapters -> validate/normalize -> dedupe -> idempotent upsert, with per-source isolation.

Safety rules (each is tested):
  * One source failing never affects another.
  * Nothing is deleted. A record is only soft-deactivated after a COMPLETE full run of a source that
    enumerates everything, with no errors, and only if the run looks sane (not suspiciously empty).
  * A failed or partial run never advances the "last full sync" marker and never deactivates.
  * Re-running the same data is idempotent (stable ids; optimistic-locked upserts).
  * Overlapping runs for one source are prevented with an expiring lock.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from navigator.adapters.base import AdapterNotConfigured, SourceAdapter
from navigator.logging_util import log
from navigator.store.data_store import DataStore, VersionConflict
from navigator.util import iso, utcnow

from . import metrics
from .dedupe import merge_duplicate, merge_same_record
from .normalize import RejectedRecord, normalize

FULL_SYNC_EVERY_DAYS = 7
LOCK_SECONDS = 600
RUN_RETENTION_DAYS = 90
MAX_UPSERT_ATTEMPTS = 3
MIN_SANE_FRACTION = 0.5  # fewer than half of what we already know => do not deactivate anything


@dataclass
class SyncCounts:
    fetched: int = 0
    created: int = 0
    updated: int = 0
    merged_duplicates: int = 0
    rejected: int = 0
    errors: int = 0
    deactivated: int = 0
    activity_written: int = 0

    def as_dict(self) -> dict[str, int]:
        return self.__dict__.copy()


@dataclass
class SyncResult:
    source_id: str
    status: str  # success | partial | failed | disabled | skipped
    mode: str = "incremental"
    counts: SyncCounts = field(default_factory=SyncCounts)
    error: str | None = None
    duration_s: float = 0.0  # wall-clock seconds of this source's run (for the DataSyncDuration metric)


def _upsert(store: DataStore, rec, counts: SyncCounts) -> str:
    for _ in range(MAX_UPSERT_ATTEMPTS):
        got = store.get_resource(rec.id)
        try:
            if got:
                existing, version = got
                store.put_resource(merge_same_record(existing, rec), version)
                counts.updated += 1
                return rec.id
            dupes = [d for d in store.find_by_fingerprint(rec.fingerprint) if d != rec.id]
            if dupes:
                canon_got = store.get_resource(dupes[0])
                if canon_got:
                    canonical, version = canon_got
                    store.put_resource(merge_duplicate(canonical, rec), version)
                    counts.merged_duplicates += 1
                    return canonical.id
            store.put_resource(rec, None)
            counts.created += 1
            return rec.id
        except VersionConflict:
            continue  # someone else wrote; re-read and merge again
    raise VersionConflict(rec.id)


def _sync_source(adapter: SourceAdapter, store: DataStore, *, mode: str = "auto") -> SyncResult:
    sid = adapter.source_id
    now = utcnow()
    state = store.get_sync_state(sid)
    last_full = state.get("lastFullSyncAt")
    due_full = (
        not last_full
        or (now - _parse(last_full)).days >= FULL_SYNC_EVERY_DAYS
        or not state.get("checkpoint")
    )
    full = mode == "full" or (mode == "auto" and due_full)
    result = SyncResult(sid, "success", "full" if full else "incremental")

    if not store.acquire_sync_lock(sid, int(time.time()), LOCK_SECONDS):
        result.status = "skipped"
        result.error = "another run is in progress"
        return result

    started = iso(now)
    seen_ids: set[str] = set()
    checkpoint = state.get("checkpoint")
    completed_full_enumeration = False
    try:
        for page in adapter.fetch(None if full else checkpoint, full):
            result.counts.rejected += page.rejected
            result.counts.fetched += len(page.resources) + len(page.activities) + page.rejected
            for cand in page.resources:
                try:
                    rec = normalize(cand)
                    seen_ids.add(_upsert(store, rec, result.counts))
                except RejectedRecord:
                    result.counts.rejected += 1
                except Exception as e:  # isolate a bad record from the rest of the page
                    result.counts.errors += 1
                    log("sync_record_error", source=sid, error=type(e).__name__)
            for act in page.activities:
                try:
                    store.put_activity(act)
                    result.counts.activity_written += 1
                except Exception as e:
                    result.counts.errors += 1
                    log("sync_activity_error", source=sid, error=type(e).__name__)
            # The page is durably written: it is now safe to move the checkpoint forward.
            if page.checkpoint and result.counts.errors == 0:
                checkpoint = page.checkpoint
            if page.complete and full:
                completed_full_enumeration = True
    except AdapterNotConfigured as e:
        store.release_sync_lock(sid)
        result.status, result.error = "disabled", str(e)
        _record(store, result, state, started, now, success=False, checkpoint=state.get("checkpoint"), full_done=False)
        return result
    except Exception as e:
        result.status, result.error = "failed", f"{type(e).__name__}: {str(e)[:200]}"
        metrics.emit("SyncFailed", 1, source=sid)
        log("sync_failed", source=sid, error=type(e).__name__)
        _record(store, result, state, started, now, success=False, checkpoint=state.get("checkpoint"), full_done=False)
        store.release_sync_lock(sid)
        return result

    if result.counts.errors:
        result.status = "partial"

    # Safe deactivation: complete full enumeration, no errors, sane size. Otherwise do nothing.
    if completed_full_enumeration and result.status == "success" and adapter.supports_deactivation:
        known = list(store.iter_source_ids(sid))
        active_known = [rid for rid, active in known if active]
        sane = len(active_known) < 10 or len(seen_ids) >= MIN_SANE_FRACTION * len(active_known)
        if sane:
            for rid in active_known:
                if rid not in seen_ids:
                    _deactivate(store, rid, result.counts)
        else:
            result.status = "partial"
            result.error = "suspiciously small result; deactivation skipped"
            metrics.emit("SyncSuspicious", 1, source=sid)

    ok = result.status == "success"
    _record(
        store, result, state, started, now,
        success=ok, checkpoint=checkpoint if result.status != "failed" else state.get("checkpoint"),
        full_done=ok and completed_full_enumeration,
    )
    metrics.emit("RecordsRejected", result.counts.rejected, source=sid)
    store.release_sync_lock(sid)
    return result


def _deactivate(store: DataStore, rid: str, counts: SyncCounts) -> None:
    for _ in range(MAX_UPSERT_ATTEMPTS):
        got = store.get_resource(rid)
        if not got:
            return
        rec, version = got
        try:
            store.put_resource(rec.model_copy(update={"active": False}), version)
            counts.deactivated += 1
            return
        except VersionConflict:
            continue


def _parse(value: str):
    from navigator.util import parse_iso

    return parse_iso(value) or utcnow()


def _record(store: DataStore, r: SyncResult, prev: dict[str, Any], started: str, now, *, success: bool, checkpoint, full_done: bool) -> None:
    ended = iso()
    state = {
        "sourceId": r.source_id,
        "status": r.status,
        "mode": r.mode,
        "lastRunAt": ended,
        "lastSuccessAt": ended if success else prev.get("lastSuccessAt"),
        "lastFullSyncAt": ended if full_done else prev.get("lastFullSyncAt"),
        "checkpoint": checkpoint,
        "counts": r.counts.as_dict(),
        "error": r.error,
    }
    store.put_sync_state(r.source_id, {k: v for k, v in state.items() if v is not None})
    ttl = int(now.timestamp()) + RUN_RETENTION_DAYS * 86400
    store.put_sync_run(
        r.source_id,
        {"startedAt": started, "endedAt": ended, "status": r.status, "mode": r.mode, "counts": r.counts.as_dict(), "error": r.error},
        ttl,
    )


def sync_source(*args: Any, **kwargs: Any) -> SyncResult:
    """Runs one source and records how long it took (the result's duration_s)."""
    t0 = time.monotonic()
    result = _sync_source(*args, **kwargs)
    result.duration_s = round(time.monotonic() - t0, 2)
    return result


def sync_all(adapters: dict[str, SourceAdapter], store: DataStore, *, only: list[str] | None = None, mode: str = "auto") -> list[SyncResult]:
    results = []
    for sid, adapter in adapters.items():
        if only and sid not in only:
            continue
        try:
            results.append(sync_source(adapter, store, mode=mode))
        except Exception as e:  # last line of source isolation
            results.append(SyncResult(sid, "failed", error=f"{type(e).__name__}"))
    return results
