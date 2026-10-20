"""API application: routing, auth, error shapes. One Lambda behind a Function URL (payload format v2).

Endpoints (all JSON, all under /api/v1, all except /health require a verified Cognito access token):
  GET  /api/v1/health
  POST /api/v1/resources/search          deterministic DynamoDB search, no LLM
  GET  /api/v1/resources/{id}
  GET  /api/v1/route                     optional, on-demand, Amazon Location
  POST /api/v1/assistant                 validation gateway -> community-navigator runtime
  GET  /api/v1/me/usage
  GET  /api/v1/sync-status               data freshness per source
  PUT  /api/v1/admin/quotas | /admin/switch | /admin/users/{sub};  GET /api/v1/admin/usage | /admin/sync-status
"""

from __future__ import annotations

import base64
import json
import re
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from navigator.config import QuotaLimits, Settings
from navigator.ingest import metrics
from navigator.errors import ApiError, BadRequest, Forbidden, NotFound, ServiceUnavailable, Unauthorized
from navigator.gateway.auth import Identity, JwtVerifier
from navigator.gateway.pipeline import AssistantPipeline, build_usage
from navigator.location.client import LocationClient, LocationUnavailable
from navigator.location.maps import MapAsset, MapsClient, public_base
from navigator.logging_util import log
from navigator.models import AssistantRequest, SearchRequest
from navigator.quota.ledger import UsageLedger
from navigator.search.service import SearchService
from navigator.store.data_store import DataStore

VERSION = "0.1.0"
MAX_BODY_BYTES = 16 * 1024
_CORR = re.compile(r"^[A-Za-z0-9_.:-]{8,64}$")
_ID = re.compile(r"^[A-Za-z0-9_-]{1,120}$")
_SUB = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")
_ZIP = re.compile(r"^\d{5}$")
SYNC_SOURCES = ("osm", "nyc-cfc", "211")


@dataclass
class Deps:
    settings: Settings
    verifier: JwtVerifier
    store: DataStore
    ledger: UsageLedger
    search: SearchService
    pipeline: AssistantPipeline
    location: LocationClient | None
    maps: MapsClient | None = None


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, str]
    headers: dict[str, str]
    body: Any
    correlation_id: str
    identity: Identity | None = None
    domain: str | None = None


def _binary(asset: MapAsset, cid: str) -> dict[str, Any]:
    return {
        "statusCode": 200,
        "isBase64Encoded": True,
        "headers": {"Content-Type": asset.content_type, "Cache-Control": asset.cache_control, "X-Content-Type-Options": "nosniff", "X-Correlation-Id": cid},
        "body": base64.b64encode(asset.body).decode(),
    }


def _json(status: int, body: Any, cid: str, extra: dict[str, str] | None = None) -> dict[str, Any]:
    payload = body.model_dump(mode="json", exclude_none=False) if isinstance(body, BaseModel) else body
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Correlation-Id": cid,
            **(extra or {}),
        },
        "body": json.dumps(payload, separators=(",", ":")),
    }


def _validate(model: type[BaseModel], body: Any) -> Any:
    if not isinstance(body, dict):
        raise BadRequest("Request body must be a JSON object")
    try:
        return model.model_validate(body)
    except ValidationError as e:
        # Report which fields are wrong, never the submitted values.
        problems = [{"field": ".".join(str(p) for p in err["loc"]), "issue": err["type"]} for err in e.errors()[:10]]
        raise BadRequest("Invalid request", details={"fields": problems}) from None


class App:
    def __init__(self, deps: Deps):
        self.d = deps
        self.routes: list[tuple[str, re.Pattern[str], Callable[..., Any], str]] = [
            ("GET", re.compile(r"^/api/v1/health$"), self.health, "none"),
            ("POST", re.compile(r"^/api/v1/resources/search$"), self.search, "user"),
            ("GET", re.compile(r"^/api/v1/resources/(?P<id>[^/]+)$"), self.get_resource, "user"),
            ("GET", re.compile(r"^/api/v1/route$"), self.route, "user"),
            ("POST", re.compile(r"^/api/v1/assistant$"), self.assistant, "user"),
            ("GET", re.compile(r"^/api/v1/me/usage$"), self.me_usage, "user"),
            ("GET", re.compile(r"^/api/v1/maps/style$"), self.map_style, "user"),
            ("GET", re.compile(r"^/api/v1/maps/tiles/(?P<tileset>[^/]+)/(?P<z>[^/]+)/(?P<x>[^/]+)/(?P<y>[^/]+)$"), self.map_tile, "user"),
            ("GET", re.compile(r"^/api/v1/maps/glyphs/(?P<fontstack>[^/]+)/(?P<rng>[^/]+)\.pbf$"), self.map_glyphs, "user"),
            ("GET", re.compile(r"^/api/v1/maps/sprites/(?P<scheme>[^/]+)/(?P<variant>[^/]+)/(?P<file>[^/]+)$"), self.map_sprite, "user"),
            ("GET", re.compile(r"^/api/v1/sync-status$"), self.sync_status, "user"),
            ("PUT", re.compile(r"^/api/v1/admin/quotas$"), self.admin_quotas, "admin"),
            ("PUT", re.compile(r"^/api/v1/admin/switch$"), self.admin_switch, "admin"),
            ("PUT", re.compile(r"^/api/v1/admin/users/(?P<sub>[^/]+)$"), self.admin_user, "admin"),
            ("GET", re.compile(r"^/api/v1/admin/usage$"), self.admin_usage, "admin"),
            ("GET", re.compile(r"^/api/v1/admin/sync-status$"), self.admin_sync_status, "admin"),
        ]

    # ---------- dispatch ----------

    def handle(self, event: dict[str, Any]) -> dict[str, Any]:
        headers = {str(k).lower(): str(v) for k, v in (event.get("headers") or {}).items()}
        supplied = headers.get("x-correlation-id", "")
        cid = supplied if _CORR.match(supplied) else uuid.uuid4().hex
        http = (event.get("requestContext") or {}).get("http") or {}
        method = str(http.get("method") or event.get("httpMethod") or "GET").upper()
        path = re.sub(r"/+$", "", str(event.get("rawPath") or event.get("path") or "/")) or "/"
        try:
            body: Any = None
            if method in ("POST", "PUT"):
                raw = event.get("body") or ""
                if event.get("isBase64Encoded"):
                    raw = base64.b64decode(raw).decode("utf-8", "replace")
                if len(raw.encode()) > MAX_BODY_BYTES:
                    return _json(413, {"error": {"code": "payload_too_large", "message": "Request body too large", "correlationId": cid}}, cid)
                try:
                    body = json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    raise BadRequest("Body must be valid JSON") from None
            req = Request(method, path, dict(event.get("queryStringParameters") or {}), headers, body, cid, domain=(event.get("requestContext") or {}).get("domainName"))

            matched = None
            path_known = False
            for m, pattern, fn, auth in self.routes:
                hit = pattern.match(path)
                if hit:
                    path_known = True
                    if m == method:
                        matched = (fn, auth, hit.groupdict())
                        break
            if not matched:
                if path_known:
                    return _json(405, {"error": {"code": "method_not_allowed", "message": "Method not allowed", "correlationId": cid}}, cid)
                raise NotFound("Unknown endpoint")
            fn, auth, params = matched
            if auth != "none":
                req.identity = self.d.verifier.verify(headers.get("authorization"))
                if auth == "admin":
                    self.d.verifier.require_admin(req.identity, self.d.settings.admin_group)
            status, payload = fn(req, **params)
            if isinstance(payload, MapAsset):
                return _binary(payload, cid)
            return _json(status, payload, cid)
        except ApiError as e:
            if e.status >= 500:
                metrics.emit("Api5xx", 1)
                log("api_error", correlationId=cid, code=e.code, path=path)
            return _json(e.status, e.body(cid), cid, e.headers)
        except Exception as e:  # never leak internals to the browser
            log("unhandled_error", correlationId=cid, error=type(e).__name__, path=path)
            return _json(500, {"error": {"code": "internal_error", "message": "Something went wrong.", "correlationId": cid}}, cid)

    # ---------- handlers ----------

    def health(self, req: Request):
        return 200, {"status": "ok", "version": VERSION, "mockMode": self.d.settings.mock_mode, "correlationId": req.correlation_id}

    def _limits(self, req: Request) -> QuotaLimits:
        return self.d.ledger.effective(req.identity.sub).limits  # type: ignore[union-attr]

    def _geocode_gate(self, sub: str, limits: QuotaLimits):
        """Called only on a cache miss, right before a paid geocode: spends one unit of the user's and the pilot's budget."""
        def allow() -> bool:
            return self.d.ledger.try_count_event(sub, "geocode", limits.geocodes_per_user_day) and self.d.ledger.try_count_event(
                "__app__", "geocode", limits.geocodes_per_app_day
            )

        return allow

    def search(self, req: Request):
        eff = self.d.ledger.effective(req.identity.sub)  # type: ignore[union-attr]
        if eff.disabled:
            raise Forbidden("Pilot access is disabled for this account.")
        self.d.ledger.count_event(req.identity.sub, "search", eff.limits.searches_per_user_day)  # type: ignore[union-attr]
        sr = _validate(SearchRequest, req.body)
        return 200, self.d.search.search(sr, req.correlation_id, self._geocode_gate(req.identity.sub, eff.limits))  # type: ignore[union-attr]

    def get_resource(self, req: Request, id: str):
        if not _ID.match(id):
            raise BadRequest("Invalid resource id")
        view = self.d.search.get(id)
        return 200, {"resource": view.model_dump(mode="json"), "correlationId": req.correlation_id}

    def route(self, req: Request):
        eff = self.d.ledger.effective(req.identity.sub)  # type: ignore[union-attr]
        if eff.disabled:
            raise Forbidden("Pilot access is disabled for this account.")
        zip_code, rid = req.query.get("fromZip", ""), req.query.get("toResourceId", "")
        mode = req.query.get("mode", "Car")
        if not _ZIP.match(zip_code) or not _ID.match(rid) or mode not in ("Car", "Pedestrian"):
            raise BadRequest("fromZip (5 digits), toResourceId and mode (Car|Pedestrian) are required")
        target = self.d.search.get(rid)
        if target.latitude is None or target.longitude is None:
            raise BadRequest("This provider has no map location, so a route cannot be calculated.")
        origin = self.d.search._origin(zip_code, self._geocode_gate(req.identity.sub, eff.limits))  # type: ignore[union-attr]
        if not origin.geocoded or self.d.location is None:
            raise ServiceUnavailable("Route information is unavailable right now.")
        self.d.ledger.count_event(req.identity.sub, "routes", eff.limits.routes_per_user_day)  # type: ignore[union-attr]
        self.d.ledger.count_event("__app__", "routes", eff.limits.routes_per_app_day)
        try:
            summary = self.d.location.route((origin.latitude, origin.longitude), (target.latitude, target.longitude), mode)  # type: ignore[arg-type]
        except LocationUnavailable:
            raise ServiceUnavailable("Route information is unavailable right now.") from None
        if summary is None:
            raise ServiceUnavailable("No route could be found.")
        return 200, {
            "distanceMiles": summary.distance_miles, "durationMinutes": summary.duration_minutes, "travelMode": summary.travel_mode,
            "origin": {"zipCode": zip_code, "latitude": origin.latitude, "longitude": origin.longitude},
            "destination": {"id": target.id, "name": target.name},
            "provider": "Amazon Location Service", "correlationId": req.correlation_id,
        }

    def assistant(self, req: Request):
        ar = _validate(AssistantRequest, req.body)
        return 200, self.d.pipeline.handle(req.identity, ar, req.correlation_id)  # type: ignore[arg-type]

    def me_usage(self, req: Request):
        return 200, build_usage(self.d.ledger, req.identity.sub, req.correlation_id)  # type: ignore[union-attr]

    # ---------- map proxy (no browser-side AWS key; see location/maps.py) ----------

    def _maps(self, req: Request) -> MapsClient:
        eff = self.d.ledger.effective(req.identity.sub)  # type: ignore[union-attr]
        if eff.disabled:
            raise Forbidden("Pilot access is disabled for this account.")
        self.d.ledger.count_event(req.identity.sub, "map", eff.limits.map_requests_per_user_day)  # type: ignore[union-attr]
        self.d.ledger.count_event("__app__", "map", eff.limits.map_requests_per_app_day)
        if self.d.maps is None:
            raise ServiceUnavailable("The map service is unavailable right now.")
        return self.d.maps

    def map_style(self, req: Request):
        scheme = req.query.get("scheme", "Light")
        return 200, self._maps(req).style(scheme, public_base(req.domain))

    def map_tile(self, req: Request, tileset: str, z: str, x: str, y: str):
        return 200, self._maps(req).tile(tileset, z, x, y)

    def map_glyphs(self, req: Request, fontstack: str, rng: str):
        from urllib.parse import unquote

        return 200, self._maps(req).glyphs(unquote(fontstack), rng)

    def map_sprite(self, req: Request, scheme: str, variant: str, file: str):
        return 200, self._maps(req).sprite(scheme, variant, file)

    def sync_status(self, req: Request):
        states = self.d.store.list_sync_states(list(SYNC_SOURCES))
        out = [{k: s.get(k) for k in ("sourceId", "status", "lastSuccessAt", "lastFullSyncAt")} for s in states]
        return 200, {"sources": out, "correlationId": req.correlation_id}

    # ---------- admin ----------

    def admin_quotas(self, req: Request):
        overrides = (req.body or {}).get("overrides") if isinstance(req.body, dict) else None
        if not isinstance(overrides, dict) or not overrides:
            raise BadRequest("Provide a non-empty 'overrides' object")
        known = self.d.ledger.set_quota_overrides(overrides, req.identity.sub)  # type: ignore[union-attr]
        log("admin_quotas_changed", correlationId=req.correlation_id, keys=sorted(known))
        return 200, {"overrides": known, "correlationId": req.correlation_id}

    def admin_switch(self, req: Request):
        enabled = (req.body or {}).get("assistantEnabled") if isinstance(req.body, dict) else None
        if not isinstance(enabled, bool):
            raise BadRequest("'assistantEnabled' must be true or false")
        self.d.ledger.set_switch(enabled, req.identity.sub)  # type: ignore[union-attr]
        log("admin_switch_changed", correlationId=req.correlation_id, enabled=enabled)
        return 200, {"assistantEnabled": enabled, "correlationId": req.correlation_id}

    def admin_user(self, req: Request, sub: str):
        if not _SUB.match(sub):
            raise BadRequest("Invalid user id")
        body = req.body if isinstance(req.body, dict) else {}
        disabled, overrides = body.get("disabled"), body.get("overrides")
        if disabled is not None and not isinstance(disabled, bool):
            raise BadRequest("'disabled' must be true or false")
        if overrides is not None and not isinstance(overrides, dict):
            raise BadRequest("'overrides' must be an object")
        if disabled is None and overrides is None:
            raise BadRequest("Provide 'disabled' and/or 'overrides'")
        profile = self.d.ledger.set_user_profile(sub, disabled=disabled, overrides=overrides, actor=req.identity.sub)  # type: ignore[union-attr]
        log("admin_user_changed", correlationId=req.correlation_id, target=sub, disabled=profile["disabled"])
        return 200, {**profile, "correlationId": req.correlation_id}

    def admin_usage(self, req: Request):
        day = req.query.get("day")
        if day is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            raise BadRequest("day must be YYYY-MM-DD")
        from navigator.quota.pricing import pricing_version

        return 200, {**self.d.ledger.spend_summary(day), "pricingVersion": pricing_version(), "note": "Estimated spend; see docs/cost-model.md", "correlationId": req.correlation_id}

    def admin_sync_status(self, req: Request):
        return 200, {"sources": self.d.store.list_sync_states(list(SYNC_SOURCES)), "correlationId": req.correlation_id}


# ---------- Lambda wiring ----------

_APP: App | None = None


def build_app(settings: Settings | None = None) -> App:
    from navigator.gateway.classifier import BedrockClassifier
    from navigator.gateway.invoker import AgentCoreInvoker, MockInvoker
    from navigator.location.client import CachedZipGeocoder

    s = settings or Settings()
    store = DataStore(s.data_table, s.region)
    ledger = UsageLedger(s.usage_table, s.region)
    location = None if s.mock_mode else LocationClient(s.region)
    maps = None if s.mock_mode else MapsClient(s.region)
    search = SearchService(store, CachedZipGeocoder(store, location), s)
    invoker = MockInvoker() if s.mock_mode else AgentCoreInvoker(s.agent_region, s.agent_runtime_arn)
    classifier = BedrockClassifier(s.classifier_model_id, s.region)
    pipeline = AssistantPipeline(ledger, invoker, classifier, s)
    return App(Deps(s, JwtVerifier(s.cognito_user_pool_id, s.cognito_client_id), store, ledger, search, pipeline, location, maps))


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    global _APP
    if _APP is None:
        _APP = build_app()
    return _APP.handle(event)
