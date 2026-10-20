# Community Navigator pilot platform (backend)

Python 3.12 (`uv`). Shared package `src/navigator/` used by the ingestion Lambda, the API Lambda and the AgentCore
runtime. Start with `docs/architecture.md`; the plan and inspection findings are in `docs/00-plan.md`.

```bash
uv sync --group dev --group agent
uv run pytest                                   # 170 tests, no AWS needed (moto + fixtures)
./scripts/sam_build.sh                          # builds both Lambda packages (needs sam, uv)
sam validate --lint -t infra/template.yaml --region us-east-2
./scripts/sync_runtime.sh && (cd agentcore && agentcore validate)
```

| Path | What |
| --- | --- |
| `src/navigator/adapters` | OSM, NYC CFC, 211 (disabled), partner CSV; HTTP client with backoff |
| `src/navigator/ingest` | normalize, dedupe, sync runner, demo seed, Lambda handler |
| `src/navigator/store` | DynamoDB schema and repository |
| `src/navigator/search` + `location` | deterministic search, Amazon Location client with ZIP cache |
| `src/navigator/quota` | atomic usage ledger, versioned pricing |
| `src/navigator/gateway` | Cognito verification, validation, classifier, pipeline, runtime invoker |
| `src/navigator/api` | Function URL router and admin endpoints |
| `src/navigator/agents` | Strands orchestrator, specialists, tools, meter, safety guard, AgentCore entrypoint |
| `infra/` | SAM template (us-east-2) |
| `agentcore/` | separate AgentCore project for runtime `community_navigator` |
| `docs/` | architecture, ADRs, contracts, data sources, admin, cost, monitoring, deployment, Amplify/DNS, checklist |

Nothing here is deployed. See `docs/deployment.md` and `docs/checklist.md`.
