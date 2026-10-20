# Monitoring and alarms

Dashboard `navigator-pilot` (CloudWatch): requests and tokens, estimated spend, errors and guard trips, sync
status, p95 latency, throttles/concurrency.

| Alarm | Meaning | Action |
| --- | --- | --- |
| api-lambda-errors | unhandled exception in the API | read logs by `correlationId` |
| ingest-lambda-errors / sync-failed | a source sync failed or returned a suspiciously small result | inspect `GET /admin/sync-status`; directory stays as-is (nothing deleted) |
| ingest-not-running | no ingest invocation for 3 days | check the Scheduler state |
| runtime-exceeded-limits | runtime reported more calls than allowed | investigate immediately; lower `max_model_invocations` or disable the assistant |
| usage-ledger-failures | settle/release failed; spend tracking conservative | check DynamoDB health/permissions |
| agent-invoke-failures | runtime unavailable | check the runtime; assistant answers 503 and refunds |
| token-spike | >600k tokens in an hour | check usage; consider the kill switch |
| AWS Budgets | actual 50%/80%, forecast 100% | review usage; **does not stop spend** |

Logs are structured JSON, retention 30 days, and never contain tokens, emails or message text.
