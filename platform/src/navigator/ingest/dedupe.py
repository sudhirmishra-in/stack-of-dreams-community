"""Merging an incoming record into what we already store."""

from __future__ import annotations

from navigator.models import ResourceRecord, SourceRef

_FILLABLE = ("city", "borough", "zipCode", "address", "phone", "website", "latitude", "longitude", "hours", "eligibility")


def _merge_sources(existing: list[SourceRef], incoming: list[SourceRef]) -> list[SourceRef]:
    by_key = {(s.sourceId, s.sourceRecordId): s for s in existing}
    for s in incoming:
        old = by_key.get((s.sourceId, s.sourceRecordId))
        if old is not None:
            # A human/partner verification timestamp is never erased by an automated re-sync.
            s = s.model_copy(update={"lastVerifiedAt": old.lastVerifiedAt})
        by_key[(s.sourceId, s.sourceRecordId)] = s
    return list(by_key.values())


def merge_same_record(existing: ResourceRecord, incoming: ResourceRecord) -> ResourceRecord:
    """Same source record seen again: the source is authoritative for its own fields."""
    sources = _merge_sources(existing.sources, incoming.sources)
    verified = existing.verification == "verified" and any(s.lastVerifiedAt for s in sources)
    return incoming.model_copy(
        update={"sources": sources, "verification": "verified" if verified else "unverified", "active": True}
    )


def merge_duplicate(canonical: ResourceRecord, incoming: ResourceRecord) -> ResourceRecord:
    """A different source describes the same place: keep the canonical record, add provenance, fill gaps only."""
    updates: dict[str, object] = {"sources": _merge_sources(canonical.sources, incoming.sources), "active": True}
    for f in _FILLABLE:
        if getattr(canonical, f) is None and getattr(incoming, f) is not None:
            updates[f] = getattr(incoming, f)
    types = list(dict.fromkeys([*canonical.resourceTypes, *incoming.resourceTypes]))
    updates["resourceTypes"] = types
    return canonical.model_copy(update=updates)
