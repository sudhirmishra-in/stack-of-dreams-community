"""Validation and normalization: candidate (what an adapter found) -> ResourceRecord (what we store)."""

from __future__ import annotations

import re

from navigator.adapters.base import ResourceCandidate
from navigator.models import RESOURCE_TYPES, ResourceRecord, SourceRef
from navigator.util import fingerprint, resource_id, valid_coordinates

_ZIP = re.compile(r"^\d{5}$")
_PHONE_OK = re.compile(r"^[\d\s().+\-ext]{7,30}$", re.I)


class RejectedRecord(ValueError):
    pass


def _text(value: str | None, limit: int) -> str | None:
    if not value:
        return None
    v = " ".join(value.split())
    return v[:limit] or None


def normalize(c: ResourceCandidate, *, namespace: str = "real", demo: bool = False) -> ResourceRecord:
    name = _text(c.name, 120)
    if not name:
        raise RejectedRecord("missing name")
    if not c.source_record_id or not c.source_id:
        raise RejectedRecord("missing source identity")
    zip_code = c.zip_code if c.zip_code and _ZIP.match(c.zip_code) else None
    lat, lon = (c.latitude, c.longitude) if valid_coordinates(c.latitude, c.longitude) else (None, None)
    if zip_code is None and lat is None:
        raise RejectedRecord("no ZIP code and no valid coordinates: cannot be located")
    phone = _text(c.phone, 40)
    if phone and not _PHONE_OK.match(phone):
        phone = None  # never display something that does not look like a phone number
    website = c.website if c.website and re.match(r"^https?://", c.website, re.I) else None
    types = [t for t in dict.fromkeys(c.resource_types) if t in RESOURCE_TYPES] or ["food_assistance"]
    ref = c.ref or SourceRef(sourceId=c.source_id, sourceRecordId=c.source_record_id)
    return ResourceRecord(
        id=resource_id(c.source_id, c.source_record_id),
        namespace=namespace,  # type: ignore[arg-type]
        name=name,
        city=_text(c.city, 60),
        borough=_text(c.borough, 40),
        zipCode=zip_code,
        address=_text(c.address, 160),
        phone=phone,
        website=website,
        latitude=lat,
        longitude=lon,
        resourceTypes=types,  # type: ignore[arg-type]
        facilityKind=c.facility_kind,
        hours=_text(c.hours, 200),
        operatingDays=c.operating_days,
        eligibility=_text(c.eligibility, 300),
        verification="unverified",
        isDemoData=demo,
        sources=[ref],
        fingerprint=fingerprint(name, zip_code, lat, lon),
    )
