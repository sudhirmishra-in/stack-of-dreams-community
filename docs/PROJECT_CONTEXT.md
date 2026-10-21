# Project context (for humans and future Claude Code sessions)

**Last verified: 2026-10-21** against the repository (`main`, commit `f58691d`) and the live AWS account. **Read `docs/OPERATIONS_RUNBOOK.md` for how to deploy, add users and verify.**
This file records facts. It contains no secrets, account IDs, endpoints or ARNs; look those up as shown in "How to re-verify".

Legend: **[LIVE]** deployed and checked. **[LIVE, UNVERIFIED]** deployed, but not exercised end to end. **[PLANNED]** not built or not deployed.

---

## 1. What this is and how the repository is organized

"Stack of Dreams Labs": a React web app presenting AI agents, plus the **Community Resource Navigator** (AI for Good) pilot for the
AWS Breaking Barriers 2026 hackathon: families find food assistance, baby formula and diapers; coordinators see a read-only
dashboard; an AI assistant answers grounded in directory data. **Using the AI agents is invite-only**: admin-created Cognito users, or Google accounts whose email is on a sign-up allowlist AND that the owner has approved (section 5).

Repository root = this folder (GitHub: `sudhirmishra-in/stack-of-dreams-community`, public, default branch `main`).
The sibling folders `../testagent` (own local git, no remote) and `../hackathonNYC26` (empty AgentCore project) are NOT part of this repo.

```
src/                    React 19 + TypeScript + Vite + Tailwind 4 frontend
  app/ auth/ components/ config/ hooks/ pages/ services/ types/ utils/ tests/
  features/aiForGood/   Community Navigator UI: pages, components (map, filters, cards), hooks, utils
backend/                EXISTING chat API (Node/TypeScript Lambda). Do not break.
platform/               PILOT backend (Python 3.12, uv)
  src/navigator/        adapters/ ingest/ store/ search/ location/ quota/ gateway/ api/ agents/
  infra/template.yaml   SAM stack for us-east-2 (DynamoDB, 2 Lambdas, Scheduler, alarms, dashboard, budget)
  agentcore/            separate AgentCore project for runtime community_navigator
  docs/                 architecture, ADRs, API contracts, data sources, admin, cost, monitoring, deployment, Amplify/DNS, checklist
  fixtures/ scripts/ tests/
amplify.yml             Amplify build + security headers (CSP is Report-Only)
scripts/verify-dist.mjs fails the build if the MapLibre worker is not emitted
docs/PROJECT_CONTEXT.md this file (facts)   docs/OPERATIONS_RUNBOOK.md (procedures)   docs/IMPLEMENTATION_PLAN.md (brief vs built)   docs/CI_CD.md
```

Tests (rerun 2026-10-21): frontend 136 passing (Vitest), pilot platform 255 passing (pytest), chat backend 15 passing. Lint, typecheck,
production build, `sam validate --lint` and `agentcore validate` pass. A clean checkout of only the tracked files builds and tests green.

## 2a. Update 2026-10-21: general assistant

The website's general AI Assistant no longer uses the original `testagent` harness (it refused generic questions because the food-bank tool and a one-line prompt made Nova Micro treat everything else as out of scope). The legacy chat Lambda now invokes a new generic harness, `research-agent/` (Nova Lite, no tools, firm no-fabricated-citations rule, accurate AgentCore/Strands/agentic-AI facts in the prompt; us-east-1; CDK stack `AgentCore-researchagent-default`). `testagent` is untouched and still deployed. The legacy chat Lambda has no quotas, so its reserved concurrency is 2. The pilot API now also serves this assistant (`agent: "research"`) with the same quotas, approval gate and kill switch as the navigator (see docs/OPERATIONS_RUNBOOK.md section 2b); the website switches to it once the SAM stack is deployed with `ResearchHarnessArn`.

## 2. The existing working integration (React -> Lambda -> AgentCore testagent) [LIVE]

`React (/chat route) -> chat Lambda (Function URL, us-east-1, stack stack-of-dreams-api) -> AgentCore harness MyHarness (us-east-1)
-> Amazon Nova Micro, plus the NonprofitGateway MCP tool Lambda (synthetic food-bank data)`.

- The chat Lambda verifies the Cognito access token **in code** (aws-jwt-verify; Function URL AuthType NONE), maps `agentId: assistant` to the harness,
  strips `<thinking>` text, and returns `{response, sessionId, agentId}`. Request/response contract is unchanged and still used by `/chat`.
- It was confirmed working by the user earlier in the project. Reserved concurrency was set to 10 on 2026-10-20 (template + deployed).
- The harness has shell/file tools and no per-user quota: keep its audience small. `testagent` itself is untouched and has pre-existing
  uncommitted local changes in its own git repo.
- The frontend selects mock vs real chat with `VITE_USE_MOCK_API`; `VITE_API_BASE_URL` is this Lambda.

## 3. New specialized agents and their status

One AgentCore runtime, **`community_navigator`** (us-east-2, Python/Strands, status READY, separate CloudFormation stack
`AgentCore-communitynavigator-default`, idle session timeout 120 s, max lifetime 900 s). Code: `platform/src/navigator/agents/`.
AgentCore runtime names cannot contain hyphens, hence `community_navigator`.

| Piece                                                                                                                  | Status                                                                                                                                                                                                    |
| ---------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Orchestrator (Strands, Amazon Nova Lite, 600 output tokens)                                                            | [LIVE] verified by direct invocation (real tool call, grounded answer, caveats, ~4k tokens)                                                                                                               |
| Deterministic tools: `search_resources`, `get_resource_details`, `get_inventory`, `get_capacity_context`, `route_info` | [LIVE] verified (search, walking route)                                                                                                                                                                   |
| Specialist agent-tools: `resource_discovery_agent`, `inventory_agent`, `capacity_agent`, `location_agent`              | [LIVE, UNVERIFIED] defined and tested offline with a scripted model through the real Strands loop; **never invoked against live Bedrock** (the orchestrator preferred direct tools, `specialistCalls: 0`) |
| Per-request limits (model calls, tool calls, tokens, time, specialist cap 3) via Strands hooks                         | [LIVE] tested offline and in the live runtime; clamped to absolute ceilings in code                                                                                                                       |
| Output guard (redacts phone/e-mail/URL/quantity not present in tool data; strips `<thinking>` and `<response>` tags)   | [LIVE]                                                                                                                                                                                                    |
| Separate runtime per specialist (A2A)                                                                                  | [PLANNED] deliberately not done (ADR-004)                                                                                                                                                                 |

They are **not separately deployed agents**: specialists are tools inside the single runtime. The existing `testagent` harness is never invoked
by the pilot (the API role cannot reach it).

## 4. Data layer, ingestion and AWS resources (all us-east-2 unless noted)

SCP rule discovered: the organization policy blocks DynamoDB, EventBridge/Scheduler, API Gateway, Secrets Manager, SQS, Amplify and X-Ray in
us-east-1 and almost everything in us-west-2. **Everything new lives in us-east-2.** An earlier "API Gateway tagging denied" diagnosis was wrong; it was this region rule.

CloudFormation stacks [LIVE]: `navigator-pilot` (SAM), `AgentCore-communitynavigator-default`, `CDKToolkit` (both regions), `aws-sam-cli-managed-default` (both),
`AgentCore-testagent-default` and `stack-of-dreams-api` (us-east-1, pre-existing).

| Resource                                                                | Detail                                                                                                                                                                                                                                                                                                                        |
| ----------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `navigator-data-pilot`                                                  | on-demand, TTL on `ttl`, point-in-time recovery on, GSI `gsi1` (namespace by ZIP) and `gsi2` (duplicate fingerprint). 165 items: 29 real resources, 5 demo, 110 activity rows, ZIP-centroid cache (4), sync state/runs. Single-table design documented in `platform/src/navigator/store/schema.py`. Table has `Retain` policy |
| `navigator-usage-pilot`                                                 | on-demand, TTL, no PITR. Counters (daily/monthly/app), in-flight slots, idempotency/reservation records, user profiles, admin config                                                                                                                                                                                          |
| `navigator-ingest-pilot` (Lambda, py3.12, 512 MB, 300 s, concurrency 1) | EventBridge Scheduler: OSM incremental daily 06:15 UTC, OSM full weekly Sun 05:45 UTC, NYC CFC monthly. All ENABLED                                                                                                                                                                                                           |
| `navigator-api-pilot` (Lambda, py3.12, 512 MB, 60 s, concurrency 30)    | Function URL (AuthType NONE; token verified in code)                                                                                                                                                                                                                                                                          |
| Alarms / SNS / budget                                                   | 8 CloudWatch alarms, dashboard `navigator-pilot`, SNS topic `navigator-alarms-pilot`, budget `navigator-pilot-monthly` ($25). 8 custom metrics in namespace `Navigator`                                                                                                                                                       |
| Logs                                                                    | 30-day retention on all groups created by this project (also the chat Lambda). `testagent`'s runtime log group has none (left alone)                                                                                                                                                                                          |

Ingestion pipeline: `Scheduler -> Ingestion Lambda -> adapters -> validate/normalize -> dedupe/merge -> optimistic-locked upsert -> DynamoDB`.
Safety rules (tested): per-source isolation, expiring lock, idempotent stable ids, backoff, nothing deleted, soft-deactivate only after a complete full sync with no errors and a sane size, failed runs never advance success markers.

Sources: **OpenStreetMap via Overpass** (real, ODbL, community-sourced, **unverified**, 29 NYC food banks), **NYC Open Data CFC `mpqk-skis`** (110 quarterly citywide activity rows; NOT per-provider, NOT capacity), **211 disabled** (no network code), partner CSV adapter implemented, REST/webhook are documented extension points.
**Inventory exists only as clearly labeled DEMO data** (5 fictional organizations in the `demo` namespace). No verified government pantry directory was found.

**OSM sync timeout: fixed 2026-10-21.** The incremental sync had failed with `The read operation timed out` because the HTTP client's 30 s read
timeout was shorter than Overpass's 55-60 s query time. OSM now uses a 75 s read timeout, 3 attempts, 55 s query timeout (worst case stays under the 300 s
Lambda limit). A manual run succeeded. The alarm `navigator-pilot-sync-failed` (24 h period) may still show ALARM until the next scheduled run (06:15 UTC) and the day boundary pass:
check it, do not assume it cleared.

## 5. Authentication, quotas and security [LIVE]

- **Cognito** user pool in us-east-2 (pre-existing): admin-create-only, MFA off, Managed Login v2 domain, app client `stackofdream-ui` without secret, PKCE, callbacks/sign-out for localhost AND `https://agents.sudhirmishra.in`, scopes `openid email`, identity providers `COGNITO` + `Google`. 3 invited users (2 have not set a password yet), group `pilot-admin` (the owner) and the auto-created `<poolId>_Google` group. The pool requires a `zoneinfo` attribute (the Google mapping fills it from `name`; do not remove). The frontend uses `oidc-client-ts` with tokens in memory only.
  PKCE, callback/sign-out URLs currently **localhost only**. The frontend uses `oidc-client-ts` with tokens in memory only (`VITE_AUTH_MODE=oidc`).
- **Google sign-in [LIVE]**: **Continue with Google** is shown (`VITE_AUTH_GOOGLE=true`). Google proves identity only: federated users (claims: username `google_<id>` or group `<poolId>_Google`) stay **pending** until approved by `sub` (`platform/scripts/approve_user.py`, or `PUT /admin/users/{sub}` `{approved:true}`); pending users get HTTP 403 `pending_approval` everywhere except `GET /me/usage`. A **pre sign-up Lambda** (`navigator-signup-pilot`, attached as the pool's PreSignUp trigger) lets only emails on the DynamoDB allowlist create a new Google account (`platform/scripts/allow_email.py`); strangers get `not_invited` and no account. Verified: synthetic invocations of the live Lambda and a real non-invited login. Steps and rollback: `platform/docs/google-signin.md`; procedures: `docs/OPERATIONS_RUNBOOK.md`.
- **API auth**: every `/api/v1/*` route except `/health` needs a valid Cognito _access_ token (RS256 only, issuer, expiry, `token_use`, `client_id`). Identity = token `sub` only; unknown body fields are rejected.
- **Validation gateway before the runtime**: kill switch/disabled user -> sanitize + 500-char limit -> idempotent replay -> deterministic domain/injection rules (no LLM) -> **atomic DynamoDB quota reservation** -> Nova Micro classifier only for ambiguous cases -> runtime -> settle actual tokens. Fails closed. The gateway is a cost/relevance filter, not a security boundary (ADR-006).
- **Default limits** (admin-overridable): 20 req/user/day, 200/month, 500 chars, 4 history messages, 600 main output tokens, 50 classifier tokens, 3 specialist calls, 30k est. tokens/user/day, 1 concurrent, 300 req/app/day; plus per-request 8 model calls / 6 tool calls / 12k tokens / 25 s.
- **Cost caps added in the cost audit**: geocoding limited to NYC ZIP prefixes (cached forever) with 25/user/day and 200/day app caps; routes 30/user and 500/app per day; map requests 6,000/user and 30,000/app per day.
- **IAM**: separate least-privilege roles for ingestion, API and the runtime; the API role can invoke only the `community_navigator` runtime (needs both `InvokeAgentRuntime` and `InvokeAgentRuntimeForUser`: a missing second action caused the earlier chat 503, fixed).
- **Map**: the account **explicitly denies `geo:CreateKey`**, so no browser API key can exist. The API relays style/tiles/sprites/glyphs (`/api/v1/maps/*`) for signed-in users; MapLibre sends the token only to those URLs.
- **Secrets**: none in the repo or in env templates (`.env`, `.env.local`, `.cli/` are git-ignored). Public identifiers (Cognito IDs, URLs) live in `.env`/Amplify variables.

## 6. Hosting: GitHub and AWS Amplify for agents.sudhirmishra.in

| Item                                                    | Status                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GitHub repo `sudhirmishra-in/stack-of-dreams-community` | [LIVE] initial commit pushed to `main` (1 commit, 245 files, no sensitive files). Repo is **public**                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| Amplify app                                             | [LIVE] us-east-2, auto-builds `main` on push (lint + test + build gate); env vars set (public identifiers; `VITE_AUTH_GOOGLE=true`); build failure notifications still OFF                                                                                                                                                                                                                                                                                                                                                                              |
| `amplify.yml` / `customHttp.yml`                        | [LIVE] `nvm` Node 24 (`.nvmrc`), `npm ci`, lint, test, build; security headers in `customHttp.yml`; CSP is **Report-Only**                                                                                                                                                                                                                                                                                                                                                                                                                              |
| SPA rewrite rule                                        | [LIVE] regex rule with status 200 (`.mjs` excluded so the MapLibre worker is served); deep links like `/privacy` return 200                                                                                                                                                                                                                                                                                                                                                                                                                             |
| DNS `agents.sudhirmishra.in`                            | [LIVE] resolves to Amplify's CloudFront and serves the app over valid HTTPS (domain association AVAILABLE, subdomain `agents` only). The old note about adding CNAMEs at GoDaddy no longer applies: DNS is now hosted in Route 53 (see the row below)                                                                                                                                                                                                                                                                                                   |
| DNS hosting                                             | **Changed 2026-10-20:** the domain's nameservers now point to Route 53 (zone created by Amplify), not GoDaddy. This briefly broke the apex site (GitHub Pages), `www` and Google Workspace e-mail; the missing records (apex A x4, `www` CNAME, MX x5, SPF TXT and its include TXT) were copied into Route 53 and verified from public resolvers. The old GoDaddy zone is untouched. Unknown extra records in that zone (for example DKIM) were not checked: compare it in the GoDaddy console. See the incident note in `platform/docs/amplify-dns.md` |
| Cognito callback/logout                                 | [LIVE] production URLs added next to localhost                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| API CORS                                                | allows the production origin and localhost; the default `*.amplifyapp.com` origin is **not** allowed (test on the custom domain, or add it with a stack update)                                                                                                                                                                                                                                                                                                                                                                                         |

Production env vars for Amplify are listed in `platform/docs/amplify-dns.md` (public identifiers only).

## 7. Important decisions and known blockers

Decisions (details in `platform/docs/adr/README.md`): us-east-2 for all new resources; Function URL + in-code JWT verification as ingress; deterministic-first design with
capped specialist agent-tools in one runtime; DynamoDB transactional quota ledger; single-table data model with separate real/demo namespaces; server-side map proxy; separate AgentCore project so `testagent` stays untouched.

Blockers and caveats:

1. **No verified food-pantry directory**; OSM is sparse (about half of records lack ZIP/phone/hours) and unverified. Real inventory is not available anywhere.
2. **`geo:CreateKey` denied** (organization policy): no browser map key; map works only through the API proxy (higher latency/cost, capped).
3. **Specialist agents** are tools inside the runtime; in live checks the orchestrator mostly answers with direct tools (only the capacity specialist was seen invoked, once). Discovery/inventory/location specialists are tested offline only.
4. **Model output**: answers can hit the 600-token output cap on long lists (the service then returns a grounded provider list instead of an error); earlier bugs ("Stopped: tool call limit reached", leaked `<answer>` tags) were fixed and are covered by tests. Re-run `platform/scripts/live_agent_check.py` after any prompt/agent change.
5. Alarm/budget e-mail subscription is **PendingConfirmation** (the owner must click the AWS confirmation e-mail). The `navigator-pilot-sync-failed` alarm may still be in ALARM (24 h period) until after the next scheduled sync.
6. Account has credits. Fixed cost estimate about $5/month; variable paths are capped (`platform/docs/cost-model.md`). Pricing file is unverified.
7. DynamoDB isolation under true concurrency is only unit-tested with moto (which does not isolate transactions); the logic keeps every check inside one transaction.
8. Search reads the whole real namespace per query (fine at ~29 records; needs per-ZIP keys past a few thousand).
9. GitHub repo is public and contains the AWS account ID and Cognito pool ID in config files (not credentials). Consider making it private. Branch protection on `main` is not enabled.
10. Google sign-up creates a separate Cognito user even for an email that already has an invited password account (no linking, deliberately). Admin-created users are never gated; Google users always need approval.
11. Privacy Policy / Terms (`/privacy`, `/terms`) are drafts written by Claude: the owner should review the wording (and verify that AgentCore trace capture does not store prompt text before relying on the "message text is not logged" statement).

Gotchas learned (do not repeat): MapLibre builds its worker URL at runtime, so it must be set with `setWorkerUrl` (done) or the map hangs in dev and prod;
Vitest must not read the developer's `.env` (isolated via `envDir`); never put backticks in an unquoted shell heredoc;
a mocked `Response` body can be read once; Amazon Location `GetGlyphs` wants the range with `.pbf`; walking routes carry distance/duration only per leg.

## 8. Next implementation steps (in order)

1. Confirm the SNS e-mail subscription; enable Amplify build-failure notifications and GitHub branch protection on `main` (require the 4 CI checks).
2. Confirm the scheduled OSM sync (06:15 UTC) succeeds and the sync-failed alarm returns to OK.
3. Finish the Google flow test with an allowlisted account: sign in => pending => `approve_user.py <sub>` => search and assistant work; then `--revoke`.
4. Run the gated API smoke test with a real token (`platform/tests/smoke_aws.py`); verify the signed-in map and quotas in a browser.
5. Exercise the discovery/inventory/location specialists on prompts that need them; consider a `dev` stack (`EnvName` parameter) before further risky changes.
6. Flip the CSP header from Report-Only to enforcing once the console shows no violations; optionally move to API Gateway HTTP API in us-east-2 for throttling/WAF (ADR-002).
7. Real data: pursue a partner CSV/REST feed or 211 authorization (adapters exist, disabled); volunteer inventory updates need authentication (not built).
8. Housekeeping: delete the two stray pending Google test accounts if they still exist; compare the old GoDaddy DNS zone for extra records (DKIM) and delete the empty duplicate hosted zone for `agents.sudhirmishra.in`; decide whether to keep DNS in Route 53; set retention on `testagent`'s log group.

## How to re-verify

```bash
aws cloudformation list-stacks --region us-east-2 --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --query 'StackSummaries[].[StackName,StackStatus]' --output text
aws bedrock-agentcore-control list-agent-runtimes --region us-east-2 --query 'agentRuntimes[].[agentRuntimeName,status]' --output text
aws dynamodb get-item --region us-east-2 --table-name navigator-data-pilot --key '{"PK":{"S":"SYNC#osm"},"SK":{"S":"STATE"}}'
aws cloudwatch describe-alarms --region us-east-2 --alarm-name-prefix navigator- --state-value ALARM --query 'MetricAlarms[].AlarmName'
aws cloudformation describe-stacks --region us-east-2 --stack-name navigator-pilot --query "Stacks[0].Outputs"   # API base URL
aws amplify list-apps --region us-east-2; dig +short agents.sudhirmishra.in
npm test && npm run build; (cd platform && uv run pytest -q); (cd backend && npm test)
```
