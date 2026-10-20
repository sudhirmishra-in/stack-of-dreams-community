# Data sources and synchronization

| Source | Adapter | Provides | Terms / notes | Schedule |
| --- | --- | --- | --- | --- |
| OpenStreetMap (Overpass) | `adapters/osm.py` | provider directory: name, coordinates, partial address/phone/hours/website | ODbL 1.0, attribution "(c) OpenStreetMap contributors" shown in the UI; community-sourced, **unverified**; shared public service: one query/run, backoff, contact in User-Agent | incremental daily 06:15 UTC (`newer:` filter), full weekly Sun 05:45 UTC |
| NYC Open Data CFC `mpqk-skis` | `adapters/nyc_cfc.py` | citywide quarterly activity (individuals served at pantries; meals at soup kitchens, duplicated) | NYC Open Data terms; **activity, not capacity or inventory**; "N/A" rows are dropped, never stored as 0 | monthly (day 2) |
| 211 | `adapters/twoone_one.py` | none yet | **disabled**, no network code; needs authorized access and its terms | off |
| Partner CSV | `adapters/csv_partner.py` | partner exports (S3-triggered Lambda can feed it) | unverified until a human sets `lastVerifiedAt` | on demand |
| Partner REST / webhook | extension point | - | reuse `csv_partner.map_row` + `ResourceCandidate`; add a source in `adapters/registry.py` | - |
| Demo | `ingest/demo.py` | 5 fictional organizations with sample inventory | `demo` namespace only, `isDemoData`, labeled everywhere | seeded each full run |

## Pipeline
adapter pages -> `normalize` (reject missing name / no ZIP and no coordinates; drop implausible phones, non-http
links, out-of-range coordinates) -> `dedupe` (same source record: source wins, verification preserved; different
source + same fingerprint: attach provenance, fill gaps only) -> optimistic-locked upsert -> checkpoint.

## Safety rules (all unit-tested)
Per-source isolation; expiring lock prevents overlapping runs; idempotent stable ids; pagination + exponential
backoff with jitter (`Retry-After` honored; Overpass overload pages treated as retryable); checkpoints advance only
after a page is written; nothing is ever deleted; a record is only soft-deactivated after a COMPLETE full run of a
source that enumerates everything, with zero errors and a sane size (a run returning under half of what is known
deactivates nothing and flags `partial`); failed runs never move `lastSuccessAt`/checkpoints. Metrics: `SyncFailed`,
`SyncSuspicious`, `RecordsRejected`; alarm if ingestion stops running for 3 days.

## Timestamps kept separate
`sourceUpdatedAt` (source says it changed), `lastSyncedAt` (we fetched it), `lastVerifiedAt` (a human verified;
never set by automation), `asOf` on inventory, and the reporting period on activity records.

## Offline fallback
`FIXTURE_MODE=true` syncs from `fixtures/` (real captured payloads). Used in tests and if a public API is blocked.
