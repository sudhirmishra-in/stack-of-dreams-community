# API contracts (v1)

Base: the Function URL (`ApiBaseUrl` output). All JSON. Every response has `X-Correlation-Id` (a valid
`x-correlation-id` request header is echoed) and `Cache-Control: no-store`. Every route except `/health`
requires `Authorization: Bearer <Cognito access token>`.

Errors always look like `{"error":{"code","message","correlationId","details?"}}`:
| Status | code | When |
| --- | --- | --- |
| 400 | bad_request | schema/length/cursor problems (field names only, never submitted values) |
| 401 | unauthorized | missing/invalid/expired token, wrong client, ID token used |
| 403 | forbidden | user disabled; non-admin on /admin |
| 404 | not_found | unknown resource/endpoint |
| 409 | request_in_progress | same idempotency key already running/completed |
| 413 | payload_too_large | body over 16 KB |
| 422 | out_of_scope | off-topic or injection attempt (fixed refusal; no model ran) |
| 429 | quota_exceeded | `details.reason`: daily_requests, daily_tokens, monthly_requests, application_daily, concurrent_request, rejections, search, routes; `details.resetsAt`; `Retry-After` |
| 503 | service_unavailable | ledger/classifier/runtime unavailable, assistant paused (fails closed) |

## GET /api/v1/health  (public)
`{"status":"ok","version","mockMode","correlationId"}`

## POST /api/v1/resources/search  (no LLM)
Request: `zipCode` (5 digits), `resourceType` (baby_formula|groceries|diapers|food_assistance), optional
`quantity`, `formulaType`, `urgency`, `sortBy` (nearest|availability|capacity), `radiusMiles`, `includeDemo`
(default false), `limit` (1-50, default 20), `cursor`. Unknown fields are rejected.
Response: `resources[]`, `totalResults`, `dataSource`, `isDemoData`, `origin{zipCode,latitude,longitude,geocoded}`,
`nextCursor`, `attributions[]`, `notes[]`, `correlationId`.
Each resource carries `sourceId`, `sourceUrl`, `attribution`, `sourceUpdatedAt`, `lastSyncedAt`,
`lastVerifiedAt`, `freshness` (fresh|stale|unknown), `verified`, `isDemoData`, `distanceMiles?` and
`inventory` only for demo records (`inventoryIsDemo`). Real records never contain inventory or capacity.

## GET /api/v1/resources/{id}
`{"resource": {...same shape...}, "correlationId"}`

## GET /api/v1/route?fromZip=10027&toResourceId=...&mode=Car|Pedestrian
Real Amazon Location values: `distanceMiles`, `durationMinutes`, `travelMode`, `origin`, `destination`,
`provider`. 400 if the provider has no coordinates; 503 if location is unavailable (nothing is estimated).

## Map data (signed-in users, relayed from Amazon Location; used by MapLibre)
`GET /api/v1/maps/style?scheme=Light|Dark` (rewritten style JSON), `GET /api/v1/maps/tiles/vector.basemap/{z}/{x}/{y}`
(protobuf), `GET /api/v1/maps/glyphs/{fontstack}/{range}.pbf`, `GET /api/v1/maps/sprites/{Light|Dark}/Default/sprites[@2x].{json,png}`.
Binary bodies, `Cache-Control: private, max-age=86400`. 429 `details.reason: "map"` past the daily cap. 400/404 for
invalid or unknown inputs; upstream failures return a generic 503.

## POST /api/v1/assistant
Request: `message` (max 500 chars after sanitation), `sessionId`, optional `history[]` (last 4 used),
`idempotencyKey`, `context{zipCode?,resourceId?}`. Response: `response`, `citations[]` (computed from tool data),
`uncertainty[]`, `usage{inputTokens,outputTokens,modelInvocations,specialistCalls,estimatedUsd}`,
`remaining` (same as /me/usage), `sessionId`, `agentId:"community-navigator"`, `correlationId`.
Identity is only ever the token's `sub`; body fields such as `userId` are rejected.

## GET /api/v1/me/usage
`daily|monthly|tokensToday|applicationDaily {limit,used,remaining,resetsAt}`, `maxQueryChars`,
`concurrentLimit`, `disabled`. Resets are UTC.

## GET /api/v1/sync-status
`sources[{sourceId,status,lastSuccessAt,lastFullSyncAt}]` (no error text for normal users).

## Admin (group `pilot-admin`)
* `PUT /api/v1/admin/quotas` `{"overrides":{"requests_per_user_day":10}}`
* `PUT /api/v1/admin/users/{sub}` `{"disabled":true}` and/or `{"overrides":{...}}`
* `PUT /api/v1/admin/switch` `{"assistantEnabled":false}` (kill switch)
* `GET /api/v1/admin/usage?day=YYYY-MM-DD`, `GET /api/v1/admin/sync-status`

## Agent runtime contract (Lambda -> AgentCore)
Request `{prompt, history[], context{}, limits{maxModelInvocations,maxToolIterations,maxSpecialistCalls,maxTokensPerRequest,mainMaxOutputTokens,timeoutSeconds}}`
(limits are clamped in the runtime to absolute ceilings). Response `{response, citations[], uncertainty[], usage{modelInvocations,specialistCalls,byModel[{modelId,inputTokens,outputTokens}]}}`.
The existing `POST /chat` contract (testagent) is unchanged.
