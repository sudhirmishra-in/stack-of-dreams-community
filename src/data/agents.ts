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
    id: 'ai-for-good',
    name: 'AI for Good Assistant',
    description:
      'Helps families find food assistance near them, grounded in real NYC directory data. Every answer lists its sources and says when something is unknown.',
    status: 'demo',
    statusLabel: 'Pilot (invite-only)',
    interactive: true,
    capabilities: [
      'Find food pantries and food banks by ZIP code',
      'Nearest providers, with distances',
      'Says "unknown" instead of guessing inventory',
    ],
    route: '/ai-for-good/assistant',
    actionLabel: 'Open the AI for Good assistant',
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
