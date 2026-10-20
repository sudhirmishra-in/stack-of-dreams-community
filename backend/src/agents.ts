/**
 * Maps the frontend's agentId to a deployed AgentCore harness ARN.
 * Configured via the AGENT_HARNESS_MAP env var: {"assistant":"arn:aws:bedrock-agentcore:...:harness/..."}.
 */
export type AgentMap = Record<string, string>;

export function parseAgentMap(raw: string | undefined): AgentMap {
  if (!raw) return {};
  try {
    const parsed: unknown = JSON.parse(raw);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return Object.fromEntries(
        Object.entries(parsed).filter((e): e is [string, string] => typeof e[1] === 'string'),
      );
    }
  } catch {
    /* fall through */
  }
  return {};
}
