"""DynamoDB-backed usage ledger with atomic reservations.

Flow for one AI request:
  reserve()  -> ONE TransactWriteItems that atomically (a) bumps the user's daily / monthly / application
                counters only if each limit still holds, (b) records the request under its idempotency key
                (fails if it already exists), and (c) takes a concurrency slot. All-or-nothing.
  settle()   -> ONE transaction: replace the estimate by the actual tokens, add estimated spend, store the
                (small) response for safe replays, free the slot.
  release()  -> refund an unused reservation when the request failed before any model was called.

Honest limits: token figures are an estimate reserved up front and reconciled with usage the runtime
reports. Bedrock offers no per-user hard cap, so a single request can exceed its reservation; it is bounded
by max_model_invocations x output caps and max_tokens_per_request, and the NEXT request is refused once
settled usage reaches the limit. Everything fails closed: if the ledger cannot be reached the request is
refused (503), never allowed through.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import boto3
from botocore.exceptions import ClientError

from navigator.config import QuotaLimits
from navigator.errors import Conflict, QuotaExceeded, ServiceUnavailable
from navigator.store.ddb import from_ddb, to_ddb

DAY_TTL = 35 * 86400
MONTH_TTL = 70 * 86400
REQ_TTL = 2 * 86400
MAX_CACHED_RESPONSE_BYTES = 12_000
MAX_SLOTS = 5
USD_MICRO = 1_000_000


def _day(now: float) -> str:
    return datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%d")


def _month(now: float) -> str:
    return datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m")


def next_day_reset(now: float) -> str:
    d = datetime.fromtimestamp(now, timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def next_month_reset(now: float) -> str:
    d = datetime.fromtimestamp(now, timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    d = (d + timedelta(days=32)).replace(day=1)
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Reservation:
    sub: str
    request_key: str
    slot: int
    est_tokens: int
    day: str
    month: str
    now: float


@dataclass(frozen=True)
class UsageSnapshot:
    daily_requests: int
    monthly_requests: int
    daily_tokens: int
    app_daily_requests: int
    limits: QuotaLimits
    now: float


@dataclass(frozen=True)
class Effective:
    limits: QuotaLimits
    disabled: bool
    assistant_enabled: bool
    approved: bool = False  # only meaningful for federated (e.g. Google) users; admin-created users never need it


class UsageLedger:
    def __init__(self, table_name: str, region: str | None = None, resource: Any = None, clock: Callable[[], float] = time.time):
        ddb = resource or boto3.resource("dynamodb", region_name=region)
        self.table = ddb.Table(table_name)
        self._ddb = ddb
        self._client = ddb.meta.client
        self.table_name = table_name
        self._clock = clock

    # ---------- keys ----------

    @staticmethod
    def _k(pk: str, sk: str = "CTR") -> dict[str, str]:
        return {"PK": pk, "SK": sk}

    def _tx(self, items: list[dict[str, Any]]) -> None:
        self._client.transact_write_items(TransactItems=items)

    @staticmethod
    def _ser(value: Any) -> Any:
        """The resource's client serializes native Python values itself; ints/strs/Decimals pass through."""
        return to_ddb(value)

    # ---------- effective configuration (admin overrides) ----------

    def effective(self, sub: str) -> Effective:
        keys = [self._k("CONFIG", "QUOTAS"), self._k("CONFIG", "SWITCH"), self._k(f"USER#{sub}", "PROFILE")]
        try:
            resp = self._ddb.batch_get_item(RequestItems={self.table_name: {"Keys": keys, "ConsistentRead": True}})
        except ClientError as e:
            raise ServiceUnavailable("Usage service unavailable") from e
        by_sk = {(i["PK"], i["SK"]): from_ddb(i) for i in resp["Responses"].get(self.table_name, [])}
        quotas = by_sk.get(("CONFIG", "QUOTAS"), {}).get("overrides", {})
        switch = by_sk.get(("CONFIG", "SWITCH"), {})
        profile = by_sk.get((f"USER#{sub}", "PROFILE"), {})
        limits = QuotaLimits.with_overrides({**quotas, **profile.get("overrides", {})})
        return Effective(limits, bool(profile.get("disabled", False)), bool(switch.get("assistantEnabled", True)), bool(profile.get("approved", False)))

    # ---------- reserve ----------

    def reserve(self, sub: str, request_key: str, limits: QuotaLimits, est_tokens: int | None = None) -> Reservation:
        now = self._clock()
        est = est_tokens if est_tokens is not None else limits.reserve_tokens_per_request
        day, month = _day(now), _month(now)
        slots = max(1, min(limits.max_concurrent_per_user, MAX_SLOTS))
        last_error: Exception | None = None
        for slot in range(slots):
            try:
                self._reserve_tx(sub, request_key, limits, est, day, month, now, slot)
                return Reservation(sub, request_key, slot, est, day, month, now)
            except _SlotBusy as e:
                last_error = e
                continue
        raise QuotaExceeded(
            "You already have a request in progress. Please wait for it to finish.",
            details={"reason": "concurrent_request", "limit": slots},
            headers={"Retry-After": "5"},
        ) from last_error

    def _reserve_tx(self, sub, key, limits, est, day, month, now, slot) -> None:
        ttl_d, ttl_m = int(now) + DAY_TTL, int(now) + MONTH_TTL
        items = [
            {  # 0: user daily
                "Update": {
                    "TableName": self.table_name,
                    "Key": self._ser(self._k(f"U#{sub}#D#{day}")),
                    "UpdateExpression": "ADD reqs :one, tokens :est SET #ttl = :ttl",
                    "ConditionExpression": "(attribute_not_exists(reqs) OR reqs < :dreq) AND (attribute_not_exists(tokens) OR tokens <= :tokmax)",
                    "ExpressionAttributeNames": {"#ttl": "ttl"},
                    "ExpressionAttributeValues": self._ser(
                        {":one": 1, ":est": est, ":ttl": ttl_d, ":dreq": limits.requests_per_user_day,
                         ":tokmax": limits.est_tokens_per_user_day - est}
                    ),
                    "ReturnValuesOnConditionCheckFailure": "ALL_OLD",
                }
            },
            {  # 1: user monthly
                "Update": {
                    "TableName": self.table_name,
                    "Key": self._ser(self._k(f"U#{sub}#M#{month}")),
                    "UpdateExpression": "ADD reqs :one SET #ttl = :ttl",
                    "ConditionExpression": "attribute_not_exists(reqs) OR reqs < :mreq",
                    "ExpressionAttributeNames": {"#ttl": "ttl"},
                    "ExpressionAttributeValues": self._ser({":one": 1, ":ttl": ttl_m, ":mreq": limits.requests_per_user_month}),
                }
            },
            {  # 2: application daily
                "Update": {
                    "TableName": self.table_name,
                    "Key": self._ser(self._k(f"G#D#{day}")),
                    "UpdateExpression": "ADD reqs :one, tokens :est SET #ttl = :ttl",
                    "ConditionExpression": "attribute_not_exists(reqs) OR reqs < :greq",
                    "ExpressionAttributeNames": {"#ttl": "ttl"},
                    "ExpressionAttributeValues": self._ser({":one": 1, ":est": est, ":ttl": ttl_d, ":greq": limits.requests_per_app_day}),
                }
            },
            {  # 3: idempotency record
                "Put": {
                    "TableName": self.table_name,
                    "Item": self._ser(
                        {"PK": f"REQ#{sub}#{key}", "SK": "R", "status": "reserved", "est": est, "day": day, "month": month,
                         "createdAt": int(now), "ttl": int(now) + REQ_TTL}
                    ),
                    "ConditionExpression": "attribute_not_exists(PK)",
                }
            },
            {  # 4: concurrency slot (auto-expires if a run dies)
                "Put": {
                    "TableName": self.table_name,
                    "Item": self._ser(
                        {"PK": f"U#{sub}", "SK": f"SLOT#{slot}", "reqKey": key,
                         "expiresAt": int(now) + limits.request_timeout_seconds + 30, "ttl": int(now) + 3600}
                    ),
                    "ConditionExpression": "attribute_not_exists(PK) OR expiresAt < :now",
                    "ExpressionAttributeValues": self._ser({":now": int(now)}),
                }
            },
        ]
        try:
            self._tx(items)
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code == "TransactionCanceledException":
                reasons = e.response.get("CancellationReasons", [])
                self._raise_for_reasons(reasons, sub, key, limits, day, now)
            raise ServiceUnavailable("Usage service unavailable") from e

    def _raise_for_reasons(self, reasons: list[dict[str, Any]], sub, key, limits, day, now) -> None:
        failed = [i for i, r in enumerate(reasons) if r.get("Code") == "ConditionalCheckFailed"]
        if 3 in failed:  # this idempotency key was already used
            raise Conflict("This request is already being processed or was already completed.", details={"reason": "duplicate_request"})
        if 0 in failed:
            snap = self.snapshot(sub, limits)
            tokens_hit = snap.daily_requests < limits.requests_per_user_day
            raise QuotaExceeded(
                "Daily token budget reached. Try again after the reset." if tokens_hit else "Daily request limit reached.",
                details={"reason": "daily_tokens" if tokens_hit else "daily_requests", "resetsAt": next_day_reset(now)},
                headers={"Retry-After": str(max(1, int(_reset_epoch(next_day_reset(now)) - now)))},
            )
        if 1 in failed:
            raise QuotaExceeded(
                "Monthly request limit reached.",
                details={"reason": "monthly_requests", "resetsAt": next_month_reset(now)},
                headers={"Retry-After": str(max(1, int(_reset_epoch(next_month_reset(now)) - now)))},
            )
        if 2 in failed:
            raise QuotaExceeded(
                "The pilot has reached its daily capacity. Please try again tomorrow.",
                details={"reason": "application_daily", "resetsAt": next_day_reset(now)},
                headers={"Retry-After": str(max(1, int(_reset_epoch(next_day_reset(now)) - now)))},
            )
        if 4 in failed:
            raise _SlotBusy()
        raise ServiceUnavailable("Usage service unavailable")

    # ---------- settle / release ----------

    def settle(self, r: Reservation, *, input_tokens: int, output_tokens: int, usd: float | None,
               count_request: bool = True, response_json: str | None = None, status: str = "completed") -> None:
        actual = max(0, int(input_tokens) + int(output_tokens))
        delta = actual - r.est_tokens
        micro = int(round((usd or 0) * USD_MICRO))
        req_delta = 0 if count_request else -1
        cached = response_json if response_json is not None and len(response_json.encode()) <= MAX_CACHED_RESPONSE_BYTES else None

        def upd(pk, token_delta, with_reqs=True):
            expr = "ADD tokens :d, usdMicro :u, inTok :i, outTok :o" + (", reqs :rd" if with_reqs and req_delta else "")
            vals = {":d": token_delta, ":u": micro, ":i": int(input_tokens), ":o": int(output_tokens)}
            if with_reqs and req_delta:
                vals[":rd"] = req_delta
            return {"Update": {"TableName": self.table_name, "Key": self._ser(self._k(pk)),
                               "UpdateExpression": expr, "ExpressionAttributeValues": self._ser(vals)}}

        req_vals: dict[str, Any] = {":s": status, ":a": actual, ":u": micro}
        req_expr = "SET #st = :s, actual = :a, usdMicro = :u"
        if cached is not None:
            req_expr += ", cachedResponse = :c"
            req_vals[":c"] = cached
        items = [
            upd(f"U#{r.sub}#D#{r.day}", delta),  # daily/global counters held the estimate: apply the delta
            upd(f"U#{r.sub}#M#{r.month}", actual),  # the monthly counter never held an estimate: add actuals
            upd(f"G#D#{r.day}", delta),
            {"Update": {"TableName": self.table_name, "Key": self._ser({"PK": f"REQ#{r.sub}#{r.request_key}", "SK": "R"}),
                        "UpdateExpression": req_expr, "ExpressionAttributeNames": {"#st": "status"},
                        "ExpressionAttributeValues": self._ser(req_vals)}},
            {"Delete": {"TableName": self.table_name, "Key": self._ser({"PK": f"U#{r.sub}", "SK": f"SLOT#{r.slot}"}),
                        "ConditionExpression": "attribute_not_exists(PK) OR reqKey = :k",
                        "ExpressionAttributeValues": self._ser({":k": r.request_key})}},
        ]
        try:
            self._tx(items)
        except ClientError as e:
            raise ServiceUnavailable("Usage settlement failed") from e

    def release(self, r: Reservation) -> None:
        """Atomically undo a reservation for a request that never produced billable work.

        Reverses the counters, frees the slot, and DELETES the idempotency record so the client's retry with
        the same key is allowed (it was never charged).
        """
        ttl_free = {"TableName": self.table_name}

        def rev(pk, tokens):
            expr = "ADD reqs :m" + (", tokens :t" if tokens else "")
            vals = {":m": -1, **({":t": -r.est_tokens} if tokens else {})}
            return {"Update": {**ttl_free, "Key": self._ser(self._k(pk)), "UpdateExpression": expr,
                               "ExpressionAttributeValues": self._ser(vals)}}

        items = [
            rev(f"U#{r.sub}#D#{r.day}", True),
            rev(f"U#{r.sub}#M#{r.month}", False),
            rev(f"G#D#{r.day}", True),
            {"Delete": {**ttl_free, "Key": self._ser({"PK": f"REQ#{r.sub}#{r.request_key}", "SK": "R"}),
                        "ConditionExpression": "#st = :res", "ExpressionAttributeNames": {"#st": "status"},
                        "ExpressionAttributeValues": self._ser({":res": "reserved"})}},
            {"Delete": {**ttl_free, "Key": self._ser({"PK": f"U#{r.sub}", "SK": f"SLOT#{r.slot}"})}},
        ]
        try:
            self._tx(items)
        except ClientError as e:
            raise ServiceUnavailable("Usage release failed") from e

    def cached_response(self, sub: str, key: str) -> str | None:
        item = self.table.get_item(Key={"PK": f"REQ#{sub}#{key}", "SK": "R"}).get("Item")
        if item and item.get("status") == "completed":
            return item.get("cachedResponse")
        return None

    # ---------- cheap per-user event counters (deterministic rejections, route lookups) ----------

    def count_event(self, sub: str, kind: str, limit: int) -> None:
        """Bounded daily counter for events that cost little but must not be unlimited."""
        now = self._clock()
        try:
            self.table.update_item(
                Key=self._k(f"U#{sub}#D#{_day(now)}"),
                UpdateExpression=f"ADD ev_{kind} :one SET #ttl = :ttl",
                ConditionExpression=f"attribute_not_exists(ev_{kind}) OR ev_{kind} < :max",
                ExpressionAttributeNames={"#ttl": "ttl"},
                ExpressionAttributeValues={":one": 1, ":ttl": int(now) + DAY_TTL, ":max": limit},
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise QuotaExceeded(
                    "Daily limit reached for this action.", details={"reason": kind, "resetsAt": next_day_reset(now)},
                    headers={"Retry-After": str(max(1, int(_reset_epoch(next_day_reset(now)) - now)))},
                ) from e
            raise ServiceUnavailable("Usage service unavailable") from e

    def try_count_event(self, sub: str, kind: str, limit: int) -> bool:
        """Like count_event but returns False instead of raising, for callers that degrade gracefully.
        Fails closed: an unreachable ledger also returns False (the paid call is simply skipped)."""
        try:
            self.count_event(sub, kind, limit)
            return True
        except (QuotaExceeded, ServiceUnavailable):
            return False

    def count_rejection(self, sub: str, limits: QuotaLimits) -> None:
        self.count_event(sub, "rejections", limits.rejections_per_user_day)

    # ---------- read ----------

    def snapshot(self, sub: str, limits: QuotaLimits) -> UsageSnapshot:
        now = self._clock()
        keys = [self._k(f"U#{sub}#D#{_day(now)}"), self._k(f"U#{sub}#M#{_month(now)}"), self._k(f"G#D#{_day(now)}")]
        try:
            resp = self._ddb.batch_get_item(RequestItems={self.table_name: {"Keys": keys, "ConsistentRead": True}})
        except ClientError as e:
            raise ServiceUnavailable("Usage service unavailable") from e
        by_pk = {i["PK"]: from_ddb(i) for i in resp["Responses"].get(self.table_name, [])}
        d, m, g = by_pk.get(keys[0]["PK"], {}), by_pk.get(keys[1]["PK"], {}), by_pk.get(keys[2]["PK"], {})
        return UsageSnapshot(int(d.get("reqs", 0)), int(m.get("reqs", 0)), int(d.get("tokens", 0)), int(g.get("reqs", 0)), limits, now)

    def spend_summary(self, day: str | None = None) -> dict[str, Any]:
        """Aggregate application usage and estimated spend for a UTC day (admin dashboards)."""
        day = day or _day(self._clock())
        item = from_ddb(self.table.get_item(Key=self._k(f"G#D#{day}")).get("Item") or {})
        return {
            "day": day, "requests": int(item.get("reqs", 0)), "tokens": int(item.get("tokens", 0)),
            "inputTokens": int(item.get("inTok", 0)), "outputTokens": int(item.get("outTok", 0)),
            "estimatedUsd": round(int(item.get("usdMicro", 0)) / USD_MICRO, 6),
        }

    # ---------- admin ----------

    def set_quota_overrides(self, overrides: dict[str, int], actor: str) -> dict[str, Any]:
        clean = QuotaLimits.with_overrides(overrides)  # validates keys / ranges
        known = {k: getattr(clean, k) for k in overrides if hasattr(clean, k) and isinstance(overrides[k], (int, float)) and not isinstance(overrides[k], bool) and overrides[k] >= 0}
        self.table.put_item(Item=to_ddb({**self._k("CONFIG", "QUOTAS"), "overrides": known, "updatedBy": actor, "updatedAt": int(self._clock())}))
        return known

    def set_switch(self, assistant_enabled: bool, actor: str) -> None:
        self.table.put_item(Item=to_ddb({**self._k("CONFIG", "SWITCH"), "assistantEnabled": assistant_enabled, "updatedBy": actor, "updatedAt": int(self._clock())}))

    def set_user_profile(self, sub: str, *, disabled: bool | None, overrides: dict[str, int] | None, actor: str, approved: bool | None = None) -> dict[str, Any]:
        cur = from_ddb(self.table.get_item(Key=self._k(f"USER#{sub}", "PROFILE")).get("Item") or {})
        new_overrides = cur.get("overrides", {}) if overrides is None else {
            k: int(v) for k, v in overrides.items()
            if k in QuotaLimits.__dataclass_fields__ and isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0
        }
        profile = {**self._k(f"USER#{sub}", "PROFILE"), "disabled": cur.get("disabled", False) if disabled is None else disabled,
                   "approved": cur.get("approved", False) if approved is None else approved,
                   "overrides": new_overrides, "updatedBy": actor, "updatedAt": int(self._clock())}
        self.table.put_item(Item=to_ddb(profile))
        return {"disabled": profile["disabled"], "approved": profile["approved"], "overrides": new_overrides}


class _SlotBusy(Exception):
    pass


def _reset_epoch(iso_ts: str) -> float:
    return datetime.strptime(iso_ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
