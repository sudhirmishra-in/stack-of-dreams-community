# Google sign-in (Cognito federation) and pilot approval

Google sign-in uses the **existing** Cognito user pool and app client (Authorization Code + PKCE, no client secret
in the browser). Signing in with Google proves *who* a person is. It does **not** let them use the pilot: a federated
user stays `pending` until an administrator approves their Cognito `sub`. Invited (admin-created) users are unchanged.

Placeholders below: `<REGION>` = us-east-2, `<POOL_ID>`, `<CLIENT_ID>`, `<COGNITO_DOMAIN>` (e.g.
`https://<prefix>.auth.<REGION>.amazoncognito.com`). Real values are not kept in this public repo; read them with
`aws cognito-idp describe-user-pool --user-pool-id <POOL_ID>` (Domain) and the console.

## How access is decided (server side)
1. Every API call needs a verified Cognito **access** token (RS256 signature, issuer, `token_use=access`, `client_id`).
2. A token is *federated* when its verified claims show a provider login: username `Google_<id>` or membership in the
   auto-created group `<POOL_ID>_Google`. The email claim is never used for authorization.
3. A federated `sub` with no approval is refused with HTTP 403 `pending_approval` on search, details, routes, maps,
   sync-status, the assistant and admin routes. It may only call `GET /api/v1/me/usage`, which returns
   `accountStatus: "pending"` so the UI can say so. The assistant pipeline re-checks this before any quota
   reservation, model call or AgentCore invocation (defense in depth).
4. Approval is a DynamoDB profile flag (`approved`) keyed by `sub`; quotas, concurrency and kill switches are keyed by
   the same `sub`. Revoking approval or setting `disabled` takes effect on the next request.

## 1. Google Cloud console (manual)
1. APIs & Services -> OAuth consent screen: app name, support email, **Authorized domain** `sudhirmishra.in`
   (verify the domain in Google Search Console), **Privacy policy** `https://agents.sudhirmishra.in/privacy`,
   **Terms of service** `https://agents.sudhirmishra.in/terms`. Scopes: `openid`, `email`, `profile` (no sensitive
   scopes, so no Google verification review). Publishing status: **In production**, otherwise only listed test users can
   sign in.
2. Credentials -> Create credentials -> OAuth client ID -> **Web application**:
   - Authorized JavaScript origin: `<COGNITO_DOMAIN>`
   - Authorized redirect URI: `<COGNITO_DOMAIN>/oauth2/idpresponse`
3. Copy the Client ID and Client secret into the Cognito Google identity provider (below). **Never** put the secret in
   the repo, `.env*`, Amplify variables or any `VITE_*` value. It lives only inside Cognito.

## 2. Cognito changes (each one changes production authentication: ask first)
All commands use `--region <REGION>`.

a) Google identity provider (exists once the console step is done; the secret stays in Cognito). Map attributes:
```bash
aws cognito-idp update-identity-provider --user-pool-id <POOL_ID> --provider-name Google \
  --attribute-mapping email=email,email_verified=email_verified,name=name,username=sub
```
b) Admin group (needed for the admin API; the owner can instead approve users with the script below):
```bash
aws cognito-idp create-group --user-pool-id <POOL_ID> --group-name pilot-admin
aws cognito-idp admin-add-user-to-group --user-pool-id <POOL_ID> --username <invited-admin-username> --group-name pilot-admin
```
c) Allow Google on the app client. `update-user-pool-client` **resets any field you do not pass**, so read the current
client first (`describe-user-pool-client`) and re-send every setting, adding `Google` to
`--supported-identity-providers COGNITO Google`. Keep callback `https://agents.sudhirmishra.in/auth/callback`,
sign-out `https://agents.sudhirmishra.in`, flow `code`, scopes `openid email`.

**Order matters:** deploy the API stack with the approval gate *before* step (c). Once (c) is done, any Google account
can sign in; the gate is what keeps them off paid features.

## 3. Frontend
Set `VITE_AUTH_GOOGLE=true` (Amplify environment variable) and rebuild to show **Continue with Google**. With the
default (`false`) the button is hidden and only the existing sign-in is offered. Sign-in sends `identity_provider=Google`
to Cognito Managed Login, so the user goes straight to Google and returns to `/auth/callback`.

## 4. Approving a Google user
The user signs in once (they see "waiting for approval"). Find their `sub`:
```bash
aws cognito-idp list-users --region <REGION> --user-pool-id <POOL_ID> --filter 'cognito:user_status = "EXTERNAL_PROVIDER"' \
  --query 'Users[].[Attributes[?Name==`sub`]|[0].Value,Attributes[?Name==`email`]|[0].Value]' --output text
```
Approve with your AWS credentials (no token needed), or call `PUT /api/v1/admin/users/{sub}` with `{"approved": true}`
as a `pilot-admin` user:
```bash
cd platform && uv run python scripts/approve_user.py <sub>            # approve
cd platform && uv run python scripts/approve_user.py <sub> --revoke   # back to pending
```

## 5. Verify after enabling
- A new Google account: sign-in works, `/api/v1/me/usage` shows `pending`, search/assistant return 403 `pending_approval`.
- After approval: search and the assistant work and the quota badge counts down per `sub`.
- An invited (native) user still signs in with the normal button and needs no approval.
- Revoke: run the script with `--revoke`; the next request is refused.

## Rollback
Remove `Google` from the app client's supported identity providers (re-send all other settings) and set
`VITE_AUTH_GOOGLE=false`. Existing federated users keep their Cognito records but can no longer sign in.
