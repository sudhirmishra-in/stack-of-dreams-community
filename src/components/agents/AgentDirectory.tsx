import { AgentCard } from './AgentCard';
import { useBranding } from '../../config/branding';
import type { Agent } from '../../types/agent';

export function AgentDirectory({ agents }: { agents?: Agent[] }) {
  const branding = useBranding();
  const list = agents ?? branding.agents;
  return (
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-label="Agent directory">
      {list.map((a) => (
        <li key={a.id}>
          <AgentCard agent={a} />
        </li>
      ))}
    </ul>
  );
}
