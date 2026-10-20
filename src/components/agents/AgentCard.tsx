import { Bot, Clock } from 'lucide-react';
import { Card } from '../ui/Card';
import { LinkButton } from '../ui/Button';
import type { Agent } from '../../types/agent';

export function AgentCard({ agent }: { agent: Agent }) {
  const live = agent.status === 'demo';
  return (
    <Card className="flex h-full flex-col gap-4 transition hover:border-accent/40">
      <div className="flex items-start justify-between gap-3">
        <span
          className={`grid h-10 w-10 place-items-center rounded-xl ${
            live ? 'brand-gradient text-white' : 'bg-surface-2 text-muted'
          }`}
        >
          {live ? <Bot size={20} aria-hidden /> : <Clock size={18} aria-hidden />}
        </span>
        <span
          className={`rounded-full border px-2.5 py-0.5 text-xs ${
            live
              ? 'border-emerald-500/40 text-emerald-700 dark:text-emerald-300'
              : 'border-line text-muted'
          }`}
        >
          {agent.statusLabel}
        </span>
      </div>
      <div className="flex-1">
        <h3 className="font-semibold">{agent.name}</h3>
        <p className="mt-1 text-sm text-muted">{agent.description}</p>
        <ul className="mt-3 space-y-1 text-xs text-muted">
          {agent.capabilities.map((c) => (
            <li key={c}>• {c}</li>
          ))}
        </ul>
      </div>
      {agent.interactive ? (
        <LinkButton to={`/chat/${agent.id}`}>Try the demo</LinkButton>
      ) : (
        <button
          type="button"
          disabled
          className="rounded-xl border border-line px-4 py-2.5 text-sm text-muted opacity-60"
        >
          Not available yet
        </button>
      )}
    </Card>
  );
}
