"""Fixture-backed HTTP client: lets sync run offline (network blocked, tests, demos)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class FixtureHttp:
    def __init__(self, directory: str | Path):
        self.dir = Path(directory)

    def post_form_json(self, url: str, form: dict[str, str]) -> Any:
        return json.loads((self.dir / "overpass_nyc.json").read_text())

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        rows = json.loads((self.dir / "nyc_cfc.json").read_text())
        params = params or {}
        off, lim = int(params.get("$offset", 0)), int(params.get("$limit", 500))
        where = str(params.get("$where", ""))
        if "report_end_date >" in where:
            cutoff = where.split("'")[1][:10]
            rows = [r for r in rows if r["report_end_date"][:10] > cutoff]
        return rows[off : off + lim]
