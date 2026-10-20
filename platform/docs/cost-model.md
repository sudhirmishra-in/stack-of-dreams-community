# Cost model (estimates, not quotes)

Prices below are **assumptions to verify** on the AWS pricing pages; `src/navigator/quota/pricing.json` is
versioned config (`2026-10-19-unverified`) used only for estimated-spend tracking, never for billing.

## Worst-case design ceilings (what the quotas allow)
* 300 AI requests/day for the whole pilot. Each request is capped at 12,000 tokens and 8 model calls.
  Theoretical ceiling 3.6 M tokens/day; realistic requests use roughly 3-5 k tokens (system prompt + tool results).
* Using the unverified pricing file (Nova Lite about $0.06 in / $0.24 out per 1M tokens, Nova Micro cheaper):
  3.6 M tokens/day at an 85/15 input/output split is about $0.30/day (about $9/month) worst case for model tokens.
  The classifier adds a few cents. If Bedrock prices differ or you swap in a larger model, rescale this table:
  `cost = tokens/1e6 x price`.

| Component | Pilot assumption | Expected |
| --- | --- | --- |
| Bedrock tokens | see above | single-digit $/month worst case |
| AgentCore Runtime | seconds of active time per request, 300 req/day cap | low; verify consumption pricing |
| DynamoDB on-demand | ~25 request units per assistant request (reserve + settle + reads); search ~2 | well under $1/month |
| Lambda | <100k invocations | free tier / cents |
| CloudWatch | 30-day logs, ~10 alarms, 1 dashboard | ~$3-5/month (dashboard + alarms) |
| Amazon Location | ZIP geocodes cached forever (<= ~220 NYC ZIPs, Storage licence); map tiles per visit; routes capped 30/user/day | a few $ at most; verify |
| Amplify Hosting | build minutes + GB served | cents-$1 |
| Budgets | first 2 budgets free | $0 |

## Controls
Quotas -> reserved concurrency (API 10, ingest 1) -> kill switch -> `MonthlyBudgetUsd` budget (default $25) with
50/80/100%-forecast alerts to the SNS topic -> `TokenSpike` alarm (600k tokens/hour). Check Cost Explorer after
the first week and adjust the pricing file and quotas.


---

# Cost audit (2026-10-20, from real account data)

**Observed spend:** account month-to-date is about $0.00 after credits. Billable usage so far: AgentCore $0.20 and
AWS KMS $0.11 (both credit-offset); Bedrock tokens under $0.01. Usage in the last 24h: API Lambda 43 invocations,
ingestion 1.

## Fixed monthly costs (exist even with no traffic; estimates, verify on the pricing pages)
| Item | Why | Est. |
| --- | --- | --- |
| 2 KMS keys | each CDK bootstrap creates one customer-managed key (us-east-1 from `testagent`, us-east-2 from the runtime deploy) | ~$2.00 |
| 8 CloudWatch alarms | standard alarms at ~$0.10 each | ~$0.80 |
| 7 custom metrics | `Navigator` namespace: RecordsRejected (x2 sources), Api5xx, AgentInvokeFailed, AssistantRequests, ModelTokens, EstimatedSpendUsd, at ~$0.30 each | ~$2.10 |
| CloudWatch dashboard | first 3 dashboards free | $0 |
| DynamoDB point-in-time recovery | a few KB of data | under $0.01 |
| AWS Budgets, SNS, Scheduler, Cognito (1 user) | free tiers | $0 |
| **Total fixed** | | **about $5 / month** |

If a leaner setup is wanted, the controllable items are the alarms and metrics (~$3/month) and, once you are done
deploying, deleting the two `CDKToolkit` stacks (frees the two KMS keys, ~$2/month; future `agentcore deploy` runs would
need them again).

## Variable costs: every path has a bound that does not depend on user behavior
| Path | Driver | Bound (enforced server-side) |
| --- | --- | --- |
| Bedrock model tokens | assistant questions | 300 requests/day for the pilot, 20/user/day, 12k tokens and 8 model calls per request, 30k estimated tokens/user/day. Ceiling ~3.6M tokens/day, about $0.3/day at the (unverified) pricing file |
| AgentCore runtime | active CPU + session memory | same request caps; **idle session timeout lowered from 15 min to 2 min**, max session lifetime 15 min (the runtime is stateless: history is sent with each request) |
| Amazon Location geocoding (paid, storage-licensed) | search by ZIP | **NYC ZIP prefixes only** (a few hundred ZIPs, each cached forever), 25 new lookups/user/day, 200/day for the pilot |
| Amazon Location routes | route button, assistant `route_info` tool | 30/user/day, 500/day for the pilot |
| Amazon Location tiles (via the API proxy) | map views (~20-40 requests each, browser-cached 1 day) | 6,000/user/day, **30,000/day for the pilot** |
| Lambda | every request, including anonymous floods that get 401 | reserved concurrency: API 30, ingestion 1, **chat 10 (new)**; an unauthenticated call costs milliseconds |
| DynamoDB on-demand | ledger writes, searches | ~25 units per assistant request; ~4 per map tile (counters plus limits read); at the map cap this is a few cents/day |
| CloudWatch Logs | request logs | 30-day retention on **every** group created by this project, including the runtime, Application Signals, and the existing chat Lambda (which previously never expired) |
| S3 | SAM/CDK artifacts | ~190 MB total, cents/month |

## Remaining cost risks (accepted, or for you to decide)
* `testagent`'s runtime log group (`/aws/bedrock-agentcore/runtimes/<testagent runtime id>-DEFAULT`) has
  no retention (5 MB stored). I left it alone because it is outside this work. To cap it:
  `aws logs put-retention-policy --region us-east-1 --log-group-name <that group> --retention-in-days 30`.
* `testagent`'s harness has shell/file tools and no per-user quota. The existing `/chat` API requires login and now has a
  concurrency cap, but no token budget. Keep that audience small.
* Search reads the whole real directory for each query. At 29 records this costs nothing; add per-ZIP/geohash keys before
  the directory grows past a few thousand records.
* Alerts (Budgets, alarms) never stop spend. The hard stops are the quotas, the kill switch, disabling users, and the
  concurrency ceilings.
