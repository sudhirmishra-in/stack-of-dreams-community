"""Deterministic resource search. No LLM: filtering, distance, sorting and pagination are plain code.

Honesty rules enforced here:
  * Real records never get inventory, capacity or availability numbers. Only the `demo` namespace has them,
    and only when the caller opts in with includeDemo.
  * Distances are only computed from real coordinates and a successfully geocoded ZIP; otherwise the origin
    says `geocoded: false` and results fall back to ZIP-number closeness with no distance shown.
  * Every result carries its source id, attribution, timestamps and verification status.
"""

from __future__ import annotations

import base64
import binascii
from typing import Callable, Iterable

from navigator.config import Settings
from navigator.errors import BadRequest, NotFound
from navigator.location.client import Geocoder, in_pilot_area
from navigator.models import (
    INVENTORY_TYPES,
    InventoryRecord,
    Origin,
    ResourceRecord,
    ResourceView,
    SearchRequest,
    SearchResponse,
)
from navigator.store.data_store import DataStore
from navigator.util import haversine_miles, parse_iso, utcnow, valid_coordinates

SOURCE_LABELS = {
    "osm": "OpenStreetMap (community-sourced, unverified)",
    "demo": "DEMO DATA: synthetic sample record (fictional organization)",
}
MAX_CANDIDATES = 2000


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(f"o:{offset}".encode()).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        if not raw.startswith("o:"):
            raise ValueError
        offset = int(raw[2:])
        if not 0 <= offset <= MAX_CANDIDATES:
            raise ValueError
        return offset
    except (ValueError, binascii.Error, UnicodeDecodeError):
        raise BadRequest("Invalid cursor") from None


class SearchService:
    def __init__(self, store: DataStore, geocoder: Geocoder | None, settings: Settings):
        self.store, self.geocoder, self.settings = store, geocoder, settings

    # ---------- views ----------

    def _freshness(self, rec: ResourceRecord) -> str:
        if rec.isDemoData:
            return "unknown"  # synthetic data has no meaningful freshness
        stamps = [parse_iso(s.lastSyncedAt) for s in rec.sources if s.lastSyncedAt]
        stamps = [s for s in stamps if s]
        if not stamps:
            return "unknown"
        age_days = (utcnow() - max(stamps)).days
        return "fresh" if age_days <= self.settings.stale_after_days else "stale"

    def to_view(
        self,
        rec: ResourceRecord,
        inventory: dict[str, InventoryRecord] | None = None,
        searched_type: str | None = None,
        distance: float | None = None,
    ) -> ResourceView:
        primary = rec.sources[0]
        inv = {k: v.quantity for k, v in (inventory or {}).items()} or None
        inv_asof = max((v.asOf for v in (inventory or {}).values() if v.asOf), default=None)
        verified_at = max((s.lastVerifiedAt for s in rec.sources if s.lastVerifiedAt), default=None)
        return ResourceView(
            id=rec.id,
            name=rec.name,
            city=rec.city or rec.borough or "New York",
            borough=rec.borough,
            zipCode=rec.zipCode,
            address=rec.address,
            phone=rec.phone,
            website=rec.website,
            latitude=rec.latitude if valid_coordinates(rec.latitude, rec.longitude) else None,
            longitude=rec.longitude if valid_coordinates(rec.latitude, rec.longitude) else None,
            resourceTypes=rec.resourceTypes,
            availableQuantity=(inv or {}).get(searched_type) if searched_type in INVENTORY_TYPES else None,
            inventory=inv,
            inventoryIsDemo=bool(inv) and rec.isDemoData,
            inventoryAsOf=inv_asof,
            weeklyCapacity=rec.weeklyCapacity if rec.isDemoData else None,
            operatingDays=rec.operatingDays or None,
            hours=rec.hours,
            eligibility=rec.eligibility,
            lastUpdated=inv_asof or primary.sourceUpdatedAt,
            source=SOURCE_LABELS.get(primary.sourceId, primary.sourceId),
            sourceId=primary.sourceId,
            sourceUrl=primary.sourceUrl,
            attribution=primary.attribution,
            sourceUpdatedAt=primary.sourceUpdatedAt,
            lastSyncedAt=max((s.lastSyncedAt for s in rec.sources if s.lastSyncedAt), default=None),
            lastVerifiedAt=verified_at,
            freshness=self._freshness(rec),  # type: ignore[arg-type]
            verified=rec.verification == "verified" and verified_at is not None,
            isDemoData=rec.isDemoData,
            distanceMiles=round(distance, 1) if distance is not None else None,
        )

    # ---------- queries ----------

    def get(self, resource_id: str) -> ResourceView:
        got = self.store.get_resource(resource_id)
        if not got or not got[0].active:
            raise NotFound("Resource not found")
        rec = got[0]
        inv = self.store.get_inventory([rec.id])[rec.id] if rec.isDemoData else None
        return self.to_view(rec, inv)

    def _origin(self, zip_code: str, allow_geocode: Callable[[], bool] | None = None) -> Origin:
        if self.geocoder is None:
            point = None
        elif allow_geocode is None:
            point = self.geocoder.zip_point(zip_code)
        else:
            point = self.geocoder.zip_point(zip_code, allow_geocode)
        if point:
            return Origin(zipCode=zip_code, latitude=point.latitude, longitude=point.longitude, geocoded=True)
        return Origin(zipCode=zip_code, geocoded=False)

    def _candidates(self, req: SearchRequest) -> Iterable[ResourceRecord]:
        namespaces = ["real"] + (["demo"] if req.includeDemo else [])
        n = 0
        for ns in namespaces:
            for rec in self.store.iter_namespace(ns):
                if req.resourceType in rec.resourceTypes:
                    yield rec
                    n += 1
                    if n >= MAX_CANDIDATES:
                        return

    def search(self, req: SearchRequest, correlation_id: str, allow_geocode: Callable[[], bool] | None = None) -> SearchResponse:
        origin = self._origin(req.zipCode, allow_geocode)
        notes: list[str] = []
        records = list(self._candidates(req))

        if req.resourceType != "food_assistance" and not req.includeDemo:
            notes.append(
                "Real directory records confirm that an organization exists, not what it has in stock. "
                "No item-level inventory is available, so none is shown. Try 'Food Assistance', or include demo data."
            )

        inventory: dict[str, dict[str, InventoryRecord]] = {}
        demo_ids = [r.id for r in records if r.isDemoData][:30]
        if demo_ids:
            inventory = self.store.get_inventory(demo_ids)

        rows: list[tuple[ResourceRecord, float | None]] = []
        excluded_no_coords = 0
        for rec in records:
            dist = None
            if origin.geocoded and valid_coordinates(rec.latitude, rec.longitude):
                dist = haversine_miles(origin.latitude, origin.longitude, rec.latitude, rec.longitude)  # type: ignore[arg-type]
            if req.radiusMiles is not None and origin.geocoded:
                if dist is None:
                    excluded_no_coords += 1
                    continue
                if dist > req.radiusMiles:
                    continue
            if req.quantity and req.resourceType in INVENTORY_TYPES:
                inv = inventory.get(rec.id, {}).get(req.resourceType)
                if inv is None or inv.quantity < req.quantity:
                    continue  # unknown stock never satisfies a quantity requirement
            rows.append((rec, dist))

        if req.radiusMiles is not None and not origin.geocoded:
            notes.append("Distance filter was not applied: the ZIP code could not be located right now.")
        if excluded_no_coords:
            notes.append(f"{excluded_no_coords} provider(s) without map coordinates were excluded by the distance filter.")
        if not origin.geocoded and not in_pilot_area(req.zipCode):
            notes.append("Location features currently cover the New York City pilot area only.")
        if not origin.geocoded:
            notes.append("Distances are not shown: location lookup is unavailable. Results are ordered by ZIP code similarity.")

        sort = req.sortBy or "nearest"
        zip_num = int(req.zipCode)

        def qty(rec: ResourceRecord) -> int:
            q = inventory.get(rec.id, {}).get(req.resourceType)
            return q.quantity if q else -1

        def key(row: tuple[ResourceRecord, float | None]):
            rec, dist = row
            if sort == "availability":
                return (-qty(rec), rec.name)
            if sort == "capacity":
                return (-(rec.weeklyCapacity or 0), rec.name)
            if dist is not None:
                return (0, dist, rec.name)
            zip_gap = abs(int(rec.zipCode) - zip_num) if rec.zipCode else 10**6
            return (1, zip_gap, rec.name)

        rows.sort(key=key)
        total = len(rows)
        start = decode_cursor(req.cursor)
        page = rows[start : start + req.limit]
        views = [self.to_view(r, inventory.get(r.id), req.resourceType, d) for r, d in page]
        next_cursor = encode_cursor(start + req.limit) if start + req.limit < total else None

        attributions = sorted({v.attribution for v in views if v.attribution and not v.isDemoData})
        any_demo = any(v.isDemoData for v in views)
        return SearchResponse(
            resources=views,
            totalResults=total,
            dataSource=("Real directory records" + (" + DEMO DATA (synthetic)" if any_demo else "")),
            isDemoData=any_demo,
            origin=origin,
            nextCursor=next_cursor,
            attributions=attributions,
            notes=notes,
            correlationId=correlation_id,
        )
