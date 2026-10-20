import { useEffect, useRef, type ReactNode } from 'react';
import { Sparkles } from 'lucide-react';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { SuggestedPrompts } from './SuggestedPrompts';
import { ThinkingIndicator } from './ThinkingIndicator';
import { ExperimentalNotice } from '../ui/ExperimentalNotice';
import type { Agent } from '../../types/agent';
import type { ChatMessageModel } from '../../types/chat';

interface Props {
  agent: Agent;
  messages: ChatMessageModel[];
  isLoading: boolean;
  isMock: boolean;
  onSend: (text: string) => void;
  onRetry: () => void;
  /** Optional context-specific starter prompts and notice (defaults keep the standard chat). */
  prompts?: string[];
  notice?: ReactNode;
}

export function ChatWindow({
  agent,
  messages,
  isLoading,
  isMock,
  onSend,
  onRetry,
  prompts,
  notice,
}: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, isLoading]);

  const empty = messages.length === 0;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div
        className="flex-1 overflow-y-auto"
        role="log"
        aria-live="polite"
        aria-label="Conversation"
      >
        <div className="mx-auto flex min-h-full max-w-3xl flex-col px-4 py-6">
          {empty ? (
            <div className="animate-fade-up my-auto flex flex-col items-center gap-6 py-10 text-center">
              <span className="grid h-14 w-14 place-items-center rounded-2xl brand-gradient text-white shadow-lg shadow-violet-900/30">
                <Sparkles size={26} aria-hidden />
              </span>
              <div>
                <h2 className="text-2xl font-semibold tracking-tight">How can I help today?</h2>
                <p className="mt-2 max-w-md text-sm text-muted">
                  {agent.description}{' '}
                  {isMock && 'Replies are simulated locally — no AWS agent is invoked.'}
                </p>
              </div>
              <SuggestedPrompts onSelect={onSend} disabled={isLoading} prompts={prompts} />
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((m, i) => (
                <ChatMessage
                  key={m.id}
                  message={m}
                  onRetry={onRetry}
                  canRetry={i === messages.length - 1 && !isLoading}
                />
              ))}
              {isLoading && <ThinkingIndicator />}
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>

      <div className="border-t border-line bg-bg px-4 pb-4 pt-3">
        <div className="mx-auto max-w-3xl space-y-2">
          <ChatInput onSend={onSend} disabled={isLoading} />
          {notice}
          <ExperimentalNotice />
        </div>
      </div>
    </div>
  );
}
