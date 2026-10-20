"""Authenticated map proxy: strict inputs, rewritten style, binary relay, limits, fail-closed behavior."""

import base64
import io
import json
import time

import jwt
import pytest
from botocore.exceptions import ClientError
from cryptography.hazmat.primitives.asymmetric import rsa

from navigator.api.app import App, Deps
from navigator.config import Settings
from navigator.gateway.auth import JwtVerifier
from navigator.gateway.invoker import MockInvoker
from navigator.gateway.pipeline import AssistantPipeline
from navigator.location.maps import MapsClient, rewrite_style
from navigator.quota.ledger import UsageLedger
from navigator.search.service import SearchService
from navigator.store.data_store import DataStore

POOL, CLIENT = "us-east-2_AbCdEfGhI", "client-123"
ISS = f"https://cognito-idp.us-east-2.amazonaws.com/{POOL}"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
HOST = "abcdefg123.lambda-url.us-east-2.on.aws"

# Trimmed copy of the real Standard style descriptor structure (captured 2026-10-20).
STYLE = {
    "version": 8,
    "sprite": "https://maps.geo.us-east-2.amazonaws.com/v2/styles/4_1_0-beta_1/Standard/Dark/Default/sprites/sprites",
    "glyphs": "https://maps.geo.us-east-2.amazonaws.com/v2/glyphs/{fontstack}/{range}.pbf",
    "sources": {"aws": {"type": "vector", "maxzoom": 17, "attribution": "© AWS, HERE", "tiles": ["https://maps.geo.us-east-2.amazonaws.com/v2/tiles/vector.basemap/{z}/{x}/{y}"]}},
    "layers": [{"id": "bg", "type": "background"}],
}


class Blob:
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data


class FakeGeoMaps:
    def __init__(self):
        self.calls = []
        self.error = None

    def _maybe_fail(self):
        if self.error:
            raise self.error

    def get_style_descriptor(self, **kw):
        self.calls.append(("style", kw)); self._maybe_fail()
        return {"Blob": Blob(json.dumps(STYLE).encode()), "ContentType": "application/json"}

    def get_tile(self, **kw):
        self.calls.append(("tile", kw)); self._maybe_fail()
        return {"Blob": Blob(b"\x1a\x02tile-bytes\x00\xff"), "ContentType": "application/x-protobuf"}

    def get_glyphs(self, **kw):
        self.calls.append(("glyphs", kw)); self._maybe_fail()
        return {"Blob": Blob(b"glyph"), "ContentType": "application/x-protobuf"}

    def get_sprites(self, **kw):
        self.calls.append(("sprites", kw)); self._maybe_fail()
        return {"Blob": Blob(b"\x89PNGsprite"), "ContentType": "image/png"}


def tok(sub="user-sub-0001"):
    return jwt.encode({"sub": sub, "iss": ISS, "client_id": CLIENT, "token_use": "access", "exp": int(time.time()) + 600}, KEY, algorithm="RS256")


@pytest.fixture
def env(aws):
    s = Settings(data_table="data-t", usage_table="usage-t", cognito_user_pool_id=POOL, cognito_client_id=CLIENT, mock_mode=True)
    store, ledger = DataStore("data-t", resource=aws), UsageLedger("usage-t", resource=aws)
    geo = FakeGeoMaps()
    deps = Deps(s, JwtVerifier(POOL, CLIENT, key_resolver=lambda t: KEY.public_key()), store, ledger,
                SearchService(store, None, s), AssistantPipeline(ledger, MockInvoker(), None, s), None, MapsClient("us-east-2", client=geo))
    return App(deps), geo, ledger


def get(app, path, token=None, query=None, host=HOST):
    ev = {"rawPath": path, "requestContext": {"http": {"method": "GET"}, "domainName": host}, "headers": {"authorization": f"Bearer {token}"} if token else {}, "queryStringParameters": query or {}}
    r = app.handle(ev)
    return r["statusCode"], r


def test_every_map_endpoint_requires_a_valid_token(env):
    app, geo, _ = env
    for path in ("/api/v1/maps/style", "/api/v1/maps/tiles/vector.basemap/10/301/385", "/api/v1/maps/glyphs/Noto%20Sans/0-255.pbf", "/api/v1/maps/sprites/Dark/Default/sprites.json"):
        assert get(app, path)[0] == 401
        assert get(app, path, "forged.token.value")[0] == 401
    assert geo.calls == []  # nothing reached AWS


def test_style_is_rewritten_so_the_browser_only_talks_to_this_api(env):
    app, geo, _ = env
    s, r = get(app, "/api/v1/maps/style", tok(), {"scheme": "Dark"})
    style = json.loads(r["body"])
    assert s == 200 and r["headers"]["Content-Type"] == "application/json"
    base = f"https://{HOST}/api/v1/maps"
    assert style["sprite"] == f"{base}/sprites/Dark/Default/sprites"
    assert style["glyphs"] == f"{base}/glyphs/{{fontstack}}/{{range}}"
    assert style["sources"]["aws"]["tiles"] == [f"{base}/tiles/vector.basemap/{{z}}/{{x}}/{{y}}"]
    assert style["sources"]["aws"]["attribution"] == "© AWS, HERE"  # required attribution is preserved
    assert "maps.geo" not in json.dumps({k: v for k, v in style.items() if k != "sources"}) and "amazonaws.com" not in json.dumps(style["sources"]["aws"]["tiles"])


def test_style_is_cached_per_scheme_and_validates_the_scheme(env):
    app, geo, _ = env
    get(app, "/api/v1/maps/style", tok(), {"scheme": "Light"})
    get(app, "/api/v1/maps/style", tok(), {"scheme": "Light"})
    assert [c[0] for c in geo.calls].count("style") == 1
    assert get(app, "/api/v1/maps/style", tok(), {"scheme": "Neon"})[0] == 400


def test_style_refuses_untrusted_hosts(env):
    app, *_ = env
    assert get(app, "/api/v1/maps/style", tok(), host="evil.example.com")[0] == 503


def test_tiles_are_relayed_as_binary_with_private_caching(env):
    app, geo, _ = env
    s, r = get(app, "/api/v1/maps/tiles/vector.basemap/10/301/385", tok())
    assert s == 200 and r["isBase64Encoded"] is True
    assert base64.b64decode(r["body"]) == b"\x1a\x02tile-bytes\x00\xff"
    assert r["headers"]["Content-Type"] == "application/x-protobuf" and r["headers"]["Cache-Control"] == "private, max-age=86400"
    assert geo.calls[-1] == ("tile", {"Tileset": "vector.basemap", "Z": "10", "X": "301", "Y": "385"})


@pytest.mark.parametrize("path,status", [
    ("/api/v1/maps/tiles/vector.basemap/18/1/1", 400),          # beyond max zoom
    ("/api/v1/maps/tiles/vector.basemap/3/8/0", 400),            # x out of range for z=3
    ("/api/v1/maps/tiles/vector.basemap/a/1/1", 400),
    ("/api/v1/maps/tiles/vector.basemap/1/-1/1", 400),
    ("/api/v1/maps/tiles/satellite.imagery/1/1/1", 404),         # tileset allowlist
    ("/api/v1/maps/tiles/..%2f..%2fsecret/1/1/1", 404),
    ("/api/v1/maps/glyphs/..%2f..%2fetc/0-255.pbf", 400),        # path traversal attempt
    ("/api/v1/maps/glyphs/Noto%20Sans/0-255999.pbf", 400),
    ("/api/v1/maps/glyphs/Noto%20Sans/10-265.pbf", 400),         # not aligned to 256
    ("/api/v1/maps/glyphs/Noto%20Sans/256-300.pbf", 400),
    ("/api/v1/maps/sprites/Neon/Default/sprites.json", 404),
    ("/api/v1/maps/sprites/Dark/Default/../../x", 404),
    ("/api/v1/maps/sprites/Dark/Other/sprites.png", 404),
])
def test_map_inputs_are_validated_before_anything_reaches_aws(env, path, status):
    app, geo, _ = env
    assert get(app, path, tok())[0] == status
    assert geo.calls == []


def test_glyphs_and_sprites_are_relayed_with_decoded_font_names(env):
    app, geo, _ = env
    s, r = get(app, "/api/v1/maps/glyphs/Amazon%20Ember%20Regular%2CNoto%20Sans%20Regular/0-255.pbf", tok())
    assert s == 200 and base64.b64decode(r["body"]) == b"glyph"
    assert geo.calls[-1] == ("glyphs", {"FontStack": "Amazon Ember Regular,Noto Sans Regular", "FontUnicodeRange": "0-255.pbf"})
    s, r = get(app, "/api/v1/maps/sprites/Dark/Default/sprites@2x.png", tok())
    assert s == 200 and r["headers"]["Content-Type"] == "image/png"
    assert geo.calls[-1] == ("sprites", {"Style": "Standard", "ColorScheme": "Dark", "Variant": "Default", "FileName": "sprites@2x.png"})


def test_upstream_not_found_and_failures_map_to_404_and_a_generic_503(env):
    app, geo, _ = env
    geo.error = ClientError({"Error": {"Code": "NoSuchKey", "Message": "secret-bucket/path"}, "ResponseMetadata": {"HTTPStatusCode": 404}}, "GetGlyphs")
    assert get(app, "/api/v1/maps/glyphs/Missing/0-255.pbf", tok())[0] == 404
    geo.error = ClientError({"Error": {"Code": "AccessDeniedException", "Message": "arn:aws:iam::1:role/x denied"}, "ResponseMetadata": {"HTTPStatusCode": 403}}, "GetTile")
    s, r = get(app, "/api/v1/maps/tiles/vector.basemap/1/0/0", tok())
    assert s == 503 and "arn:aws" not in r["body"] and "denied" not in r["body"]


def test_disabled_users_and_the_daily_cap_apply_to_map_requests(env):
    app, geo, ledger = env
    ledger.set_user_profile("user-sub-0001", disabled=None, overrides={"map_requests_per_user_day": 2}, actor="a")
    assert get(app, "/api/v1/maps/tiles/vector.basemap/1/0/0", tok())[0] == 200
    assert get(app, "/api/v1/maps/tiles/vector.basemap/1/0/1", tok())[0] == 200
    s, r = get(app, "/api/v1/maps/tiles/vector.basemap/1/1/0", tok())
    assert s == 429 and json.loads(r["body"])["error"]["details"]["reason"] == "map"
    ledger.set_user_profile("other-sub-0002", disabled=True, overrides=None, actor="a")
    assert get(app, "/api/v1/maps/tiles/vector.basemap/1/0/0", tok("other-sub-0002"))[0] == 403


def test_rewrite_style_does_not_mutate_its_input():
    original = json.dumps(STYLE)
    rewrite_style(STYLE, "https://x.lambda-url.us-east-2.on.aws", "Light")
    assert json.dumps(STYLE) == original
