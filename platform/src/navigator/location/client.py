"""Amazon Location Service (Places v2 + Routes v2) with a DynamoDB ZIP-centroid cache.

No LLM is involved here. A ZIP geocode is requested at most once per ZIP (cached permanently, which is why
the request uses IntendedUse="Storage": that is the licence mode that allows storing results). Routes are
only requested on demand for one origin/destination pair. If the service is unreachable or not permitted,
callers fall back to non-geographic ordering; nothing is estimated or invented.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import os
from typing import Callable

import boto3
from botocore.config import Config

from navigator.logging_util import log
from navigator.store.data_store import DataStore
from navigator.util import valid_coordinates

PROVIDER = "amazon-location-places-v2"

# Pilot geography: New York City ZIP prefixes (Manhattan 100-102, Staten Island 103, Bronx 104, Queens/Brooklyn
# 110-114, Rockaways 116). Geocoding is a paid, storage-licensed lookup, so it is limited to this area: that keeps the
# number of distinct paid lookups to a few hundred for the lifetime of the cache. Override with GEOCODE_ZIP_PREFIXES
# (comma-separated; empty string = no restriction) when the pilot expands.
DEFAULT_PILOT_ZIP_PREFIXES = ("100", "101", "102", "103", "104", "110", "111", "112", "113", "114", "116")


def pilot_zip_prefixes() -> tuple[str, ...]:
    raw = os.environ.get("GEOCODE_ZIP_PREFIXES")
    if raw is None:
        return DEFAULT_PILOT_ZIP_PREFIXES
    return tuple(p.strip() for p in raw.split(",") if p.strip())


def in_pilot_area(zip_code: str) -> bool:
    prefixes = pilot_zip_prefixes()
    return not prefixes or zip_code.startswith(prefixes)


class LocationUnavailable(Exception):
    pass


@dataclass(frozen=True)
class GeoPoint:
    latitude: float
    longitude: float
    cached: bool = False


@dataclass(frozen=True)
class RouteSummary:
    distance_miles: float
    duration_minutes: float
    travel_mode: str


class Geocoder(Protocol):
    def zip_point(self, zip_code: str, allow_remote: Callable[[], bool] | None = None) -> GeoPoint | None: ...


class LocationClient:
    def __init__(self, region: str, places: Any = None, routes: Any = None):
        cfg = Config(retries={"max_attempts": 2, "mode": "standard"}, connect_timeout=3, read_timeout=5)
        self._places = places or boto3.client("geo-places", region_name=region, config=cfg)
        self._routes = routes or boto3.client("geo-routes", region_name=region, config=cfg)

    def geocode_zip(self, zip_code: str) -> GeoPoint | None:
        try:
            resp = self._places.geocode(
                QueryComponents={"PostalCode": zip_code, "Country": "USA"},
                Filter={"IncludeCountries": ["USA"]},
                MaxResults=1,
                IntendedUse="Storage",
            )
        except Exception as e:  # not permitted, throttled, network... all mean "location unavailable"
            log("geocode_failed", error=type(e).__name__)
            raise LocationUnavailable(type(e).__name__) from e
        items = resp.get("ResultItems") or []
        if not items or not items[0].get("Position") or len(items[0]["Position"]) != 2:
            return None
        lon, lat = items[0]["Position"]
        return GeoPoint(lat, lon) if valid_coordinates(lat, lon) else None

    def route(self, origin: tuple[float, float], dest: tuple[float, float], mode: str = "Car") -> RouteSummary | None:
        if mode not in ("Car", "Pedestrian"):
            raise ValueError("unsupported travel mode")
        try:
            resp = self._routes.calculate_routes(
                Origin=[origin[1], origin[0]], Destination=[dest[1], dest[0]], TravelMode=mode, MaxAlternatives=0
            )
        except Exception as e:
            log("route_failed", error=type(e).__name__)
            raise LocationUnavailable(type(e).__name__) from e
        routes = resp.get("Routes") or []
        totals = _route_totals(routes[0]) if routes else None
        if totals is None:
            return None
        meters, seconds = totals
        return RouteSummary(round(meters / 1609.344, 1), round(seconds / 60, 1), mode)


def _route_totals(route: dict[str, Any]) -> tuple[float, float] | None:
    """Distance (m) and duration (s) from a CalculateRoutes route.

    Real responses differ by travel mode: Car carries `Summary{Distance,Duration}` on the route, Pedestrian
    only has per-leg `PedestrianLegDetails.Summary.Overview{Distance,Duration}`. Use the route summary when it
    exists, otherwise sum the legs. Never guess: if neither is present there is no result.
    """
    top = route.get("Summary")
    if isinstance(top, dict) and "Distance" in top and "Duration" in top:
        return float(top["Distance"]), float(top["Duration"])
    meters = seconds = 0.0
    found = False
    for leg in route.get("Legs") or []:
        for key in ("VehicleLegDetails", "PedestrianLegDetails"):
            overview = ((leg.get(key) or {}).get("Summary") or {}).get("Overview") or {}
            if "Distance" in overview and "Duration" in overview:
                meters += float(overview["Distance"])
                seconds += float(overview["Duration"])
                found = True
    return (meters, seconds) if found else None


class CachedZipGeocoder:
    def __init__(self, store: DataStore, client: LocationClient | None):
        self.store, self.client = store, client

    def zip_point(self, zip_code: str, allow_remote: Callable[[], bool] | None = None) -> GeoPoint | None:
        """Cached centroid, or (only for pilot-area ZIPs, and only if `allow_remote` agrees) one paid lookup."""
        hit = self.store.get_zip_geo(zip_code)
        if hit and valid_coordinates(hit.get("latitude"), hit.get("longitude")):
            return GeoPoint(hit["latitude"], hit["longitude"], cached=True)
        if self.client is None or not in_pilot_area(zip_code):
            return None
        if allow_remote is not None and not allow_remote():
            return None  # per-user / app-wide geocode budget exhausted: degrade to no distances, never guess
        try:
            point = self.client.geocode_zip(zip_code)
        except LocationUnavailable:
            return None
        if point:
            self.store.put_zip_geo(zip_code, point.latitude, point.longitude, PROVIDER)
        return point
