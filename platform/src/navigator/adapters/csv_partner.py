"""Partner CSV adapter: the extension point for nonprofit partner exports (e.g. an S3 upload).

Expected columns (header row required): id, name, address, city, borough, zip, phone, website, lat, lon,
types (semicolon separated: baby_formula;groceries;diapers;food_assistance), hours, eligibility.
Partner data is `unverified` until a human sets lastVerifiedAt. Source reading is injected, so an S3-triggered
Lambda can pass the object body, or the REST/webhook adapters can reuse `map_row`.
"""

from __future__ import annotations

import csv
import io
from typing import Callable, Iterator

from navigator.models import RESOURCE_TYPES, SourceRef
from navigator.util import iso, valid_coordinates

from .base import Page, ResourceCandidate

MAX_ROWS = 20_000


def _f(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def map_row(source_id: str, row: dict[str, str], synced_at: str) -> ResourceCandidate | None:
    rid, name = (row.get("id") or "").strip(), (row.get("name") or "").strip()
    if not rid or not name:
        return None
    lat, lon = _f(row.get("lat")), _f(row.get("lon"))
    if not valid_coordinates(lat, lon):
        lat = lon = None
    types = [t.strip() for t in (row.get("types") or "").split(";") if t.strip() in RESOURCE_TYPES] or ["food_assistance"]
    return ResourceCandidate(
        source_id=source_id,
        source_record_id=rid,
        name=name,
        zip_code=(row.get("zip") or "").strip()[:5] or None,
        city=(row.get("city") or "").strip() or None,
        borough=(row.get("borough") or "").strip() or None,
        address=(row.get("address") or "").strip() or None,
        phone=(row.get("phone") or "").strip() or None,
        website=(row.get("website") or "").strip() or None,
        latitude=lat,
        longitude=lon,
        resource_types=types,  # type: ignore[arg-type]
        hours=(row.get("hours") or "").strip() or None,
        eligibility=(row.get("eligibility") or "").strip() or None,
        ref=SourceRef(sourceId=source_id, sourceRecordId=rid, lastSyncedAt=synced_at),
    )


class CsvPartnerAdapter:
    supports_deactivation = True

    def __init__(self, source_id: str, read_text: Callable[[], str]):
        self.source_id, self._read = source_id, read_text

    def fetch(self, checkpoint: str | None, full: bool) -> Iterator[Page]:
        synced_at = iso()
        resources, rejected = [], 0
        for i, row in enumerate(csv.DictReader(io.StringIO(self._read()))):
            if i >= MAX_ROWS:
                raise ValueError(f"CSV exceeds {MAX_ROWS} rows")
            cand = map_row(self.source_id, row, synced_at)
            if cand is None:
                rejected += 1
            else:
                resources.append(cand)
        yield Page(resources=resources, rejected=rejected, complete=True)
