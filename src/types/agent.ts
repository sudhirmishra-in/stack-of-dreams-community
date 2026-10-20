export type AgentStatus = 'demo' | 'coming-soon';

export interface Agent {
  id: string;
  name: string;
  description: string;
  status: AgentStatus;
  statusLabel: string;
  interactive: boolean;
  capabilities: string[];
}
