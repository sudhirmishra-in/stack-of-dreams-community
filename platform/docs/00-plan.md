# Pilot platform: inspection report and plan

Date of inspection: 2026-10-19. Everything below was observed read-only; nothing was deployed or changed.

## 1. What is actually deployed vs planned

| Item | State |
| --- | --- |
| `testagent` harness `MyHarness` + `NonprofitGateway` (us-east-1) | **Deployed**, working. Has uncommitted local changes in its own git repo. Untouched by this work. |
| Chat API `stack-of-dreams-api` (us-east-1): Lambda Function URL, in-code Cognito verification | **Deployed**, working. Untouched. |
| Cognito user pool `us-east-2_tPaKrhmEX` (us-east-2) | **Deployed**. Admin-create-only (good), no MFA, **no groups**, 1 user. App client has callback/logout URLs for `localhost` only, scopes `openid email`. |
| React app (`stack-of-dreams-communitynavigator`) | Built locally. **Not a git repository**; no GitHub remote. Not hosted anywhere. |
| DynamoDB, EventBridge Scheduler, Amazon Location maps, Amplify app, community-navigator runtime, usage ledger | **Not deployed.** Planned in this work. |
| `agents.sudhirmishra.in` DNS | **No record exists.** Apex has the 4 GitHub Pages A records; `www` is a CNAME to `sudhirmishra-in.github.io`. DNS is hosted at **GoDaddy** (not Route 53). No CAA records. |
| AWS Budgets | **None configured.** Month-to-date spend is about $0.00. |

## 2. Findings that change the design

1. **The account's Organizations SCP is region-based, not service-specific.** In **us-east-1** it explicitly denies DynamoDB, EventBridge (Rules + Scheduler), API Gateway, Secrets Manager, SQS, Amplify, X-Ray. **us-east-2 allows all of them** (and Lambda, AgentCore, Bedrock, Location). **us-west-2 denies almost everything.** My earlier statement that the API Gateway failure was about *tagging* was wrong: it was the region.
   **Decision: all new resources go in `us-east-2`** (same region as Cognito). `testagent` and the chat API stay in us-east-1. I will not try to bypass the SCP.
2. **No verified public food-pantry directory exists for NYC in open-data portals.** Searched NYC Open Data, NY State and others. NYC "Community Food Connection (Quarterly Report)" (`mpqk-skis`) is **118 rows of citywide aggregates** (59 quarters x {pantries: individuals served, soup kitchens: meals served}, duplicated persons counted). It has no provider names, addresses or coordinates, so it can feed *citywide activity context only*, never per-provider capacity.
   The only real, public, documented-terms directory with coordinates is **OpenStreetMap** (ODbL, via Overpass): 32 NYC food banks/soup kitchens, of which only 15 have a ZIP, 5 a phone number and 9 opening hours. It is community-sourced, so every record is labeled **unverified**; ODbL attribution is mandatory.
   **Decision:** OSM adapter (live, polite, incremental) + NYC CFC activity adapter + disabled 211 adapter + documented CSV/REST/webhook extension points. All have offline fixtures.
3. **Amplify needs a GitHub repo**; none exists for this app. Amplify is allowed in us-east-2. Manual (zip) deployment is possible, but custom-domain CI/CD needs the repo. This is a manual prerequisite.
4. **Location APIs:** the legacy `geo:*` list calls work in us-east-2. Whether the newer `geo-maps` / `geo-places` / `geo-routes` IAM actions are allowed by the SCP **cannot be verified without a (billable, tiny) call**; treated as an unverified assumption with graceful fallback.
5. **Model availability (us-east-2):** Nova Micro, Nova Lite, Nova 2 Lite, Claude Haiku 4.5 are listed. Default: Nova Micro for the classifier, Nova Lite for the orchestrator (both configurable).
6. Local Python is 3.9; the new backend uses `uv` with Python 3.12. Docker is available (for Lambda/AgentCore packaging if needed).

## 2b. Result of the first deployment attempt
Creating `AWS::Location::APIKey` failed with AccessDenied: `geo:CreateKey` is an explicit deny for this user. Rolled back
cleanly (no tables left); the key is now optional and off by default. Everything else deployed.

## 3. Architecture (single account, us-east-2)

```
React (Amplify) --JWT--> Lambda Function URL (api) --+--> DynamoDB  (resources / sync / usage)
                              |                      +--> Amazon Location (geocode, route)
              gateway: auth -> schema -> quota reservation -> domain rules -> Nova Micro classifier (ambiguous only)
                              |
                              +--(allowed only)--> AgentCore Runtime "community-navigator"
                                                     Orchestrator (Strands, agent-as-tool)
                                                       |- resource_discovery tool/agent  (DynamoDB)
                                                       |- inventory tool/agent           (DynamoDB, demo labels)
                                                       |- capacity tool/agent            (DynamoDB activity)
                                                       '- location tool/agent            (Location)
EventBridge Scheduler -> Ingestion Lambda -> adapters (OSM, NYC CFC, 211*, partner*) -> validate/normalize/dedupe -> DynamoDB
(* disabled / extension points)
```

Ingress choice: **Lambda Function URL with in-code Cognito verification** (proven in this account; no new approval risk). API Gateway in us-east-2 is probably allowed and would add throttling/WAF; recorded as a follow-up in ADR-002.

## 4. Dependency graph

```
schemas+contracts ──> dynamodb design ──> adapters ──> ingestion ──> deterministic search ──┐
                                   └────> quota ledger ──> auth/gateway ──> classifier ────┤
agent tools (reuse search/store) ──> orchestrator ──> agentcore runtime ────────────────────┤
location client ──> geocode/route endpoints ──> React map ──────────────────────────────────┤
                                                                         API handler ──> React integration ──> Amplify/DNS docs
```

## 5. Cost exposure (estimates, not quotes: verify on AWS pricing pages)

| Component | Pilot assumption | Order of magnitude |
| --- | --- | --- |
| DynamoDB on-demand | < 100k requests/month, < 100 MB | well under $1/month |
| Lambda (api + ingest) | < 100k invocations | within free tier / cents |
| EventBridge Scheduler | a few schedules | free tier |
| CloudWatch logs/alarms | 14-day retention, ~10 alarms | ~$1-2/month |
| Amazon Location | tiles/geocode, cached | a few dollars if used; keep keyed + cached |
| AgentCore Runtime | per-use (CPU/memory active time) | low at 300 req/day cap |
| Bedrock tokens | **capped by quota design**: 300 req/day x 30k tokens ceiling = 9M tokens/day theoretical max | Nova Lite/Micro prices are cents per million tokens, so worst case is a few dollars/day; see `docs/cost-model.md` |
| Amplify Hosting | build minutes + GB served | ~cents-$1 for a pilot |

Alerts do **not** stop spend; the only hard stops are the server-side quotas (and disabling users/the application kill switch).

## 6. Deployment changes (all behind explicit approval)

1. New SAM stack `community-navigator-pilot` in **us-east-2** (DynamoDB, Lambdas, Scheduler, alarms, Location API key, budgets are separate).
2. New AgentCore project `platform/agentcore` deploying runtime `community-navigator` (separate CDK stack; `testagent` unchanged).
3. Cognito: add groups `pilot-admin`, add production callback/logout URLs (manual/approved).
4. Amplify app from a GitHub repo (prerequisite: create repo) and one **CNAME** at GoDaddy for `agents`.

## 7. Risks

- No real inventory source exists: **inventory is demo-only** and namespaced; real records show "inventory unknown".
- OSM data is sparse/unverified; Overpass is a shared public service (respect usage policy; low-frequency schedule).
- Token quotas are *estimates* reserved up front and reconciled with reported usage; Bedrock itself has no per-user hard cap.
- New Location IAM prefixes and the Cognito group setup are unverified until a real deployment.
- The `testagent` harness exposes shell/file tools; the pilot runtime must never share it.
