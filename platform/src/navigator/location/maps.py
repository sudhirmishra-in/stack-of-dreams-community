"""Map data access for the browser map, served through our authenticated API (no browser-side AWS key).

Account policy blocks creating Amazon Location API keys, so the API Lambda fetches style, tiles, sprites and
glyphs with its own IAM role and relays them to signed-in users. Inputs are validated against strict patterns
and allowlists before anything reaches AWS, and the style descriptor is rewritten so the browser only ever
talks to this API.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from navigator.errors import BadRequest, NotFound, ServiceUnavailable
from navigator.logging_util import log

SCHEMES = ("Light", "Dark")
TILESETS = ("vector.basemap",)
MAX_ZOOM = 17  # the style declares maxzoom 17
_FONTSTACK = re.compile(r"^[A-Za-z0-9 ,_-]{1,200}$")
_RANGE = re.compile(r"^\d{1,5}-\d{1,5}$")
_SPRITE_FILES = ("sprites.json", "sprites.png", "sprites@2x.json", "sprites@2x.png")
_HOST = re.compile(r"^[a-z0-9]+\.lambda-url\.[a-z0-9-]+\.on\.aws$")
STYLE = "Standard"
VARIANT = "Default"


@dataclass(frozen=True)
class MapAsset:
    body: bytes
    content_type: str
    cache_control: str = "private, max-age=86400"


def public_base(domain_name: str | None) -> str:
    """The URL the browser used to reach this API. Only a real Function URL host is trusted."""
    if not domain_name or not _HOST.match(domain_name):
        raise ServiceUnavailable("Map service is not available from this address.")
    return f"https://{domain_name}"


def rewrite_style(style: dict[str, Any], base: str, scheme: str) -> dict[str, Any]:
    """Points every data URL in the descriptor at this API. Attribution links are left untouched."""
    out = json.loads(json.dumps(style))  # deep copy
    prefix = f"{base}/api/v1/maps"
    out["sprite"] = f"{prefix}/sprites/{scheme}/{VARIANT}/sprites"
    out["glyphs"] = f"{prefix}/glyphs/{{fontstack}}/{{range}}"
    for src in (out.get("sources") or {}).values():
        if isinstance(src, dict) and src.get("tiles"):
            src["tiles"] = [f"{prefix}/tiles/{ts}/{{z}}/{{x}}/{{y}}" for ts in TILESETS]
        src.pop("url", None) if isinstance(src, dict) and "tiles" in src else None
    return out


class MapsClient:
    def __init__(self, region: str, client: Any = None):
        cfg = Config(retries={"max_attempts": 2, "mode": "standard"}, connect_timeout=3, read_timeout=8)
        self._c = client or boto3.client("geo-maps", region_name=region, config=cfg)
        self._style_cache: dict[str, dict[str, Any]] = {}

    def _call(self, name: str, **kw: Any) -> tuple[bytes, str]:
        try:
            r = getattr(self._c, name)(**kw)
            blob = r["Blob"]
            return (blob.read() if hasattr(blob, "read") else blob), r.get("ContentType", "application/octet-stream")
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if code in ("404", "NoSuchKey", "ResourceNotFoundException") or status == 404:
                raise NotFound("Map asset not found") from e
            log("maps_upstream_error", operation=name, code=code)
            raise ServiceUnavailable("The map service is unavailable right now.") from e
        except Exception as e:
            log("maps_upstream_error", operation=name, code=type(e).__name__)
            raise ServiceUnavailable("The map service is unavailable right now.") from e

    def style(self, scheme: str, base: str) -> dict[str, Any]:
        if scheme not in SCHEMES:
            raise BadRequest("scheme must be Light or Dark")
        if scheme not in self._style_cache:  # descriptors change rarely; keep per warm container
            body, _ = self._call("get_style_descriptor", Style=STYLE, ColorScheme=scheme)
            self._style_cache[scheme] = json.loads(body)
        return rewrite_style(self._style_cache[scheme], base, scheme)

    def tile(self, tileset: str, z: str, x: str, y: str) -> MapAsset:
        if tileset not in TILESETS:
            raise NotFound("Unknown tileset")
        if not (z.isdigit() and x.isdigit() and y.isdigit()) or len(z + x + y) > 20:
            raise BadRequest("Invalid tile coordinates")
        zi, xi, yi = int(z), int(x), int(y)
        if zi > MAX_ZOOM or xi >= 2**zi or yi >= 2**zi:
            raise BadRequest("Tile coordinates out of range")
        body, ctype = self._call("get_tile", Tileset=tileset, Z=str(zi), X=str(xi), Y=str(yi))
        return MapAsset(body, ctype)

    def glyphs(self, fontstack: str, unicode_range: str) -> MapAsset:
        if not _FONTSTACK.match(fontstack) or not _RANGE.match(unicode_range):
            raise BadRequest("Invalid glyph request")
        start, end = (int(n) for n in unicode_range.split("-"))
        if start % 256 != 0 or end != start + 255:
            raise BadRequest("Glyph ranges must be aligned to 256")
        # The AWS API takes the range WITH its extension (pattern [0-9]+-[0-9]+\.pbf), unlike the style's URL template.
        body, _ = self._call("get_glyphs", FontStack=fontstack, FontUnicodeRange=f"{unicode_range}.pbf")
        return MapAsset(body, "application/x-protobuf")

    def sprite(self, scheme: str, variant: str, filename: str) -> MapAsset:
        if scheme not in SCHEMES or variant != VARIANT or filename not in _SPRITE_FILES:
            raise NotFound("Unknown sprite")
        body, _ = self._call("get_sprites", Style=STYLE, ColorScheme=scheme, Variant=variant, FileName=filename)
        return MapAsset(body, "application/json" if filename.endswith(".json") else "image/png")
