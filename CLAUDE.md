# CLAUDE.md

**Read `docs/PROJECT_CONTEXT.md` first.** It has the verified architecture, what is deployed vs planned, known blockers and next steps.

## Overview

"Stack of Dreams Labs" React app + the Community Resource Navigator (AI for Good) pilot. Three working parts:

1. **Frontend** (`src/`): React 19, TypeScript, Vite, Tailwind 4. Routes include `/chat` and `/ai-for-good/*`.
2. **Existing chat API** (`backend/`, us-east-1): React -> Lambda Function URL -> AgentCore harness `MyHarness` (the sibling `../testagent` project). Working. Do not change its contract.
3. **Pilot platform** (`platform/`, **us-east-2**): DynamoDB, scheduled ingestion (OpenStreetMap, NYC Open Data), authenticated API Lambda, validation gateway with DynamoDB quotas, and the Strands AgentCore runtime `community_navigator` (orchestrator + 4 specialist agent-tools in ONE runtime).
   Access to the AI agents is **invite-only** (admin-created Cognito users; no sign-up).

## Commands

- Frontend: `npm run dev` (port 5173 is the only Cognito-allowed origin) | `npm test` | `npm run lint` | `npm run build` (also verifies the MapLibre worker)
- Pilot platform: `cd platform && uv sync --group dev --group agent && uv run pytest -q`
- Chat backend: `cd backend && npm test`
- Infra: `platform/scripts/sam_build.sh us-east-2`, `sam validate --lint -t platform/infra/template.yaml --region us-east-2`, `cd platform/agentcore && agentcore validate`
- After changing `platform/src/navigator/`, run `platform/scripts/sync_runtime.sh` before `agentcore deploy` (it copies the package into the runtime bundle).

## Rules (these matter)

- **Ask before** any AWS deploy, Cognito/CORS/DNS change, `git push`, or deleting anything. Show a change-set preview first (`sam deploy --no-execute-changeset`). Never force-push.
- **Never print or commit secrets.** `.env*`, `.cli/`, credentials are git-ignored; docs and code use no account IDs/endpoints/ARNs. The GitHub repo is public.
- **All new AWS resources go in us-east-2** (organization policy denies DynamoDB, Scheduler, API Gateway, Amplify etc. in us-east-1). Do not try to bypass SCP denies; `geo:CreateKey` is also denied (map runs through the API proxy).
- **Do not modify `../testagent`** or the `/chat` contract. The pilot never routes to `testagent`.
- **Honesty about data:** real directory records are OpenStreetMap, community-sourced and `unverified`, with NO inventory. Inventory is DEMO data only (`demo` namespace, always labeled `isDemoData`). Never present activity (people served) as capacity or inventory. No invented addresses, phones, hours.
- Server-side limits are the only real cost/abuse controls (quotas, concurrency, caps). Alerts do not stop spend.
- Verify against real AWS when it matters: fakes and moto have repeatedly missed real response shapes and IAM actions.
- Tests must not depend on `.env` (Vitest reads `src/tests/noenv`). Keep ESLint, Prettier and the test suites green; never delete a failing test to pass.
- Shell: never use backticks inside an unquoted heredoc; use `<<'EOF'`.

## Current state in one paragraph

Backend, runtime, data and alarms are deployed in us-east-2 and the code is pushed to GitHub (`main`). **Amplify and `agents.sudhirmishra.in` are NOT set up yet** (needs the owner to connect GitHub in the console; DNS is at GoDaddy; keep the apex GitHub Pages records and `www` untouched). Open issues: the scheduled OSM sync timed out (alarm firing), the signed-in end-to-end path has not been verified with a real token, the SNS alert subscription is unconfirmed, and no `pilot-admin` Cognito group exists. Details and next steps: `docs/PROJECT_CONTEXT.md`.
