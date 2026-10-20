"""Structured logging. Never log tokens, raw queries, emails or other personal data."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

_LOGGER = logging.getLogger("navigator")
if not _LOGGER.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    _LOGGER.addHandler(handler)
    _LOGGER.setLevel(logging.INFO)
    _LOGGER.propagate = False

_FORBIDDEN_KEYS = {"authorization", "token", "query", "message", "email", "password", "api_key", "apikey"}


def log(event: str, **fields: Any) -> None:
    safe = {k: v for k, v in fields.items() if k.lower() not in _FORBIDDEN_KEYS}
    _LOGGER.info(json.dumps({"event": event, **safe}, default=str))
