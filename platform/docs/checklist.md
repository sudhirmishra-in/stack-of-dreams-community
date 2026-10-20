# Deployment checklist, blockers and manual approvals

## Done and verified locally
- [x] Backend: 170 tests (adapters, dedupe, idempotent sync, stale/missing data, quota concurrency, retries,
      unauthorized/forged tokens, prompt injection, classifier errors, token/tool/invocation limits, delegation,
      grounding guard, API contract). Real Strands loop exercised with a scripted model.
- [x] Frontend: 106 tests, lint, typecheck, production build.
- [x] SAM template passes `sam validate --lint`; both Lambda packages build (45 MB each).
- [x] AgentCore project `platform/agentcore` passes `agentcore validate`.
- [x] Real public data captured as fixtures (OSM 32 elements, NYC CFC 118 rows).

## Not verified (needs real AWS)
- DynamoDB transaction isolation under true concurrency (moto does not isolate; logic is single-transaction).
- Amazon Location Maps/Places/Routes v2 IAM actions and the style-descriptor URL under the account SCP.
- Real Overpass availability (it returned a 502 "at capacity" once during development; the adapter retries).
- Bedrock model access (Nova Lite / Micro in us-east-2) and the runtime's real answer quality.
- Cognito group claims in access tokens; CSP with real traffic; Amplify build.

## Deployed on 2026-10-19/20 (with your approval)
- [x] Stack `navigator-pilot` (us-east-2): 2 DynamoDB tables, ingestion + API Lambdas, 3 Scheduler schedules, alarms,
      dashboard, budget ($25/month), SNS topic. API: `<ApiBaseUrl: the Function URL from the stack output>`
- [x] First ingestion: OSM 29 real records (3 unnamed rejected), NYC CFC 110 activity rows (8 "N/A" rejected),
      5 demo orgs, 211 disabled. Unauthenticated checks pass (health 200; protected routes 401; CORS limited to allowed origins).
- [x] Runtime `community_navigator` (AgentCore, us-east-2): `<community_navigator runtime ARN>`,
      stack `AgentCore-communitynavigator-default`; API stack updated with this ARN. us-east-2 was CDK-bootstrapped for this
      (an empty orphan staging bucket from an earlier deleted bootstrap was removed first, with approval).
- [x] Direct runtime invocation verified: real tool call, 2 Nova Lite calls (~4.1k tokens), 8 cited unverified OSM records,
      caveats present, no `<thinking>` leak (fixed and redeployed), geocoding via Amazon Location Places v2 works and is cached.
- [ ] Still unverified: the signed-in path through the API (needs a pilot user token), concurrency/quota behavior on real
      DynamoDB, Maps v2 tiles (blocked, see below), and routes (`geo-routes`).
- [ ] Alarm/budget email (also: budget alerts reach nobody until subscribed): the SNS topic has no subscriber yet. Subscribe: `aws sns subscribe --region us-east-2 --topic-arn arn:aws:sns:us-east-2:160102057204:navigator-alarms-pilot --protocol email --notification-endpoint <your email>` then confirm the email.

## Blockers
0. **Browser-side map API keys are impossible here** (`geo:CreateKey` explicitly denied by the organization). The map is
   therefore served by an authenticated proxy in the API (ADR-008). Verified against real Amazon Location with admin
   credentials: style, vector tile, 3 font stacks, all 4 sprite files, plus walking and driving routes. NOT yet verified:
   the full signed-in browser path (needs a pilot user's token) and the per-user caps under real load.
1. **No verified food-pantry directory.** Real records come from OpenStreetMap (sparse, unverified). Inventory exists
   only as labeled demo data. A partner feed (CSV/REST) or 211 authorization would fix this.
2. **No GitHub repo** for the app yet (needed by Amplify CI/CD).
3. **SCP**: everything must stay in us-east-2.

## Approvals needed from you (nothing happens until you say so)
- [ ] Deploy `navigator-pilot` stack (creates billable-on-use resources; see cost-model.md)
- [ ] Run first ingestion (calls Overpass and NYC Open Data)
- [ ] `agentcore deploy` for `community_navigator`
- [ ] Cognito changes (group, production callback URLs, inviting users)
- [ ] Create the GitHub repo and Amplify app; add the two GoDaddy CNAME records
- [ ] Optional real-AWS smoke test (`RUN_AWS_SMOKE=1`)
