"""boto3 <-> DynamoDB value conversion (floats are not accepted natively; numbers come back as Decimal)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def to_ddb(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: to_ddb(v) for k, v in value.items() if v is not None}  # DynamoDB: omit nulls
    if isinstance(value, (list, tuple)):
        return [to_ddb(v) for v in value]
    return value


def from_ddb(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: from_ddb(v) for k, v in value.items()}
    if isinstance(value, list):
        return [from_ddb(v) for v in value]
    if isinstance(value, set):
        return sorted(from_ddb(v) for v in value)
    return value
