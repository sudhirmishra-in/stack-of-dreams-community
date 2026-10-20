# Architecture

```
                       Browser (React, Amplify-hosted at agents.sudhirmishra.in)
                          |  Cognito hosted UI (Authorization Code + PKCE)  -> access token (Bearer)
                          v
        +-----------------------------------------------------------------+
        |  API Lambda (Function URL, us-east-2)   navigator.api.app       |
        |   1 verify Cognito access token (signature, iss, exp, client_id)|
        |   2 route: /resources/search  /resources/{id}  /route          |
        |             /assistant  /me/usage  /sync-status  /admin/*       |
        +--------+----------------------+------------------+-------------+
                 | deterministic        | assistant only   | on demand
                 v                      v                  v
        DynamoDB (data)         VALIDATION GATEWAY    Amazon Location (geocode ZIP,
        resources/inventory/    1 kill switch / disabled user         route)  ZIP cache in DynamoDB
        activity/sync/zip-cache 2 sanitize + length (500 chars)
                 ^              3 idempotent replay
                 |              4 deterministic domain rules  --reject--> fixed 422, no model
                 |              5 ATOMIC quota reservation    --refuse--> 429/409/503, no model
        DynamoDB (usage)  <---- 6 Nova Micro classifier (ambiguous only)
        counters, slots,        7 invoke AgentCore runtime
        reservations            8 settle ACTUAL tokens + estimated USD
                                      |
                                      v
                      AgentCore Runtime  community_navigator   (separate from testagent)
                       Orchestrator (Strands, Nova Lite, 400 out tokens)
                        |- deterministic tools: search / details / inventory / capacity / route
                        '- specialist agent-tools: discovery, inventory, capacity, location (cap 3 / request)
                       LimitsHook: invocations, tool calls, tokens, wall clock  -> cancels calls
                       guard_response: strips contact/quantity claims not present in tool data

EventBridge Scheduler -> Ingestion Lambda -> adapters (OSM, NYC CFC, 211*, partner*) ->
   validate -> normalize -> dedupe/merge -> optimistic-locked upsert -> DynamoDB (data)
```

`testagent` and the existing `/chat` Lambda (us-east-1) are untouched. The legacy chat page keeps using them.

## Why it is shaped this way
* **Deterministic first.** Search, filtering, sorting, distance and map interaction never call a model.
* **Gate before spend.** Everything that can stop a request (auth, schema, quota, domain) runs before any
  model, and each stop is tested to prove no model was invoked.
* **Grounded output.** Citations, freshness, verification and caveats are computed from what the tools
  returned, not from what the model says.
* **Fail closed.** Missing auth configuration, an unreachable ledger or a classifier error refuse the request.

## Components and IAM (least privilege, one role each)
| Component | Can do | Cannot do |
| --- | --- | --- |
| Ingestion Lambda | read/write data table | usage table, Bedrock, AgentCore, Location |
| API Lambda | read data table, write ZIP cache keys only, usage table, classifier model only, invoke the community_navigator runtime ARN only, Location geocode/route | invoke testagent or any other runtime; write directory records |
| Runtime role | read data table, write ZIP cache keys only, orchestrator model only, Location | write the usage table, write directory records |
| Browser map key | map read actions on the allowed referrers | everything else |

## Data model
See `src/navigator/store/schema.py` (access patterns documented beside the keys).
