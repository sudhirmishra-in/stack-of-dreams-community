# research-agent (general AI Assistant)

AgentCore **harness** (declarative agent, no code): a general research and technical assistant on Amazon Nova Lite with
no tools, no memory, a firm "never give specific citations" rule, and a short accurate fact sheet about agentic AI,
Bedrock AgentCore and Strands Agents. Food-assistance questions are redirected to the separate AI for Good Assistant.

- Config: `app/researchagent/harness.json` (model, limits, prompt). `system-prompt.md` mirrors the prompt.
- Limits (cost): 800 output tokens per reply, 6 iterations, 8,000 tokens and 60 s per request, sessions end after 120 s idle.
- Deploy (us-east-1, needs approval): `agentcore validate && agentcore deploy --target default -y`. Preview: `agentcore deploy --target default --diff`.
- Served to the website through the pilot API (`agent: "research"`), which adds sign-in, approval, quotas and the kill switch.
  See `docs/OPERATIONS_RUNBOOK.md` section 2b.
- After changing the prompt, redeploy and re-read real answers (no unit test can judge them); `platform/scripts/live_agent_check.py`
  targets the navigator runtime, and a harness can be called directly with `InvokeHarness` using your AWS credentials.
