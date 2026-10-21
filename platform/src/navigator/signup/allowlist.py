"""The list of emails invited to sign up with an external identity provider (Google).

One DynamoDB item in the usage table (`CONFIG` / `ALLOWLIST`) holding a string set. Emails are stored lowercase.
Managed with scripts/allow_email.py; read by the Cognito pre sign-up Lambda."""

from __future__ import annotations

import re
from typing import Any

import boto3

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
KEY = {"PK": "CONFIG", "SK": "ALLOWLIST"}


def normalize(email: Any) -> str | None:
    """Lowercased, trimmed email, or None when it does not look like one."""
    if not isinstance(email, str):
        return None
    e = email.strip().lower()
    return e if len(e) <= 254 and _EMAIL.match(e) else None


class Allowlist:
    def __init__(self, table_name: str, region: str | None = None, resource: Any = None):
        self.table = (resource or boto3.resource("dynamodb", region_name=region)).Table(table_name)

    def _emails(self) -> set[str]:
        item = self.table.get_item(Key=KEY, ConsistentRead=True).get("Item") or {}
        return {str(e) for e in item.get("emails", set())}

    def contains(self, email: Any) -> bool:
        e = normalize(email)
        return e is not None and e in self._emails()

    def list(self) -> list[str]:
        return sorted(self._emails())

    def add(self, email: str) -> None:
        e = normalize(email)
        if e is None:
            raise ValueError("not a valid email address")
        self.table.update_item(Key=KEY, UpdateExpression="ADD emails :e", ExpressionAttributeValues={":e": {e}})

    def remove(self, email: str) -> None:
        e = normalize(email)
        if e is None:
            raise ValueError("not a valid email address")
        try:
            self.table.update_item(Key=KEY, UpdateExpression="DELETE emails :e", ExpressionAttributeValues={":e": {e}})
        except self.table.meta.client.exceptions.ClientError:
            # Deleting the last element removes the attribute; a missing item is fine too.
            pass
