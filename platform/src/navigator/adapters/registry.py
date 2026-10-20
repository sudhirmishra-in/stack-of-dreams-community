"""Builds the enabled adapters from settings. Source isolation lives in the sync runner."""

from __future__ import annotations

from navigator.config import Settings

from .base import SourceAdapter
from .http import HttpClient
from .nyc_cfc import NycCfcAdapter
from .osm import OsmAdapter
from .twoone_one import TwoOneOneAdapter


def build_adapters(settings: Settings, http: HttpClient | None = None) -> dict[str, SourceAdapter]:
    client = http or HttpClient(f"StackOfDreamsLabs-pilot/0.1 (contact: {settings.contact_for_user_agent})")
    adapters: dict[str, SourceAdapter] = {}
    if settings.osm_enabled:
        adapters["osm"] = OsmAdapter(client, settings.overpass_url)
    if settings.nyc_cfc_enabled:
        adapters["nyc-cfc"] = NycCfcAdapter(client)
    # Always registered so its disabled state shows up in sync status instead of silently vanishing.
    adapters["211"] = TwoOneOneAdapter(settings.twoone_one_enabled, settings.twoone_one_api_key_param)
    return adapters
