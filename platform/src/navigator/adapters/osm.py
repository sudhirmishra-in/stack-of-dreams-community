"""OpenStreetMap (Overpass API) food bank / soup kitchen directory.

Terms: ODbL 1.0 (https://opendatacommons.org/licenses/odbl/1-0/). Attribution "(c) OpenStreetMap
contributors" is mandatory and is carried on every record. Data is community-sourced and **not verified**.
Overpass is a shared public service: this adapter makes one query per run, with backoff, from a
low-frequency schedule, and identifies itself with a contact in the User-Agent.
"""

from __future__ import annotations

import re
from typing import Any, Iterator

from navigator.models import SourceRef
from navigator.util import iso, valid_coordinates

from .base import Page, ResourceCandidate
from .http import HttpClient

SOURCE_ID = "osm"
LICENSE = "ODbL 1.0"
ATTRIBUTION = "© OpenStreetMap contributors"
NYC_AREA_ID = 3600175905  # OSM relation 175905 (New York City) as an Overpass area id

_ZIP = re.compile(r"^(\d{5})(?:-\d{4})?$")


def build_query(area_id: int = NYC_AREA_ID, newer_than: str | None = None) -> str:
    newer = f'(newer:"{newer_than}")' if newer_than else ""
    return (
        f"[out:json][timeout:60];area(id:{area_id})->.a;("
        f'nwr(area.a)["amenity"="social_facility"]["social_facility"~"^(food_bank|soup_kitchen)$"]{newer};'
        f'nwr(area.a)["amenity"="food_bank"]{newer};'
        ");out meta center tags 1000;"
    )


def _clean(value: Any, limit: int = 200) -> str | None:
    if not isinstance(value, str):
        return None
    v = " ".join(value.split())
    return v[:limit] or None


def _website(tags: dict[str, str]) -> str | None:
    url = _clean(tags.get("website") or tags.get("contact:website"), 300)
    return url if url and re.match(r"^https?://", url, re.I) else None


def map_element(el: dict[str, Any], synced_at: str) -> ResourceCandidate | None:
    """Maps one Overpass element, or returns None when it lacks the minimum (a name)."""
    tags: dict[str, str] = el.get("tags") or {}
    name = _clean(tags.get("name"), 120)
    if not name:
        return None  # an unnamed point cannot be shown to a family or de-duplicated safely
    lat = el.get("lat", (el.get("center") or {}).get("lat"))
    lon = el.get("lon", (el.get("center") or {}).get("lon"))
    if not valid_coordinates(lat, lon):
        lat = lon = None

    zip_match = _ZIP.match((tags.get("addr:postcode") or "").strip())
    house, street = _clean(tags.get("addr:housenumber"), 20), _clean(tags.get("addr:street"), 100)
    kind = tags.get("social_facility") or tags.get("amenity")
    record_id = f"{el.get('type', 'node')}/{el['id']}"
    return ResourceCandidate(
        source_id=SOURCE_ID,
        source_record_id=record_id,
        name=name,
        zip_code=zip_match.group(1) if zip_match else None,
        city=_clean(tags.get("addr:city"), 60),
        address=f"{house} {street}" if house and street else None,
        phone=_clean(tags.get("phone") or tags.get("contact:phone"), 40),
        website=_website(tags),
        latitude=lat,
        longitude=lon,
        facility_kind="soup_kitchen" if kind == "soup_kitchen" else "food_bank",
        hours=_clean(tags.get("opening_hours"), 200),
        ref=SourceRef(
            sourceId=SOURCE_ID,
            sourceRecordId=record_id,
            sourceUrl=f"https://www.openstreetmap.org/{record_id}",
            license=LICENSE,
            attribution=ATTRIBUTION,
            sourceUpdatedAt=el.get("timestamp"),
            lastSyncedAt=synced_at,
            lastVerifiedAt=None,
        ),
    )


class OsmAdapter:
    source_id = SOURCE_ID
    supports_deactivation = True

    def __init__(self, http: HttpClient, url: str, area_id: int = NYC_AREA_ID):
        self.http, self.url, self.area_id = http, url, area_id

    def fetch(self, checkpoint: str | None, full: bool) -> Iterator[Page]:
        # Incremental runs ask only for elements changed since the last successful sync. Deletions are
        # invisible to that query, so only full runs may deactivate missing records.
        newer = None if full or not checkpoint else checkpoint
        data = self.http.post_form_json(self.url, {"data": build_query(self.area_id, newer)})
        elements = data.get("elements") if isinstance(data, dict) else None
        if not isinstance(elements, list):
            raise ValueError("unexpected Overpass response shape")
        synced_at = iso()
        resources, rejected = [], 0
        for el in elements:
            if not isinstance(el, dict) or "id" not in el:
                rejected += 1
                continue
            cand = map_element(el, synced_at)
            if cand is None:
                rejected += 1
            else:
                resources.append(cand)
        base_ts = (data.get("osm3s") or {}).get("timestamp_osm_base")
        yield Page(resources=resources, checkpoint=base_ts or checkpoint, rejected=rejected, complete=newer is None)
