import { Link } from 'react-router';
import { Bot, Lock, Plus, Trash2 } from 'lucide-react';
import type { Agent } from '../../types/agent';

interface Props {
  agents: Agent[];
  activeAgentId: string;
  onNewConversation: () => void;
  onClear: () => void;
  onNavigate?: () => void;
}

export function Sidebar({ agents, activeAgentId, onNewConversation, onClear, onNavigate }: Props) {
  return (
    <div className="flex h-full flex-col gap-4 p-3">
      <button
        type="button"
        onClick={() => {
          onNewConversation();
          onNavigate?.();
        }}
        className="flex items-center justify-center gap-2 rounded-xl border border-line bg-surface px-3 py-2.5 text-sm font-medium transition hover:bg-surface-2"
      >
        <Plus size={16} aria-hidden /> New conversation
      </button>

      <nav aria-label="Agents" className="flex-1 overflow-y-auto">
        <h2 className="px-2 pb-2 text-xs font-semibold uppercase tracking-wider text-muted">
          Agents
        </h2>
        <ul className="space-y-1">
          {agents.map((a) => {
            const active = a.id === activeAgentId;
            const inner = (
              <>
                <span
                  className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg ${
                    a.interactive ? 'brand-gradient text-white' : 'bg-surface-2 text-muted'
                  }`}
                >
                  {a.interactive ? <Bot size={16} aria-hidden /> : <Lock size={14} aria-hidden />}
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium">{a.name}</span>
                  <span className="block truncate text-xs text-muted">{a.statusLabel}</span>
                </span>
              </>
            );
            return (
              <li key={a.id}>
                {a.interactive ? (
                  <Link
                    to={`/chat/${a.id}`}
                    aria-current={active ? 'page' : undefined}
                    onClick={onNavigate}
                    className={`flex items-center gap-3 rounded-xl px-2 py-2 transition ${
                      active ? 'bg-surface-2 ring-1 ring-accent/40' : 'hover:bg-surface-2'
                    }`}
                  >
                    {inner}
                  </Link>
                ) : (
                  <div
                    aria-disabled="true"
                    className="flex cursor-not-allowed items-center gap-3 rounded-xl px-2 py-2 opacity-60"
                  >
                    {inner}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="space-y-2 border-t border-line pt-3">
        <button
          type="button"
          onClick={() => {
            onClear();
            onNavigate?.();
          }}
          className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-sm text-muted transition hover:bg-surface-2 hover:text-fg"
        >
          <Trash2 size={14} aria-hidden /> Clear conversation
        </button>
        <p className="px-2 text-xs leading-relaxed text-muted">
          Chat history is kept in this browser's local storage, which is not appropriate for
          confidential or regulated information.
        </p>
      </div>
    </div>
  );
}
