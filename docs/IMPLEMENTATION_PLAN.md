# Implementation plan: gap analysis against the "real-data multi-agent pilot" brief

Status date: 2026-10-20. Written after inspecting the repository and the deployed AWS state (us-east-2).
Detailed design lives in `platform/docs/` (architecture, data-sources, api-contracts, cost-model, monitoring,
deployment). This file maps the brief to what exists and lists what is still open.

## 1. Deployed state (verified)

| Item | State |
|---|---|
| Frontend | Amplify (us-east-2), `main` auto-builds with lint + tests; live at agents.sudhirmishra.in |
| Chat backend (`testagent`) | Lambda Function URL, us-east-1, unchanged |
| Pilot platform | SAM stack `navigator-pilot`, us-east-2 (API + ingest Lambdas, 2 DynamoDB tables, 3 schedules, 8 alarms, dashboard, budget) |
| Agent runtime | AgentCore `community_navigator`, us-east-2, READY (separate CDK project, `platform/agentcore`) |
| Auth | Cognito, invite-only; production callback URLs configured 2026-10-20 |
| Environments | One environment only (`pilot`). There is no separate dev stack. |

## 2. Brief vs. implementation

| Brief item | Status | Notes |
|---|---|---|
| Real data source (NYC, reusable licence) | Done | OpenStreetMap/Overpass (ODbL), NYC Open Data Community Food Connection. Licence, schema, pagination in `platform/docs/data-sources.md` |
| Adapters, normalisation, provenance, dedup, idempotent upserts, backoff, partial failure | Done | `platform/src/navigator/{adapters,ingest,store}` |
| EventBridge sync + CloudWatch monitoring | Done, **one defect** | OSM incremental sync fails with an Overpass read timeout; alarm `navigator-pilot-sync-failed` is in ALARM. No data lost |
| 211 and partner adapters | Done as disabled config | Not active and not claimed active; needs authorization |
| Deterministic search API (no LLM) | Done | `POST /api/v1/resources/search`, `GET /api/v1/resources/{id}` |
| Separate AgentCore runtime + Strands orchestrator + 4 specialists | Done | Agents-as-tools in one runtime; max 3 specialist calls; per-request limits via hooks |
| Never fabricate inventory | Done | Real OSM records are "unverified, inventory unknown"; inventory exists only in a labelled demo namespace; output guard redacts unsupported contacts/quantities |
| Cognito invite-only | Done | Admin-create only, MFA off |
| Quotas (20/day, 200/month, 30k tokens, 400 output, 3 specialists, 1 concurrent, 300/app/day) | Done | Atomic DynamoDB `TransactWriteItems`, enforced before any model or runtime call |
| Token accounting across classifier, orchestrator, specialists | Done | Ledger settles actual tokens; monthly-delta bug fixed and covered by a test |
| Validation gateway; classifier only when needed | Done | Fails closed; unauthenticated, over-quota and unrelated requests never reach Bedrock |
| AgentCore native cost controls | Done | Runtime lifecycle (idle 120s, max 900s), reserved Lambda concurrency, Bedrock model/token caps, budget + alarms |
| `GET /api/v1/me/usage` | Done | Used by `PilotUsageBadge` |
| Admin quota management + kill switch | Done in API | `PUT /admin/quotas`, `/admin/switch`, `/admin/users/{sub}`. **Not usable yet:** the Cognito `pilot-admin` group does not exist |
| React wiring (search, details, map, assistant, usage, login) | Done | Verified in production on 2026-10-20 |
| Stale / unavailable inventory labelling | Done | |
| `testagent` route preserved | Done | Regression-tested; verified working |
| Tests | Done | Frontend 116, platform 210, plus backend; CI on GitHub Actions |
| Dev environment first, then promote | **Not done** | Everything went to the single `pilot` stack |
| Specialist agents exercised against live Bedrock | **Not done** | Only the orchestrator path was exercised live |
| Signed-in smoke test with a real token | **Partly** | User verified manually in the UI; the scripted `smoke_aws.py` has not been run with a token |

## 3. Remaining work (proposed order)

1. **Fix OSM sync timeout.** Raise the adapter read timeout above Overpass's 60 s server limit, add a test, redeploy `navigator-pilot`, confirm the alarm returns to OK. Needs approval: backend deploy.
2. **Create the `pilot-admin` Cognito group** and add the owner, so the admin quota and kill-switch endpoints can be exercised. Needs approval: Cognito change.
3. **Live specialist test.** Run assistant prompts that force each specialist (inventory unknown, location, capacity) and check responses cite retrieved record IDs. Costs a few cents of Bedrock usage.
4. **Dev environment.** Parameterise the SAM stack name and resource names (`Stage` parameter), deploy `navigator-dev`, and make the scripted smoke test pass there before any further production deploy. Charge-incurring: needs approval; expected idle cost is near zero (pay-per-request tables, no provisioned capacity).
5. **Safety nets.** Branch protection on `main` (require the 4 CI checks), Amplify failure notifications, confirm the SNS email subscription, GitHub repo visibility decision.

## 4. Cost exposure

Unchanged from `platform/docs/cost-model.md`: at pilot limits the dominant cost is Bedrock (Nova Lite/Micro) at roughly cents per day worst case; DynamoDB on-demand, Lambda, Location and Amplify are within or near free-tier at pilot volume. A $25 budget and the `token-spike` alarm guard it. A dev stack would add negligible idle cost.

## 5. Deployment order and rollback

Order: ingest fix (platform stack) -> verify alarm -> Cognito group -> dev stack -> promote. Rollback: SAM stack previous version via `aws cloudformation` rollback or redeploy of the previous commit; the AgentCore runtime is versioned and a prior commit can be redeployed; the emergency switch (`PUT /admin/switch`) stops new AI invocations instantly without a deploy. Frontend: revert the commit on `main`; Amplify rebuilds.

## 6. Known limitations

- OSM records are community-contributed and unverified; opening hours and services may be stale.
- No inventory source exists for real providers; no partner has authorized a feed.
- 211 and partner integrations are disabled until authorized.
- Single environment, single region (us-east-2); chat backend remains in us-east-1.
