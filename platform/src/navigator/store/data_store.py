"""Data-table repository: resources, inventory, activity, sync state, geocode cache."""

from __future__ import annotations

from typing import Any, Iterator

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from navigator.models import ActivityRecord, InventoryRecord, ResourceRecord
from navigator.util import iso

from .ddb import from_ddb, to_ddb


class VersionConflict(Exception):
    """Another writer changed the item between our read and write."""


def _zip_key(rec: ResourceRecord) -> str:
    return rec.zipCode or "_____"


class DataStore:
    def __init__(self, table_name: str, region: str | None = None, resource: Any = None):
        ddb = resource or boto3.resource("dynamodb", region_name=region)
        self.table = ddb.Table(table_name)
        self._ddb = ddb
        self.table_name = table_name

    # ---------- resources ----------

    def get_resource(self, resource_id: str) -> tuple[ResourceRecord, int] | None:
        item = self.table.get_item(Key={"PK": f"RES#{resource_id}", "SK": "META"}).get("Item")
        if not item:
            return None
        data = from_ddb(item)
        return ResourceRecord.model_validate(data["record"]), int(data.get("version", 0))

    def put_resource(self, rec: ResourceRecord, expected_version: int | None) -> int:
        """Optimistic-locked upsert. `expected_version=None` means "must not exist yet"."""
        new_version = (expected_version or 0) + 1
        item = {
            "PK": f"RES#{rec.id}",
            "SK": "META",
            "gsi1pk": f"NS#{rec.namespace}",
            "gsi1sk": f"Z#{_zip_key(rec)}#{rec.id}",
            "gsi2pk": f"FP#{rec.fingerprint}",
            "gsi2sk": f"RES#{rec.id}",
            "version": new_version,
            "active": rec.active,
            "updatedAt": iso(),
            "record": rec.model_dump(mode="json"),
        }
        kwargs: dict[str, Any] = {"Item": to_ddb(item)}
        if expected_version is None:
            kwargs["ConditionExpression"] = "attribute_not_exists(PK)"
        else:
            kwargs["ConditionExpression"] = "#v = :v"
            kwargs["ExpressionAttributeNames"] = {"#v": "version"}
            kwargs["ExpressionAttributeValues"] = {":v": expected_version}
        try:
            self.table.put_item(**kwargs)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise VersionConflict(rec.id) from e
            raise
        return new_version

    def iter_namespace(self, namespace: str, include_inactive: bool = False) -> Iterator[ResourceRecord]:
        kwargs: dict[str, Any] = {
            "IndexName": "gsi1",
            "KeyConditionExpression": Key("gsi1pk").eq(f"NS#{namespace}"),
        }
        while True:
            resp = self.table.query(**kwargs)
            for item in resp.get("Items", []):
                if include_inactive or item.get("active", True):
                    yield ResourceRecord.model_validate(from_ddb(item["record"]))
            if "LastEvaluatedKey" not in resp:
                return
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    def find_by_fingerprint(self, fingerprint: str) -> list[str]:
        resp = self.table.query(IndexName="gsi2", KeyConditionExpression=Key("gsi2pk").eq(f"FP#{fingerprint}"))
        return [it["PK"].removeprefix("RES#") for it in resp.get("Items", [])]

    # ---------- inventory ----------

    def put_inventory(self, inv: InventoryRecord) -> None:
        self.table.put_item(
            Item=to_ddb({"PK": f"RES#{inv.resourceId}", "SK": f"INV#{inv.itemType}", "record": inv.model_dump(mode="json")})
        )

    def get_inventory(self, resource_ids: list[str]) -> dict[str, dict[str, InventoryRecord]]:
        """BatchGet the three inventory item types for each resource (callers cap the id list)."""
        out: dict[str, dict[str, InventoryRecord]] = {rid: {} for rid in resource_ids}
        keys = [{"PK": f"RES#{rid}", "SK": f"INV#{t}"} for rid in resource_ids for t in ("baby_formula", "groceries", "diapers")]
        for i in range(0, len(keys), 100):
            batch = {self.table_name: {"Keys": keys[i : i + 100]}}
            while batch:
                resp = self._ddb.batch_get_item(RequestItems=batch)
                for item in resp["Responses"].get(self.table_name, []):
                    inv = InventoryRecord.model_validate(from_ddb(item["record"]))
                    out[inv.resourceId][inv.itemType] = inv
                batch = resp.get("UnprocessedKeys") or {}
        return out

    # ---------- citywide activity ----------

    def put_activity(self, rec: ActivityRecord) -> None:
        # Key includes the period, so re-syncing the same quarter overwrites it (idempotent).
        self.table.put_item(
            Item=to_ddb(
                {
                    "PK": f"ACT#{rec.sourceId}#{rec.program}",
                    "SK": f"P#{rec.periodEnd}",
                    "record": rec.model_dump(mode="json"),
                    "syncedAt": iso(),
                }
            )
        )

    def list_activity(self, source_id: str, program: str, limit: int = 8) -> list[ActivityRecord]:
        resp = self.table.query(
            KeyConditionExpression=Key("PK").eq(f"ACT#{source_id}#{program}"), ScanIndexForward=False, Limit=limit
        )
        return [ActivityRecord.model_validate(from_ddb(i["record"])) for i in resp.get("Items", [])]

    # ---------- sync state ----------

    def get_sync_state(self, source_id: str) -> dict[str, Any]:
        item = self.table.get_item(Key={"PK": f"SYNC#{source_id}", "SK": "STATE"}).get("Item")
        return from_ddb(item) if item else {}

    def put_sync_state(self, source_id: str, state: dict[str, Any]) -> None:
        self.table.put_item(Item=to_ddb({**state, "PK": f"SYNC#{source_id}", "SK": "STATE"}))

    def put_sync_run(self, source_id: str, run: dict[str, Any], ttl_epoch: int) -> None:
        self.table.put_item(Item=to_ddb({**run, "PK": f"SYNC#{source_id}", "SK": f"RUN#{run['startedAt']}", "ttl": ttl_epoch}))

    def list_sync_states(self, source_ids: list[str]) -> list[dict[str, Any]]:
        return [s for s in (self.get_sync_state(sid) for sid in source_ids) if s]

    def acquire_sync_lock(self, source_id: str, now_epoch: int, ttl_seconds: int) -> bool:
        """Prevents overlapping runs for one source. The lock expires on its own if a run dies."""
        try:
            self.table.update_item(
                Key={"PK": f"SYNC#{source_id}", "SK": "STATE"},
                UpdateExpression="SET lockUntil = :u",
                ConditionExpression="attribute_not_exists(lockUntil) OR lockUntil < :now",
                ExpressionAttributeValues={":u": now_epoch + ttl_seconds, ":now": now_epoch},
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    def release_sync_lock(self, source_id: str) -> None:
        self.table.update_item(
            Key={"PK": f"SYNC#{source_id}", "SK": "STATE"}, UpdateExpression="REMOVE lockUntil"
        )

    def iter_source_ids(self, source_id: str, namespace: str = "real") -> Iterator[tuple[str, bool]]:
        """(resource id, active) for every record that lists `source_id` among its sources."""
        for rec in self.iter_namespace(namespace, include_inactive=True):
            if any(s.sourceId == source_id for s in rec.sources):
                yield rec.id, rec.active

    # ---------- geocode cache ----------

    def get_zip_geo(self, zip_code: str) -> dict[str, Any] | None:
        item = self.table.get_item(Key={"PK": f"ZIP#{zip_code}", "SK": "GEO"}).get("Item")
        return from_ddb(item) if item else None

    def put_zip_geo(self, zip_code: str, lat: float, lon: float, provider: str) -> None:
        self.table.put_item(
            Item=to_ddb({"PK": f"ZIP#{zip_code}", "SK": "GEO", "latitude": lat, "longitude": lon, "provider": provider, "cachedAt": iso()})
        )
