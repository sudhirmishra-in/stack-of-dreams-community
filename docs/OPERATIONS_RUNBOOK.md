# Operations runbook (for the owner and for future agents)

How to run, change and verify the live system. Facts about _what exists_ are in `docs/PROJECT_CONTEXT.md`; the original
brief-vs-built gap analysis is `docs/IMPLEMENTATION_PLAN.md`. Like those files, this one holds no secrets, account IDs or ARNs
(the GitHub repo is public): read real values from AWS as shown. Region for everything new is **us-east-2**.

Ground rules that have held all project long (the owner asked for them; keep them):

- **Ask before** any AWS deploy, Cognito/CORS/DNS change, `git push`, or deletion. Never force-push. Show a preview first.
- Never print or commit secrets. Do not touch `../testagent`, the `/chat` contract, DNS, or the GitHub Pages site at `sudhirmishra.in`.
- Tests first for bug fixes (write the failing test, then the fix). Never delete a failing test to get green.
- macOS: `sed -i` needs `sed -i ''`; prefer a small Python snippet for multi-line edits. Quote heredocs (`<<'EOF'`).

## 1. Who can do what (access model)

| Kind of user            | How they get in                                                                 | Needs approval?                                         | Quotas         |
| ----------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------- | -------------- |
| Invited (password) user | You run `admin-create-user`; they sign in with the normal **Sign in** button    | No                                                      | Per user `sub` |
| Google user             | Email must be on the sign-up **allowlist**; they click **Continue with Google** | **Yes**: starts _pending_ until you approve their `sub` | Per `sub`      |
| Anyone else             | Rejected at Google sign-up (`not_invited`); no account is created               | n/a                                                     | n/a            |
| Admin                   | Member of Cognito group `pilot-admin` (needed only for `/api/v1/admin/*`)       | n/a                                                     | n/a            |

Server rules (in code, tested): every call needs a verified Cognito **access** token; identity is the token `sub` only (never email).
A token is _federated_ if its claims show a provider login (username `google_<id>` or group `<poolId>_Google`, matched case-insensitively).
Federated and unapproved => HTTP 403 `pending_approval` on everything except `GET /api/v1/me/usage` (which reports `accountStatus: pending`).
Approval flag lives in the usage table (`USER#<sub>` / `PROFILE`, field `approved`). Allowlist lives in the usage table
(`CONFIG` / `ALLOWLIST`, a string set of lowercase emails). Cognito's pre sign-up Lambda `navigator-signup-<env>` reads it.
The Google identity provider exists in the Cognito pool; its client secret is stored only inside Cognito. The pool requires a
`zoneinfo` attribute, which is why the Google attribute mapping contains `zoneinfo = name`: do not remove it.

### Add a person who signs in with Google

```bash
cd platform
uv run python scripts/allow_email.py add person@gmail.com          # lets them create an account
# they sign in once at https://agents.sudhirmishra.in (Continue with Google): pending
aws cognito-idp list-users --region us-east-2 --user-pool-id <POOL_ID> --filter 'cognito:user_status = "EXTERNAL_PROVIDER"' \
  --query 'Users[].[Attributes[?Name==`sub`]|[0].Value,Attributes[?Name==`email`]|[0].Value]' --output text
uv run python scripts/approve_user.py <sub>                        # lets them use the pilot (add --revoke to undo)
```

### Add a person who uses a password

```bash
aws cognito-idp admin-create-user --region us-east-2 --user-pool-id <POOL_ID> --username person@gmail.com \
  --user-attributes Name=email,Value=person@gmail.com Name=email_verified,Value=true
```

(If Cognito says a required attribute is missing, add `Name=zoneinfo,Value=UTC`.) Cognito emails a temporary password.

### Remove or pause

`approve_user.py <sub> --revoke` (back to pending, next request refused); `allow_email.py remove <email>` (stops _new_ Google
accounts; does not delete an existing one); `allow_email.py list`. Emergency stop for all AI calls: `PUT /api/v1/admin/switch`
`{"assistantEnabled": false}` as a `pilot-admin` user. Per-user override or disable: `PUT /api/v1/admin/users/{sub}`.

## 2. Deploying (all manual and approved)

### Frontend (automatic)

Push to `main` => Amplify (app in us-east-2) runs `nvm`/`npm ci`/lint/test/build and publishes https://agents.sudhirmishra.in.
A failed build keeps the previous deployment live. `VITE_*` values are baked in at build time: change an Amplify variable, then
start a new build (`aws amplify start-job --app-id <APP_ID> --branch-name main --job-type RELEASE`). Variables are public
identifiers only; `VITE_AUTH_GOOGLE=true` shows the Google button. The tests ignore shell `VITE_*` variables (see `vite.config.ts`),
so Amplify's variables cannot break the test gate. Details: `docs/CI_CD.md`, `platform/docs/amplify-dns.md`.

### Pilot API / ingestion / signup Lambdas (SAM stack `navigator-pilot`)

```bash
cd platform && ./scripts/sam_build.sh us-east-2 && cd infra
sam deploy --stack-name navigator-pilot --region us-east-2 --resolve-s3 --capabilities CAPABILITY_IAM \
  --no-execute-changeset --no-fail-on-empty-changeset --parameter-overrides <ALL current parameters>
aws cloudformation describe-change-set --region us-east-2 --change-set-name <arn printed above> \
  --query 'Changes[].ResourceChange.[Action,LogicalResourceId,Replacement]' --output text     # show the owner
aws cloudformation execute-change-set --region us-east-2 --change-set-name <arn>              # after approval
```

**Always pass every parameter**: `sam deploy` resets omitted ones to template defaults. Read the live values with
`aws cloudformation describe-stacks --region us-east-2 --stack-name navigator-pilot --query 'Stacks[0].Parameters'`
(an empty `AlarmEmail` is its default: omit it, `AlarmEmail=` is rejected). A routine change-set also lists the three schedules
and the scheduler role as "Modify": those are reference-only updates, not replacements. Expect only Lambda code changes.
After executing: `curl $ApiBaseUrl/api/v1/health` => 200 and any protected route without a token => 401.

### Agent runtime (AgentCore, separate CDK stack)

```bash
cd platform && ./scripts/sync_runtime.sh && cd agentcore && agentcore validate && agentcore deploy -y
```

The runtime ARN does not change on update. Run `platform/scripts/live_agent_check.py` afterwards (section 4).
Anything under `platform/src/navigator/` that the runtime imports needs BOTH the SAM deploy (API) and the runtime deploy.

### Cognito (production authentication: highest care)

`update-user-pool` and `update-user-pool-client` **reset every field you do not send**. Procedure used every time: save the live
object (`describe-user-pool` / `describe-user-pool-client`) to a scratch file, build the update from it changing only the intended
field, apply, re-read, diff, and restore immediately if anything else changed. The pre sign-up trigger is attached to the pool
(`LambdaConfig.PreSignUp`); the stack deploys the Lambda but never owns the pool. Full commands: `platform/docs/google-signin.md`.

## 3. Quotas and costs (current)

Per user: 20 requests/day, 200/month, 500 chars, 4 history messages, 30k estimated tokens/day, 1 concurrent. Pilot: 300 requests/day.
Per request: 8 model calls, 6 tool calls, 12k tokens, 25 s, 3 specialist calls, **600 main output tokens** (raised from 400; hard ceiling
600). Geocode 25/user and 200/app per day; routes 30/user and 500/app; map 6,000/user and 30,000/app. Overrides via `/api/v1/admin/quotas`.
Cost model and audit: `platform/docs/cost-model.md` (worst case a few dollars per month; budget $25 with alerts).

## 4. Verifying behaviour

- Unit/integration: `npm test`; `cd platform && uv run --locked pytest -q`; `npm run lint`; `npm run build`;
  `uvx --from 'aws-sam-cli==1.155.2' sam validate --lint -t platform/infra/template.yaml --region us-east-2`.
- Real model behaviour: `RUNTIME_ARN=<arn> uv run python scripts/live_agent_check.py` (a few cents; read the answers).
  Last full run (2026-10-21): discovery, location, off-topic, injection and real-record inventory ("unknown") all correct; a long answer
  can still be cut at the output cap, in which case the service returns a grounded provider list instead of an error.
- Signed-in end to end needs a real browser login (the agent cannot sign in). Scripted API smoke test: `platform/tests/smoke_aws.py`
  (`RUN_AWS_SMOKE=1`, needs a user access token).
- Pre sign-up Lambda in AWS without creating accounts: `aws lambda invoke --function-name navigator-signup-pilot` with a synthetic
  `PreSignUp_ExternalProvider` event (allowed email => event returned; stranger => `not_invited`).

## 5. Known behaviours and gotchas

- Google sign-in with the _same email_ as an invited user creates a **separate** Cognito user (no automatic linking, on purpose:
  email-based linking is an account-takeover risk). That second account is pending until approved.
- Cognito runs the pre sign-up trigger only when creating an account; existing Google accounts are unaffected by allowlist changes.
- `navigator-pilot-sync-failed` has a 24-hour period, so it stays in ALARM until the failing day rolls out even after a good sync.
- OSM/Overpass: the client read timeout must exceed the query timeout (now 75 s vs 55 s). Records are community-sourced and unverified.
- The model sometimes wraps replies in `<answer>`/`<response>` tags or repeats a hook's "Stopped:" text; `agents/service.py` and
  `gateway/invoker_text.py` clean/replace these. If you change prompts, re-run the live check.
- Privacy Policy and Terms are at `/privacy` and `/terms` (drafts for the owner's review; contact is the sudhirmishra.in site).
- DNS for `sudhirmishra.in` is hosted in Route 53 (moved when Amplify was connected). Records for the apex site, `www` and mail were
  re-created there on 2026-10-20 and a Google site-verification TXT sits beside the SPF TXT in the apex TXT record set. Never
  replace the apex TXT set; merge into it. Incident note: `platform/docs/amplify-dns.md`.
