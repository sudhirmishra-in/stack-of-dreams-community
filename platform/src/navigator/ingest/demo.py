"""Fictional demo organizations and inventory. Lives ONLY in the `demo` namespace.

These mirror the synthetic dataset behind the testagent lookup tool and the frontend's mock service, so
demo screens and demo assistant answers agree. Coordinates are approximate ZIP-area points for fictional
organizations, not real addresses. Real organizations never receive inventory from this module.
"""

from __future__ import annotations

from navigator.models import InventoryRecord, ResourceRecord, SourceRef
from navigator.store.data_store import DataStore
from navigator.util import fingerprint, iso

SOURCE_ID = "demo"
NOTICE = "DEMO DATA: synthetic sample record (fictional organization)"

# id, name, borough, zip, lat, lon, capacity households/week, open days, produce, canned, dairy, formula
_SEEDS = [
    ("fb-001", "Harbor Community Pantry", "Brooklyn", "11201", 40.6935, -73.9866, 400, ["Mon", "Wed", "Sat"], 1200, 2500, 300, 0),
    ("fb-002", "Riverside Food Share", "Manhattan", "10027", 40.8115, -73.9531, 650, ["Tue", "Thu", "Fri"], 800, 4000, 900, 150),
    ("fb-003", "Queens Neighbors Kitchen", "Queens", "11375", 40.7210, -73.8448, 250, ["Mon", "Fri", "Sun"], 150, 600, 0, 40),
    ("fb-004", "Bronx Bread & Beyond", "Bronx", "10451", 40.8200, -73.9265, 500, ["Wed", "Thu", "Sat"], 2000, 1800, 500, 75),
    ("fb-005", "Staten Island Helping Hands", "Staten Island", "10301", 40.6435, -74.0865, 180, ["Tue", "Sat"], 90, 700, 60, 0),
]


def seed_demo(store: DataStore) -> int:
    now = iso()
    for rid, name, boro, zip_code, lat, lon, cap, days, produce, canned, dairy, formula in _SEEDS:
        res_id = f"demo-{rid}"
        types = ["food_assistance", "groceries"] + (["baby_formula"] if formula > 0 else [])
        rec = ResourceRecord(
            id=res_id, namespace="demo", name=name, city=boro, borough=boro, zipCode=zip_code,
            latitude=lat, longitude=lon, resourceTypes=types, facilityKind="food_bank",  # type: ignore[arg-type]
            operatingDays=days, weeklyCapacity=cap, verification="unverified", isDemoData=True,
            sources=[SourceRef(sourceId=SOURCE_ID, sourceRecordId=rid, attribution=NOTICE, lastSyncedAt=now)],
            fingerprint=fingerprint(name, zip_code, None, None),
        )
        got = store.get_resource(res_id)
        store.put_resource(rec, got[1] if got else None)
        for item, qty, unit in (("baby_formula", formula, "units"), ("groceries", produce + canned + dairy, "lbs")):
            store.put_inventory(InventoryRecord(resourceId=res_id, itemType=item, quantity=qty, unit=unit, asOf=None, sourceId=SOURCE_ID, isDemoData=True))  # type: ignore[arg-type]
        # Diaper stock is intentionally not seeded: the demo dataset does not track it.
    return len(_SEEDS)
