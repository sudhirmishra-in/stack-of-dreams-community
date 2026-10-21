# CLAUDE.md

**Read `docs/PROJECT_CONTEXT.md` first** (verified architecture, what is deployed, blockers, next steps), then `docs/OPERATIONS_RUNBOOK.md` (how to deploy, add users, verify; the exact procedures) when you will change or operate anything. `docs/IMPLEMENTATION_PLAN.md` maps the original brief to what exists.

## Overview

"Stack of Dreams Labs" React app + the Community Resource Navigator (AI for Good) pilot. Three working parts:

1. **Frontend** (`src/`): React 19, TypeScript, Vite, Tailwind 4. Routes include `/chat` and `/ai-for-good/*`.
2. **Existing chat API** (`backend/`, us-east-1): React -> Lambda Function URL -> AgentCore harness `MyHarness` (the sibling `../testagent` project). Working. Do not change its contract.
3. **Pilot platform** (`platform/`, **us-east-2**): DynamoDB, scheduled ingestion (OpenStreetMap, NYC Open Data), authenticated API Lambda, validation gateway with DynamoDB quotas, and the Strands AgentCore runtime `community_navigator` (orchestrator + 4 specialist agent-tools in ONE runtime).
   Access to the AI agents is **invite-only**: admin-created Cognito users, or Google sign-in for emails on a sign-up allowlist that the owner then approves by Cognito `sub` (pending until approved).

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

Everything is live and verified as of 2026-10-21 (`docs/PROJECT_CONTEXT.md` has the details): the frontend auto-deploys from `main` to https://agents.sudhirmishra.in via Amplify
(tests gate the build); the pilot backend (`navigator-pilot` SAM stack) and the `community_navigator` AgentCore runtime run in us-east-2; Cognito offers password sign-in for invited
users and **Continue with Google**, where a pre sign-up Lambda only lets allowlisted emails create accounts and the API keeps Google users _pending_ until approved (403 `pending_approval`).
Recent fixes: OSM sync timeout, 600-token answer cap with a grounded fallback, case-insensitive federated detection. Open items: SNS e-mail confirmation, branch protection and Amplify
failure alerts, confirming the next scheduled OSM sync clears `navigator-pilot-sync-failed`, a signed-in smoke test with a real token, and specialist agents rarely exercised live.

## Operating rules learned the hard way

- Deploys: SAM change-set preview first, pass **all** stack parameters (omitted ones reset to defaults), execute only after the owner says so. `update-user-pool*` Cognito calls reset omitted fields: read, change one field, apply, re-read, diff.
- Changing anything under `platform/src/navigator/agents/` or its imports: unit tests are not enough; deploy (approved) and run `platform/scripts/live_agent_check.py`.
- Federated identity is decided from verified token claims only, never email. Do not auto-link Google accounts to password accounts by email.
- Public repo: use placeholders for account IDs, pool IDs and ARNs in docs; real values come from `aws` commands.
- macOS shell: `sed -i ''`; use Python for multi-line edits.
