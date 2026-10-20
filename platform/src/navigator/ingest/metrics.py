"""CloudWatch Embedded Metric Format lines (printed to stdout; no PutMetricData call, no extra IAM)."""

from __future__ import annotations

import json
import time
from typing import Any

NAMESPACE = "Navigator"


def emit(name: str, value: float, unit: str = "Count", **dimensions: str) -> None:
    line: dict[str, Any] = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": NAMESPACE,
                    "Dimensions": [list(dimensions.keys())] if dimensions else [[]],
                    "Metrics": [{"Name": name, "Unit": unit}],
                }
            ],
        },
        name: value,
        **dimensions,
    }
    print(json.dumps(line))
