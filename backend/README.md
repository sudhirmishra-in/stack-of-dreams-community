# Backend: chat API

`POST /chat` → Lambda Function URL → Lambda (verifies the Cognito token) → Amazon Bedrock AgentCore harness.

API Gateway is not used: the account's organization policy denies tagging HTTP APIs, so the Lambda does the authentication itself.

Request / response match the frontend contract:

```json
{ "message": "Hello", "sessionId": "<uuid>", "agentId": "assistant" }
{ "response": "…", "sessionId": "<uuid>", "agentId": "assistant" }
```

## Behavior

- The Lambda verifies the Cognito **access token** (signature, issuer, expiry, `token_use`, app client ID) with `aws-jwt-verify` before doing anything else. The Function URL uses `AuthType NONE`, so this check is the only gate; invalid requests get 401.
- `agentId` is looked up in `AGENT_HARNESS_MAP`; unknown agents get 404. To add an agent, add a parameter and an entry in `template.yaml` plus IAM permission for its harness.
- The runtime session ID is `sha256(userId:sessionId)`, so users cannot join each other's agent sessions, and it meets AgentCore's 33-character minimum.
- Message limit 4000 chars, body limit 16 KB, no built-in throttling (consider reserved concurrency). Errors return generic messages; details go to CloudWatch.
- Model `<thinking>…</thinking>` text is stripped from replies. Responses are not streamed.

## Local checks

```bash
npm install
npm run typecheck && npm test && npm run build
```

## Deploy

Deployed as stack `stack-of-dreams-api` in us-east-1 (same region as the harness; Cognito can stay in us-east-2). Requires the AWS SAM CLI and credentials.

```bash
export PATH=$PWD/node_modules/.bin:$PATH   # SAM needs esbuild on PATH
sam build
sam deploy --stack-name stack-of-dreams-api --region us-east-1 --resolve-s3 \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    CognitoUserPoolId=us-east-2_tPaKrhmEX \
    CognitoClientId=<app client id> \
    AssistantHarnessArn=<testagent harness ARN> \
    "AllowedOrigins=https://agents.sudhirmishra.in,http://localhost:5173"
```

The `ApiBaseUrl` output (a Lambda Function URL) goes in the frontend `.env`:

```
VITE_USE_MOCK_API=false
VITE_API_BASE_URL=<ApiBaseUrl output>
```

To tear down: `aws cloudformation delete-stack --stack-name stack-of-dreams-api --region us-east-1`.

## Security notes

- The `testagent` harness has shell and file tools plus a food-bank gateway. Any signed-in user can ask it to run commands in its sandbox. Restrict who can sign in (Cognito sign-up settings) or use a harness with only the tools you want exposed.
- Everything signed-in users can reach is billed to your account; keep the throttle and consider a Cognito user limit or AWS Budgets alert.
