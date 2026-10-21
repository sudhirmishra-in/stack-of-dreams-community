# CI/CD

Frontend delivery is **Amplify on push to `main`**, gated by tests. Everything else is checked by GitHub Actions on pull
requests. AWS backend deployments (SAM stack, AgentCore runtime) are **manual and approved**, on purpose.

```
feature branch --PR--> GitHub Actions CI (4 jobs, no secrets) --merge--> main --push--> Amplify: nvm (Node 24) -> npm ci -> lint -> test -> build -> deploy
                                                                                          (any failure keeps the previous deployment live)
```

| Piece                | File                       | What it does                                                                                                                                                            |
| -------------------- | -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Node pin             | `.nvmrc`                   | `24`. Amplify's default image has Node 22.18, too old for the test dependencies (`jsdom` needs 22.22+/24.15+)                                                           |
| Amplify build + gate | `amplify.yml`              | `nvm install`/`nvm use`, `npm ci`, `npm run lint`, `npm test`, `npm run build` (which also verifies the MapLibre worker is emitted)                                     |
| Security headers     | `customHttp.yml`           | HSTS, nosniff, frame deny, referrer/permissions policy, **CSP in Report-Only mode**                                                                                     |
| CI                   | `.github/workflows/ci.yml` | `frontend` (lint, test, build), `platform` (pytest, SAM template lint), `chat-backend` (typecheck, test, bundle), `hygiene` (no tracked `.env`, no credential patterns) |

All third-party actions are pinned to full commit SHAs. The workflow uses `permissions: contents: read` and needs no secrets or AWS credentials.

## One-time settings (done by a person, not by code)

1. **GitHub -> Settings -> Branches -> branch protection for `main`**: require a pull request, require the four checks above
   (`Frontend (lint, test, build)`, `Pilot platform (pytest, SAM template lint)`, `Chat backend (typecheck, test, bundle)`,
   `Repository hygiene (no secrets)`), block force pushes. The check names appear after the first workflow run.
2. **Amplify -> Hosting -> Environment variables** (public identifiers only): see `platform/docs/amplify-dns.md`. A new build is needed after changing them.
3. **Amplify -> Rewrites and redirects**: replace the default `404-200` rule with the regex rule from `platform/docs/amplify-dns.md`, status **200**.
4. **Amplify -> Notifications**: turn on email for failed builds.
5. Leave **pull request previews off**: preview URLs are not allowed by Cognito or API CORS, so previews could not sign in.

## Rollback

Amplify console -> the app -> `main` -> pick a previous successful build -> **Redeploy this version**, or `git revert` the commit and push.

## What CI/CD does not do

- It does not deploy AWS infrastructure. Backend changes: `platform/scripts/sam_build.sh`, a change-set preview, then execute; `agentcore deploy` after `platform/scripts/sync_runtime.sh`. See `platform/docs/deployment.md`.
- It does not prove the signed-in end-to-end path; use `platform/tests/smoke_aws.py` (gated) for that.

## Optional later

- Dependabot for npm, uv and GitHub Actions (keeps the pinned SHAs current).
- Automating backend deploys from GitHub with OIDC and a narrowly scoped role plus a required-approval environment. Never store long-lived AWS keys in GitHub.
