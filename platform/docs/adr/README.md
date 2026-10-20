# Architecture decision records

| # | Decision | Status |
| --- | --- | --- |
| 001 | Deploy new resources in us-east-2 | accepted |
| 002 | Lambda Function URL with in-code Cognito verification as ingress | accepted (revisit) |
| 003 | OpenStreetMap + NYC Open Data as the real sources; no scraping; 211 disabled | accepted |
| 004 | Deterministic tools first; specialist agents as capped agent-tools in ONE runtime | accepted |
| 005 | DynamoDB transactional reservation ledger for quotas | accepted |
| 006 | Query gateway is a cost/relevance filter, not a security boundary | accepted |
| 007 | Single-table DynamoDB for directory data; separate usage table | accepted |
| 008 | Server-side geocoding with ZIP cache; map tiles relayed by the authenticated API (no browser key) | accepted |
| 009 | Separate AgentCore project and runtime; testagent is never invoked by the pilot | accepted |

## ADR-001: us-east-2
The account's Organizations SCP explicitly denies DynamoDB, EventBridge/Scheduler, API Gateway, Secrets Manager,
SQS, Amplify and X-Ray in us-east-1 and almost everything in us-west-2; us-east-2 allows them. The earlier API
Gateway failure was this region rule, not tagging. Cognito already lives in us-east-2. We do not attempt to bypass
the SCP. Cross-region is fine for the existing us-east-1 chat stack.

## ADR-002: Function URL ingress
Proven in this account (the chat API uses it). Authentication is enforced in code (PyJWT, RS256 only, issuer,
expiry, `token_use=access`, `client_id`). Cost of the choice: no built-in throttling/WAF, so we rely on the
persistent DynamoDB limits, `ReservedConcurrentExecutions`, and the budget alarms. API Gateway HTTP API in
us-east-2 is probably allowed and would add throttling and WAF; adopt it if the pilot grows (unverified because
creating one is a deployment).

## ADR-003: data sources
No verified government pantry directory exists in NYC/NYS open-data portals (searched). The NYC Community Food
Connection dataset is 118 citywide quarterly aggregates (pantries: individuals served, soup kitchens: meals
served, duplicated), so it is stored only as *activity context*. The only public directory with coordinates and
documented terms is OpenStreetMap (ODbL, Overpass): 32 NYC food banks/soup kitchens at capture time, many
missing ZIP/phone/hours. All its records are `unverified` and carry the ODbL attribution. 211 is disabled with
no network code. Partner REST/CSV/webhook adapters are documented extension points (CSV implemented).

## ADR-004: agents
Specialist agents exist as agent-tools (Strands "agents as tools") but the orchestrator is instructed to use
deterministic tools directly, and `maxSpecialistCalls` (3) is a hard cap enforced in code. Splitting into
separate runtimes (A2A) is deferred: one runtime keeps latency, cost and IAM simple.

## ADR-005: quota ledger
One `TransactWriteItems` checks and increments the user daily counter (requests and an estimated-token
threshold), the monthly counter, the application daily counter, the idempotency record and a concurrency slot,
atomically. DynamoDB conditions cannot do arithmetic, so the token check compares against a precomputed
threshold. Settlement replaces the estimate with actual reported tokens. A failed-before-billing request is
refunded atomically and frees its idempotency key so retries are safe. Limit: token figures are estimates, not a
Bedrock hard cap.

## ADR-006: gateway
Regex rules + a 50-token Nova Micro classifier reduce cost and off-topic traffic. They are bypassable, so real
controls are tool allowlists (read-only, deterministic), least-privilege IAM, output guarding and untrusted-data
handling of every source string.

## ADR-007: DynamoDB
Resource META + INV# items share a partition (one Query gets both); GSI1 lists a namespace by ZIP; GSI2 finds
cross-source duplicates by fingerprint. Real and demo records are separate namespaces so invented stock can never
attach to a real organization. Usage counters live in their own table (hot writes, TTL, separate IAM).

## ADR-008: maps
Geocoding/routing run server-side (IAM, cached ZIP centroids, `IntendedUse=Storage` as caching requires).
The account's organization policy **explicitly denies `geo:CreateKey`**, so a browser-side Amazon Location API key
cannot exist. Instead the API Lambda fetches the style descriptor, vector tiles, sprites and glyphs with its own
read-only role (`geo-maps:Get*`) and relays them to signed-in users: `GET /api/v1/maps/{style,tiles,sprites,glyphs}`.
The style descriptor is rewritten so the browser only ever talks to this API; MapLibre attaches the user's Cognito
access token via `transformRequest`, and only for URLs under `/api/v1/maps/`. Inputs are strictly validated (scheme,
tileset allowlist, tile ranges, font-stack/range patterns, 256-aligned glyph ranges) before anything reaches AWS.
Costs/limits: each map view is ~20-40 small requests, browser-cached for a day (`private, max-age=86400`),
capped per user (`map_requests_per_user_day`, default 6000) and by `ApiReservedConcurrency` (30). Amazon's required
attribution is kept in the style and shown by MapLibre. Pan, zoom, markers and selection remain pure client code.
Trade-off: tiles traverse a Lambda (extra latency/cost vs. direct tile access). If the account later allows API keys or
identity-pool credentials, the proxy can be replaced without UI changes beyond the style URL.

## ADR-009: separation
`platform/agentcore` is its own AgentCore project (own CDK stack, runtime `community_navigator`; runtime names
cannot contain hyphens). The API role is allowed to invoke only that runtime ARN.
