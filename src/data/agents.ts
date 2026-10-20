import type { Agent } from '../types/agent';

export const AGENTS: Agent[] = [
  {
    id: 'assistant',
    name: 'AI Assistant',
    description: 'General-purpose AI assistant powered by Amazon Bedrock AgentCore.',
    status: 'demo',
    statusLabel: 'Demo available',
    interactive: true,
    capabilities: ['Conversational Q&A', 'Markdown & code answers', 'Session-aware follow-ups'],
  },
  {
    id: 'research',
    name: 'Research Agent',
    description: 'Specialized agent for technical research and analysis.',
    status: 'coming-soon',
    statusLabel: 'Coming soon',
    interactive: false,
    capabilities: ['Planned: technical research', 'Planned: structured analysis'],
  },
  {
    id: 'orchestrator',
    name: 'Multi-Agent Orchestrator',
    description: 'Coordinates specialized AI agents.',
    status: 'coming-soon',
    statusLabel: 'Coming soon',
    interactive: false,
    capabilities: ['Planned: agent routing', 'Planned: multi-step workflows'],
  },
];

export const DEFAULT_AGENT_ID = 'assistant';

export const getAgent = (id: string): Agent | undefined => AGENTS.find((a) => a.id === id);
