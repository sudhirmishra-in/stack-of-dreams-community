# Deployment (nothing here has been run; every step that creates AWS resources needs your approval)

Region for everything new: **us-east-2** (see ADR-001). `testagent` and the us-east-1 chat stack stay as they are.

## 0. Preconditions
`aws sts get-caller-identity` shows account 160102057204; tools: `sam`, `uv`, `agentcore`, Docker not required.
Local checks (free): `cd platform && uv run pytest && sam validate --lint -t infra/template.yaml --region us-east-2`.

## 1. Data + API stack (creates DynamoDB, 2 Lambdas, Scheduler, alarms, dashboard, budget, map key)
```bash
cd platform && ./scripts/sam_build.sh us-east-2
cd infra && sam deploy --stack-name navigator-pilot --region us-east-2 --resolve-s3 --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    CognitoUserPoolId=us-east-2_tPaKrhmEX CognitoClientId=<app client id> \
    IngestContact=<your email> AlarmEmail=<your email> \
    "AllowedOrigins=https://agents.sudhirmishra.in,http://localhost:5173" \
    "MapReferers=https://agents.sudhirmishra.in/*,http://localhost:5173/*" \
    MonthlyBudgetUsd=25 MockMode=false
```
The map needs no key: the API relays tiles for signed-in users (ADR-008). Deploy with `ApiReservedConcurrency=30` (default).
Leave `AgentRuntimeArn` empty first: the assistant answers 503 until step 3, and the search/map work. Confirm the SNS
subscription email. Tables are `Retain` (deleting the stack keeps your data).
If any resource is denied by the SCP, stop and report it; do not work around it.

## 2. First data load (invokes the ingestion Lambda once)
```bash
aws lambda invoke --region us-east-2 --function-name navigator-ingest-pilot \
  --cli-binary-format raw-in-base64-out --payload '{"mode":"full"}' /dev/stdout
```
Then `GET /api/v1/admin/sync-status`. OSM may need a retry if Overpass is overloaded (the adapter backs off).

## 3. Agent runtime (separate stack, separate approval)
```bash
cd platform && ./scripts/sync_runtime.sh
cd agentcore && agentcore validate && agentcore deploy      # runtime community_navigator, target us-east-2
```
Take the runtime ARN from `agentcore status`, then update the API stack with `AgentRuntimeArn=<arn>` and
re-deploy step 1. Model access: confirm Nova Lite and Nova Micro are enabled in Bedrock for us-east-2.

## 4. Cognito
Create the `pilot-admin` group and add production callback/sign-out URLs (docs/pilot-admin.md).

## 5. Frontend config
`VITE_PILOT_API_BASE_URL=<ApiBaseUrl>`, `VITE_USE_MOCK_RESOURCES=false`, `VITE_AUTH_*` (production redirect URI),
No map key is needed: the map appears automatically when `VITE_PILOT_API_BASE_URL` is set and `VITE_USE_MOCK_RESOURCES=false`.

## 6. Verify (optional real-AWS smoke test; calls only the deployed API)
```bash
cd platform && RUN_AWS_SMOKE=1 PILOT_API_URL=<ApiBaseUrl> SMOKE_TOKEN=<pilot user access token> uv run python tests/smoke_aws.py
```
Add `SMOKE_ASSISTANT=1` for one real assistant question. Also check manually: map renders markers (the map data via
the API proxy (`geo-maps:Get*`), geocoding (`geo-places`) and routes (`geo-routes`) are all verified allowed), a 2nd
concurrent assistant request gets 429, an off-topic question gets 422 without a runtime invocation.

## Rollback
Assistant: `PUT /admin/switch {"assistantEnabled":false}`. Frontend: unset `VITE_PILOT_API_BASE_URL` (falls back,
visibly, to the old chat). Stacks: `aws cloudformation delete-stack --stack-name navigator-pilot --region us-east-2`
(tables retained); `agentcore remove` + redeploy for the runtime.
