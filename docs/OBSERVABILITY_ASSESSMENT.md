# Observability assessment (Phase 1)

Assessed 2026-10-21 against the repository (`main`) and the live AWS account, **read-only**: nothing was changed.
Account IDs, ARNs and endpoints are intentionally not recorded here (public repo); commands to re-check are in section 8.

Evidence labels: **[verified]** = observed directly in AWS or the deployed artifact; **[docs]** = from AWS documentation;
**[inferred]** = a conclusion drawn from verified facts; **[unknown]** = not yet determined.

## 1. Headline findings

1. **AgentCore traces are NOT reaching CloudWatch today** [verified]. CloudWatch Transaction Search is ACTIVE in us-east-2,
   the X-Ray-to-CloudWatch-Logs resource policy exists, and the runtime is invoked daily, yet the shared `aws/spans` log group
   has **0 events in 7 days**, X-Ray returns **0 traces in 24 hours**, and the runtime's own `spans` log stream is empty.
2. **Likely root cause** [inferred from verified facts]: the deployed `community_navigator` package contains the OpenTelemetry
   SDK and `opentelemetry-instrument` (the runtime entry point is `opentelemetry-instrument main.py`, and the log line
   "Attempting to instrument while already instrumented" confirms the wrapper runs), but it does **not** contain
   `aws-opentelemetry-distro` or an OTLP exporter (verified by listing the deployed zip). AgentCore's documentation requires
   `aws-opentelemetry-distro>=0.18.0` for spans to be delivered [docs]. `platform/agentcore/app/community_navigator/pyproject.toml`
   lists only `strands-agents`, `bedrock-agentcore`, `boto3`, `pydantic`. This must be confirmed by fixing it and observing spans,
   not assumed.
3. **Specialist agents cannot be told apart in traces** [verified in code]: the orchestrator and the four specialist agents are
   created without a `name`, so even with spans flowing they would all appear as unnamed Strands agents.
4. **Only 4 of the 15 requested custom metrics exist, none with dimensions, in a different namespace** [verified in code].
5. **Alerts do not reach a person** [verified]: all 8 alarms have an action (the SNS topic), but the e-mail subscription on that topic
   is still `PendingConfirmation`.
6. **The research harness and `testagent` (us-east-1) cannot use Transaction Search/X-Ray** [verified]: an organization SCP
   explicitly denies `xray:GetTraceSegmentDestination` in us-east-1 (consistent with the earlier finding that X-Ray is denied in
   us-east-1). GenAI-style tracing for those two harnesses is therefore not available unless the SCP changes. Their AgentCore
   runtime log groups have **no retention** set (testagent's holds ~8 MB and grows forever).

## 2. What is enabled, missing or misconfigured

| Area                               | State                                                                                                                                                                                                       | Evidence                                                                                                                                                                                         |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Transaction Search (us-east-2)     | **Enabled**: destination CloudWatchLogs, status ACTIVE; indexing rule "Default" = **100 %**                                                                                                                 | [verified] `xray get-trace-segment-destination`, `get-indexing-rules`. Enabled as a side effect of `agentcore deploy` ("Transaction search enabled" in its output), not by a deliberate decision |
| Transaction Search (us-east-1)     | **Blocked** by SCP                                                                                                                                                                                          | [verified] explicit deny on `xray:GetTraceSegmentDestination`                                                                                                                                    |
| ADOT in the navigator runtime      | **Missing** (no `aws-opentelemetry-distro`, no OTLP exporter in the deployed zip)                                                                                                                           | [verified] zip listing                                                                                                                                                                           |
| Runtime execution role permissions | Has `xray:PutTraceSegments`, `xray:PutTelemetryRecords`, `logs:PutResourcePolicy`, logs write                                                                                                               | [verified] sufficient for span delivery                                                                                                                                                          |
| Runtime telemetry env vars         | None set (only `DATA_TABLE`, `ENV_NAME`, `ORCHESTRATOR_MODEL_ID`)                                                                                                                                           | [verified]; AgentCore normally injects ADOT defaults for runtimes [docs]                                                                                                                         |
| Span destination for this runtime  | Its own log group (`spans` and `otel-rt-logs` streams exist, both empty)                                                                                                                                    | [verified]                                                                                                                                                                                       |
| Runtime application logs           | JSON lines from `bedrock_agentcore.app` include `requestId`, duration; our own `log()` events also appear                                                                                                   | [verified]                                                                                                                                                                                       |
| Lambda X-Ray tracing               | `PassThrough` (no active tracing) on API, ingest, signup and the chat Lambda                                                                                                                                | [verified]                                                                                                                                                                                       |
| Strands telemetry                  | No explicit tracer/`name=` on agents; `strands-agents` 1.61.1 has built-in OTel hooks that need an exporter                                                                                                 | [verified]                                                                                                                                                                                       |
| Correlation                        | API `correlationId` is logged in Lambda but **not sent** to the runtime payload; no trace id propagated                                                                                                     | [verified in code]                                                                                                                                                                               |
| Token accounting                   | Real per-model tokens settled in the usage ledger (navigator: from the runtime meter; research: from harness stream metadata). No per-agent split (specialists are summed into the model totals)            | [verified in code]                                                                                                                                                                               |
| Log retention                      | 30 days on all navigator/chat log groups and `aws/spans`; **none** on the two us-east-1 AgentCore harness log groups                                                                                        | [verified]                                                                                                                                                                                       |
| Metrics format                     | CloudWatch Embedded Metric Format printed to stdout (no `PutMetricData` calls, no extra IAM)                                                                                                                | [verified]                                                                                                                                                                                       |
| Dashboard                          | `navigator-pilot`: 6 widgets (requests/tokens, estimated spend, errors and guard trips, data sync, Lambda duration, throttles/concurrency)                                                                  | [verified]                                                                                                                                                                                       |
| Alarms                             | 8: agent-invoke-failures, api-lambda-errors, ingest-lambda-errors, ingest-not-running, runtime-exceeded-limits, sync-failed, token-spike, usage-ledger-failures. `sync-failed` has a 24 h period so it lags | [verified]                                                                                                                                                                                       |
| Data-sync status                   | DynamoDB `SYNC#<source>` state/run records (status, lastSuccessAt, counts, errors)                                                                                                                          | [verified]                                                                                                                                                                                       |
| Log hygiene                        | `log()` drops keys `authorization, token, query, message, email, password, api_key`; users are identified by a SHA-256 of the Cognito `sub`                                                                 | [verified in code]                                                                                                                                                                               |

## 3. Gap against the requested metrics

Existing namespace: `Navigator` (no dimensions). Requested namespace: `CommunityNavigator/Production`.

| Requested                                  | Today                                                                                  |
| ------------------------------------------ | -------------------------------------------------------------------------------------- |
| AgentInvocations                           | Partial: `AssistantRequests` (API level, not per agent)                                |
| AgentErrors                                | Partial: `AgentInvokeFailed`                                                           |
| AgentLatency                               | **Missing** (only Lambda `Duration`; no request-level latency, so no real P50/P95/P99) |
| ModelInputTokens / ModelOutputTokens       | Partial: one combined `ModelTokens` (no model dimension)                               |
| EstimatedModelCost                         | Partial: `EstimatedSpendUsd`                                                           |
| ToolInvocations / ToolErrors               | **Missing** (counted in the per-request meter, never emitted)                          |
| QuotaRejections                            | **Missing** (429s are returned, not counted)                                           |
| AuthenticationFailures                     | **Missing** (401/403 are returned, not counted)                                        |
| ResourceSearches / ResourceSearchNoResults | **Missing**                                                                            |
| DataSyncSuccess / DataSyncFailures         | Partial: `SyncFailed`, `SyncSuspicious`, `RecordsRejected`                             |
| DataSyncAge                                | **Missing** (derivable from `lastSuccessAt`)                                           |

## 4. Billing impact of enabling traces (from AWS pricing pages [docs]; verify before relying)

- Spans ingested through Transaction Search are billed as CloudWatch Logs-style ingestion: about **$0.35/GB** (first 10 TB), with
  a **100 GB free allowance for the first 3 months**.
- **Indexing** spans as X-Ray trace summaries: **$0.75 per million indexed spans beyond the 1 % included**. The account's
  indexing rule is currently **100 %**, so every span would be indexed and billed once spans flow. At this pilot's volume
  (a few hundred assistant requests a day, tens of spans each) that is on the order of cents per month, but the percentage is
  a one-line control and should be lowered (for example to 1 to 5 %) before ingestion starts.
- Custom metrics: **$0.30 per metric per month** (first 10,000); each distinct metric name and dimension combination is a
  separate metric. 15 metrics x a handful of low-cardinality dimension sets is roughly **$5 to $30/month**; this, not traces, is
  the larger cost driver and is controlled by keeping dimensions few.
- Dashboards: 3 free; alarms: **$0.10 per alarm metric per month** (10 free). Logs storage stays at the existing 30-day retention.
- Application Signals (if ever enabled) is billed per signal and is **not** part of this plan.

## 5. Privacy and security observations

- Spans from GenAI frameworks can carry **prompts, model outputs and tool inputs/outputs**. The docs describe an
  `AWS_GENAI_CONTENT_EXTRACTION_OPT_OUT` setting whose exact behaviour is ambiguous [docs]. **[unknown]** whether content would
  appear on spans for this runtime. This must be tested with real spans and an explicit decision made before ingestion is left
  on, because the public Privacy Policy states that message text is not written to logs.
- Current logs contain no tokens, emails or prompts by construction (`log()` allow-list/deny-list), and use a hashed user key.
- AgentCore session ids passed to the runtime are SHA-256 hashes of `sub:sessionId`, which is already pseudonymous.

## 6. What this means for the plan

1. Fix span export first (add the ADOT distro, name every agent, pass a correlation id), because everything in the GenAI view depends on it.
2. Before any ingestion: lower the X-Ray indexing percentage, decide content capture, and confirm retention (30 days).
3. Add the missing metrics through the existing EMF mechanism (no new IAM, no `PutMetricData`), under a configurable namespace, with bounded dimensions.
4. Build the dashboard and alarms in the SAM stack; fix alert delivery (confirm the SNS subscription) so alarms are meaningful.
5. us-east-1 harnesses: cannot be traced under the current SCP; use their service-provided runtime metrics/logs and set 30-day retention (needs approval).

## 7. Decisions needed from the owner

- Namespace: keep `Navigator` for the existing 11 metrics and add `CommunityNavigator/Production`, or move everything (dashboards/alarms would be updated together).
- Trace sampling/indexing percentage and whether prompt/response content may ever appear on spans (recommended: no).
- Whether to enable Lambda active tracing (X-Ray) on the API Lambda in us-east-2 (cost is small; adds cross-service traces).
- Whether to ask the organization to relax the SCP for X-Ray in us-east-1 (not required for the rest of the plan).

## 8. How to re-check (read-only)

```bash
aws xray get-trace-segment-destination --region us-east-2
aws xray get-indexing-rules --region us-east-2
aws logs describe-log-groups --region us-east-2 --log-group-name-prefix aws/spans
aws logs describe-log-streams --region us-east-2 --log-group-name <runtime log group> --log-stream-name-prefix spans
aws lambda get-function-configuration --region us-east-2 --function-name navigator-api-pilot --query TracingConfig
aws cloudwatch describe-alarms --region us-east-2 --alarm-name-prefix navigator-pilot
```
