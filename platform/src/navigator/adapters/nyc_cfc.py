"""NYC Open Data: Community Food Connection (Quarterly Report), dataset mpqk-skis.

Meaning (from the publisher): count of *individuals served* at CFC-funded food pantries and *meals served* at
soup kitchens, per quarter, **citywide and duplicated** (a person served twice counts twice). It is service
*activity*. It is not provider-level, not capacity, and not inventory, and must never be presented as such.
Publisher: NYC Department of Social Services (DSS). Terms: NYC Open Data Terms of Use.
"""

from __future__ import annotations

from typing import Any, Iterator

from navigator.models import ActivityRecord

from .base import Page
from .http import HttpClient

SOURCE_ID = "nyc-cfc"
DATASET = "mpqk-skis"
BASE_URL = f"https://data.cityofnewyork.us/resource/{DATASET}.json"
PAGE_SIZE = 500

_PROGRAMS = {
    "food pantries (individuals served)": ("food_pantry", "individuals_served"),
    "soup kitchens ( meals served)": ("soup_kitchen", "meals_served"),
}
MEANING = {
    "individuals_served": "Individuals served per quarter at CFC-funded food pantries, citywide (duplicated persons).",
    "meals_served": "Meals served per quarter at CFC-funded soup kitchens, citywide.",
}


def map_row(row: dict[str, Any]) -> ActivityRecord | None:
    program = _PROGRAMS.get(" ".join(str(row.get("facility", "")).lower().split()))
    raw = str(row.get("number", "")).replace(",", "").strip()
    start, end = str(row.get("report_start_date", ""))[:10], str(row.get("report_end_date", ""))[:10]
    # "N/A" means the number was not reported. It is *missing*, never zero.
    if not program or not raw.isdigit() or len(start) != 10 or len(end) != 10:
        return None
    return ActivityRecord(
        sourceId=SOURCE_ID,
        program=program[0],
        metric=program[1],
        value=int(raw),
        periodStart=start,
        periodEnd=end,
        meaning=MEANING[program[1]],
    )


class NycCfcAdapter:
    source_id = SOURCE_ID
    supports_deactivation = False  # activity facts are append/overwrite by period, never deactivated

    def __init__(self, http: HttpClient, base_url: str = BASE_URL):
        self.http, self.base_url = http, base_url

    def fetch(self, checkpoint: str | None, full: bool) -> Iterator[Page]:
        offset = 0
        where = f"report_end_date > '{checkpoint}T00:00:00'" if checkpoint and not full else None
        while True:
            params: dict[str, Any] = {"$limit": PAGE_SIZE, "$offset": offset, "$order": "report_end_date,facility"}
            if where:
                params["$where"] = where
            rows = self.http.get_json(self.base_url, params)
            if not isinstance(rows, list):
                raise ValueError("unexpected SODA response shape")
            activities, rejected = [], 0
            for row in rows:
                rec = map_row(row) if isinstance(row, dict) else None
                if rec is None:
                    rejected += 1
                else:
                    activities.append(rec)
            last_page = len(rows) < PAGE_SIZE
            newest = max((a.periodEnd for a in activities), default=checkpoint)
            yield Page(activities=activities, checkpoint=newest, rejected=rejected, complete=last_page)
            if last_page:
                return
            offset += PAGE_SIZE
