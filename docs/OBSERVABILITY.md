# Observability (AgentCore, CloudWatch, alarms)

Status: **Phase 2 (span export) is DEPLOYED and verified with real spans** (runtime version 9, 2026-10-22), with one follow-up: the scrubber's credential-ID rule was added AFTER that deploy and is not in the running runtime until the next runtime deploy. Phases 3 to 8 (structured logging everywhere,
custom metrics, dashboard, alarms, smoke tests, admin page) are planned and listed in `docs/OBSERVABILITY_ASSESSMENT.md`.
Do not describe tracing as working until real spans have been seen in CloudWatch (section 4).

Decisions made by the owner (2026-10-21): no prompt/response content on spans; X-Ray indexing lowered to 1 %; keep the
existing `Navigator` metric namespace and add `CommunityNavigator/Production` alongside it.

## 1. What was wrong (verified)

Transaction Search was on, but the runtime exported **no spans**: the deployed package had the OpenTelemetry SDK and the
`opentelemetry-instrument` wrapper but not `aws-opentelemetry-distro`/an OTLP exporter, which AgentCore requires. Specialist
agents were unnamed. The API correlation id never reached the runtime. See the assessment for the full list.

## 2. What the code now does (Phase 2)

| Change                                                                                                                                                                                                                                                                                                                                                                                                          | File                                                        |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| Add `aws-opentelemetry-distro>=0.18.0` (resolves to 0.21.0 with OTLP exporters for Linux arm64/py3.12)                                                                                                                                                                                                                                                                                                          | `platform/agentcore/app/community_navigator/pyproject.toml` |
| Name every agent: `orchestrator`, `resource_discovery`, `inventory`, `capacity`, `location` (appear as `gen_ai.agent.name`)                                                                                                                                                                                                                                                                                     | `agents/orchestrator.py`                                    |
| **Scrub message content from spans before export**: drops `gen_ai.*` content events and prompt/completion/messages/tool-argument/result/system-prompt attributes, exception messages and stack traces, and span status text. Keeps agent/tool names, model id, token counts, durations, status, error TYPES. Runs as the first span processor; if that cannot be guaranteed it shuts tracing down (fail closed) | `agents/telemetry.py`                                       |
| Pass the API's `correlationId` to the runtime (validated `[A-Za-z0-9_-]{8,64}`, else ignored), attach it to the active span as `correlation.id`, and log one structured `agent_invocation` line (service, environment, agentName, correlationId, status, durationMs, model, tokens, no prompt/answer/user id)                                                                                                   | `gateway/pipeline.py`, `agents/runtime.py`                  |

Why the scrubber exists: Strands puts user prompts, model replies, system prompts and tool inputs/outputs on spans and has no
switch to turn that off (verified in its source). Spans go to CloudWatch Logs, and the public Privacy Policy says message text is
not logged.

Tests (`platform/tests/test_telemetry.py`, 17): content is absent from exported spans even when the exporter was registered first;
non-sensitive telemetry survives; fail-closed outcomes; names on real Strands spans produced by the real agent loop; correlation id
validation and that the prompt never appears in logs; distro packaged. The end-to-end test runs the real Strands loop with a
scripted model and asserts a secret string in the prompt, tool input and replies is not in any exported span.

## 2b. Verified on the live runtime (2026-10-22)

Canary question with a unique string and a correlation id, plus the standard answer check (answers unchanged):

- 55 spans in the runtime's own `spans` log stream (before the fix: none). Log line `tracing_content_safety: scrubbing`.
- Canary string and other prompt fragments (ZIPs, place names, question text): **0 hits** in span data. The only event kept was `exception` with the error type only.
- Agent names seen: `orchestrator`, `resource_discovery` (inventory, capacity and location not yet exercised). Token attributes on 28 spans. `correlation.id` present and matching the `agent_invocation` log line.
- Observed leftover: `aws.auth.account.access_key` (a temporary credential key ID, not a secret) on DynamoDB spans. Now scrubbed in code (`CREDENTIAL_KEYS`); takes effect at the next runtime deploy.
- Not checked: the CloudWatch GenAI Observability console view (data was read from the log stream).
- Packaged versions at deploy: aws-opentelemetry-distro 0.21.0, OpenTelemetry SDK 1.44.0, Strands 1.62.0; tests also pass against exactly these.

## 3. Deploy plan (every step needs owner approval)

1. **Lower trace indexing first** (account-level X-Ray setting, us-east-2): `aws xray update-indexing-rule --region us-east-2 --name Default --rule '{"Probabilistic":{"DesiredSamplingPercentage":1}}'`. Currently 100 % (indexed spans beyond the 1 % included cost $0.75 per million). Rollback: set it back to 100.
2. `platform/scripts/sync_runtime.sh`, then `cd platform/agentcore && agentcore validate && agentcore deploy --target default --diff` (preview), then `agentcore deploy -y`. Creates a new runtime version; the ARN does not change.
3. Redeploy `navigator-pilot` via change-set so the API sends `correlationId` (optional field: the old runtime ignores it, so order is not critical).
4. Verify (section 4). If spans leak content or the runtime misbehaves: redeploy the previous commit's runtime (rollback), or set `DISABLE_ADOT_OBSERVABILITY=true` on the runtime.

Cost of this phase: nothing new is provisioned. Once spans flow, ingestion is about $0.35/GB (100 GB free for 3 months) and
indexing at 1 % is within the included amount. At pilot volume this is cents per month. Retention stays 30 days.

## 4. Verification (do not claim success before this)

Run one canary question containing a unique string through the API (or `platform/scripts/live_agent_check.py`), then:

```bash
# spans arrived?  (runtime's own log group, stream "spans", or the shared aws/spans)
aws logs start-query --region us-east-2 --log-group-name aws/spans --start-time $(($(date +%s)-3600)) --end-time $(date +%s) \
  --query-string 'fields @timestamp, name, attributes.gen_ai.agent.name | sort @timestamp desc | limit 20'
# CANARY: the unique string must NOT appear anywhere in spans
aws logs start-query --region us-east-2 --log-group-name aws/spans --start-time $(($(date +%s)-3600)) --end-time $(date +%s) \
  --query-string 'fields @message | filter @message like /<canary>/ | limit 5'
```

Expected: spans with `orchestrator` (and specialist names when delegated), token attributes, `correlation.id`, and zero canary hits. Also confirm the
runtime log line `tracing_content_safety` says `scrubbing`.

## 5. Limits

- The research harness and `testagent` live in us-east-1 where an organization policy blocks X-Ray/Transaction Search: no GenAI traces for them.
- Reordering span processors uses OpenTelemetry SDK internals; the fail-closed check and the post-deploy canary exist because of that.
