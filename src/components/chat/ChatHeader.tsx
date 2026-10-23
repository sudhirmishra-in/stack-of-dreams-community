import { Menu, Plus } from 'lucide-react';
import type { Agent } from '../../types/agent';

interface Props {
  agent: Agent;
  isMock: boolean;
  onOpenSidebar: () => void;
  onNewConversation: () => void;
}

export function ChatHeader({ agent, isMock, onOpenSidebar, onNewConversation }: Props) {
  return (
    <div className="flex items-center justify-between gap-2 border-b border-line px-3 py-2.5">
      <div className="flex min-w-0 items-center gap-2">
        <button
          type="button"
          onClick={onOpenSidebar}
          aria-label="Open agents sidebar"
          className="rounded-lg p-2 text-muted hover:bg-surface-2 md:hidden"
        >
          <Menu size={18} aria-hidden />
        </button>
        <h1 className="truncate text-sm font-semibold">{agent.name}</h1>
        <span
          className={`shrink-0 rounded-full border px-2 py-0.5 text-[11px] ${
            isMock
              ? 'border-amber-500/40 text-amber-700 dark:text-amber-300'
              : 'border-emerald-500/40 text-emerald-700 dark:text-emerald-300'
          }`}
        >
          {isMock ? 'Mock mode' : 'Live API'}
        </span>
        <span className="hidden text-[11px] text-muted md:inline">
          Saved in this browser until you start a new chat
        </span>
      </div>
      <button
        type="button"
        onClick={onNewConversation}
        aria-label="New chat"
        title="Start a new chat. The conversation saved in this browser is replaced."
        className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs font-medium hover:bg-surface-2"
      >
        <Plus size={14} aria-hidden /> New chat
      </button>
    </div>
  );
}
