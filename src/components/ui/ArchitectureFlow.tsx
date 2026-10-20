import { ArrowDown } from 'lucide-react';

export interface ArchNode {
  name: string;
  role: string;
  detail: string;
}

export const ARCH_NODES: ArchNode[] = [
  {
    name: 'React Frontend',
    role: 'User interface',
    detail:
      'Renders the chat experience, keeps the session ID, and sends messages to the API. Holds no AWS credentials.',
  },
  {
    name: 'Amazon API Gateway',
    role: 'Public API entry point',
    detail:
      'Exposes the HTTPS endpoint (POST /chat), and is the place for CORS, throttling and authorization.',
  },
  {
    name: 'AWS Lambda',
    role: 'Integration layer',
    detail:
      'Validates the request and invokes AgentCore Runtime with the session ID using its own IAM role, keeping credentials out of the browser.',
  },
  {
    name: 'Amazon Bedrock AgentCore Runtime',
    role: 'Managed agent hosting',
    detail: 'Runs the agent container in isolated, session-aware sessions and handles scaling.',
  },
  {
    name: 'Strands AI Agent',
    role: 'Agent logic',
    detail:
      'The agent loop: system prompt, reasoning, and tool use, built with the Strands Agents SDK.',
  },
  {
    name: 'Amazon Bedrock Foundation Model',
    role: 'Language model',
    detail: 'Generates the reasoning and responses the agent relies on.',
  },
];

export const PROPOSED_NODES: ArchNode[] = [
  {
    name: 'React UI',
    role: 'Reusable shell',
    detail: 'Project-specific branding, navigation and agent configuration on the shared frontend.',
  },
  {
    name: 'Amazon API Gateway',
    role: 'API entry point',
    detail: 'HTTPS endpoint for the project application.',
  },
  {
    name: 'AWS Lambda',
    role: 'Integration layer',
    detail: 'Validates requests and invokes the agent runtime.',
  },
  {
    name: 'Amazon Bedrock AgentCore',
    role: 'Managed agent hosting',
    detail: 'Hosts the project agent.',
  },
  {
    name: 'Strands Agents',
    role: 'Agent logic',
    detail: 'Project-specific agent behavior and tools.',
  },
];

export function ArchitectureFlow({
  compact = false,
  nodes = ARCH_NODES,
}: {
  compact?: boolean;
  nodes?: ArchNode[];
}) {
  return (
    <ol
      className="mx-auto flex max-w-xl flex-col items-stretch"
      aria-label="Target architecture flow"
    >
      {nodes.map((n, i) => (
        <li key={n.name} className="flex flex-col items-center">
          <div className="w-full rounded-xl border border-line bg-surface px-4 py-3 text-center">
            <p className="text-sm font-semibold">{n.name}</p>
            {!compact && <p className="text-xs text-muted">{n.role}</p>}
          </div>
          {i < nodes.length - 1 && (
            <ArrowDown size={18} className="my-1 text-accent-2" aria-hidden />
          )}
        </li>
      ))}
    </ol>
  );
}
