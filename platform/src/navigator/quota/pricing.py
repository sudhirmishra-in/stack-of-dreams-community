"""Versioned model pricing used ONLY for estimated-spend tracking.

The file `pricing.json` is configuration, not an authority: prices change, regions differ, and cross-region
inference profiles can be priced differently. Always verify against the AWS Bedrock pricing page and bump
`version` when updating. Unknown models yield no estimate (never a guess).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

PRICING_PATH = Path(__file__).with_name("pricing.json")


@lru_cache(maxsize=1)
def load_pricing(path: str | None = None) -> dict[str, Any]:
    return json.loads(Path(path or PRICING_PATH).read_text())


def estimate_usd(model_id: str, input_tokens: int, output_tokens: int, pricing: dict[str, Any] | None = None) -> float | None:
    table = (pricing or load_pricing())["models"]
    entry = table.get(model_id) or table.get(model_id.removeprefix("us.").removeprefix("global."))
    if not entry:
        return None
    return (input_tokens / 1000) * entry["inputPer1kUsd"] + (output_tokens / 1000) * entry["outputPer1kUsd"]


def pricing_version() -> str:
    return str(load_pricing().get("version", "unknown"))
