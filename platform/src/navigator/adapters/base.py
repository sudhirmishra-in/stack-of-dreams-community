"""Adapter contract. Adapters fetch and map raw source data into candidates; they never write to the store."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Protocol

from navigator.models import ActivityRecord, FacilityKind, ResourceType, SourceRef


class AdapterNotConfigured(Exception):
    """The source is disabled or lacks the credentials/authorization it needs."""


@dataclass
class ResourceCandidate:
    source_id: str
    source_record_id: str
    name: str | None
    zip_code: str | None = None
    city: str | None = None
    borough: str | None = None
    address: str | None = None
    phone: str | None = None
    website: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    resource_types: list[ResourceType] = field(default_factory=lambda: ["food_assistance"])
    facility_kind: FacilityKind = "other"
    hours: str | None = None
    operating_days: list[str] = field(default_factory=list)
    eligibility: str | None = None
    ref: SourceRef | None = None


@dataclass
class Page:
    resources: list[ResourceCandidate] = field(default_factory=list)
    activities: list[ActivityRecord] = field(default_factory=list)
    #: Opaque position to persist after this page is *durably written* (incremental sync).
    checkpoint: str | None = None
    #: Count of raw rows the adapter could not map (reported in sync status).
    rejected: int = 0
    #: True on the final page of a full, successful enumeration.
    complete: bool = False


class SourceAdapter(Protocol):
    source_id: str
    #: True if a complete run enumerates the entire source, so absent records may be deactivated.
    supports_deactivation: bool

    def fetch(self, checkpoint: str | None, full: bool) -> Iterator[Page]: ...
