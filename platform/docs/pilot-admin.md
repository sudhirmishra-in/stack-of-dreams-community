# Pilot user provisioning and quota administration

> **Using the AI agents is invite-only.** There is no public sign-up: the Cognito pool (`us-east-2_tPaKrhmEX`) is
> admin-create-only, so only people an administrator invites can sign in. Every assistant, search, map and usage request
> also needs a valid token, and access can be removed at any time by disabling the user (see below). Nobody else can
> reach the agents, and anonymous requests are rejected with 401.

The Cognito pool is already invite-only (admin-create-only, no self sign-up).

## One-time (needs approval; changes Cognito)
```bash
aws cognito-idp create-group --region us-east-2 --user-pool-id us-east-2_tPaKrhmEX \
  --group-name pilot-admin --description "Can change pilot quotas and disable users"
aws cognito-idp admin-add-user-to-group --region us-east-2 --user-pool-id us-east-2_tPaKrhmEX \
  --username <your-username> --group-name pilot-admin
```
Add the production URLs to the app client (callback `https://agents.sudhirmishra.in/auth/callback`, sign-out
`https://agents.sudhirmishra.in`). Scopes `openid email` are enough. Groups arrive in the access token as `cognito:groups`.

## Invite a pilot user
```bash
aws cognito-idp admin-create-user --region us-east-2 --user-pool-id us-east-2_tPaKrhmEX \
  --username person@example.com --user-attributes Name=email,Value=person@example.com Name=email_verified,Value=true
```
Cognito emails a temporary password. Consider requiring MFA for admins.

## Find a user's id (`sub`)
```bash
aws cognito-idp admin-get-user --region us-east-2 --user-pool-id us-east-2_tPaKrhmEX --username person@example.com \
  --query "UserAttributes[?Name=='sub'].Value" --output text
```

## Administer (access token of a `pilot-admin` user)
```bash
API=https://xxxx.lambda-url.us-east-2.on.aws; T=<admin access token>
# global defaults
curl -X PUT $API/api/v1/admin/quotas -H "Authorization: Bearer $T" -H 'content-type: application/json' \
  -d '{"overrides":{"requests_per_user_day":10,"requests_per_app_day":150}}'
# per-user override or disable (access is cut immediately: checked on every request)
curl -X PUT $API/api/v1/admin/users/<sub> -H "Authorization: Bearer $T" -H 'content-type: application/json' -d '{"disabled":true}'
# emergency kill switch for the whole assistant (search keeps working)
curl -X PUT $API/api/v1/admin/switch -H "Authorization: Bearer $T" -H 'content-type: application/json' -d '{"assistantEnabled":false}'
# today's aggregate usage and estimated spend
curl $API/api/v1/admin/usage -H "Authorization: Bearer $T"
```
Overridable keys: `requests_per_user_day`, `requests_per_user_month`, `max_query_chars`, `history_messages`,
`main_max_output_tokens`, `classifier_max_output_tokens`, `max_specialist_calls`, `est_tokens_per_user_day`,
`max_concurrent_per_user`, `requests_per_app_day`, `max_model_invocations`, `max_tool_iterations`,
`max_tokens_per_request`, `request_timeout_seconds`, `reserve_tokens_per_request`, `rejections_per_user_day`,
`routes_per_user_day`, `searches_per_user_day`. Unknown keys and negative values are ignored.
Every admin change is logged with the actor's `sub` (no tokens or message text are ever logged).

## Defaults
20 requests/user/day, 200/user/month, 500 chars, 4 history messages, 400 output tokens (main), 50 (classifier),
3 specialist calls/request, 30,000 estimated tokens/user/day, 1 concurrent request/user, 300 requests/app/day.
Counters reset at 00:00 UTC (daily) and the 1st (monthly).

## Hard stops vs alerts
Hard stops: server-side quotas, kill switch, disabled users, `ApiReservedConcurrency`, per-request model/tool/token
limits. **Alerts do not stop spend**: AWS Budgets and CloudWatch alarms only notify.
