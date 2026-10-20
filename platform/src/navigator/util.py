"""Small pure helpers: ids, fingerprints, time, geometry."""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from datetime import datetime, timezone

_SAFE_ID = re.compile(r"[^A-Za-z0-9_-]+")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or utcnow()).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def resource_id(source_id: str, source_record_id: str) -> str:
    """URL-safe, stable id derived from the source identity (so re-syncs upsert the same item)."""
    return _SAFE_ID.sub("-", f"{source_id}-{source_record_id}").strip("-")


def _norm(text: str | None) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def fingerprint(name: str | None, zip_code: str | None, lat: float | None, lon: float | None) -> str:
    """Cross-source duplicate key: normalized name + ZIP, or name + ~100m coordinate cell."""
    place = zip_code or (f"{round(lat, 3)}:{round(lon, 3)}" if lat is not None and lon is not None else "")
    return hashlib.sha256(f"{_norm(name)}|{place}".encode()).hexdigest()[:24]


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def valid_coordinates(lat: float | None, lon: float | None) -> bool:
    return (
        lat is not None
        and lon is not None
        and -90 <= lat <= 90
        and -180 <= lon <= 180
        and not (lat == 0 and lon == 0)
    )
