export type AgentStatus = 'demo' | 'coming-soon';

export interface Agent {
  id: string;
  name: string;
  description: string;
  status: AgentStatus;
  statusLabel: string;
  interactive: boolean;
  capabilities: string[];
  /** Where "open" goes when the agent has its own page instead of the general /chat/:id window. */
  route?: string;
  /** Button text for an interactive agent (default "Try the demo"). */
  actionLabel?: string;
}
