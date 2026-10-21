import { useEffect, useRef, useState } from 'react';
import { Navigate, useLocation, useNavigate, useParams } from 'react-router';
import type { ChatContext } from '../types/chat';
import { X } from 'lucide-react';
import { Sidebar } from '../components/layout/Sidebar';
import { ChatHeader } from '../components/chat/ChatHeader';
import { ChatWindow } from '../components/chat/ChatWindow';
import { useChat } from '../hooks/useChat';
import { useBranding } from '../config/branding';
import { generalChatContext } from '../config/generalChat';

export default function ChatPage({ context }: { context?: ChatContext }) {
  const { agents, defaultAgentId } = useBranding();
  const { agentId = defaultAgentId } = useParams();
  const agent = agents.find((a) => a.id === agentId);
  if (!agent || !agent.interactive) return <Navigate to="/agents" replace />;
  // An agent with its own page (AI for Good) must never be served by the general chat window and service.
  if (agent.route && !context) return <Navigate to={agent.route} replace />;
  // The general assistant is served through the quota-enforcing pilot API whenever that API is configured.
  const resolved = context ?? (agent.id === 'assistant' ? generalChatContext() : undefined);
  return <ChatView key={agent.id} agentId={agent.id} context={resolved} />;
}

function ChatView({ agentId, context }: { agentId: string; context?: ChatContext }) {
  const { agents } = useBranding();
  const agent = agents.find((a) => a.id === agentId)!;
  const chat = useChat(agentId, context?.service, context?.conversationKey);
  const [drawer, setDrawer] = useState(false);

  // A prompt handed over by another page (e.g. "Ask AI" on a resource) is sent once, then cleared
  // from navigation state so a refresh does not resend it.
  const location = useLocation();
  const navigate = useNavigate();
  const initialPrompt = (location.state as { initialPrompt?: string } | null)?.initialPrompt;
  const sentInitial = useRef(false);
  useEffect(() => {
    if (!initialPrompt || sentInitial.current) return;
    sentInitial.current = true;
    navigate(location.pathname + location.search, { replace: true, state: null });
    void chat.sendMessage(initialPrompt);
  }, [initialPrompt, chat, navigate, location.pathname, location.search]);

  const sidebar = (
    <Sidebar
      agents={agents}
      activeAgentId={agentId}
      onNewConversation={chat.startNewConversation}
      onClear={chat.clearConversation}
      onNavigate={() => setDrawer(false)}
    />
  );

  return (
    <div className="flex h-[calc(100dvh-3.5rem)]">
      <aside className="hidden w-64 shrink-0 border-r border-line bg-surface/50 md:block">
        {sidebar}
      </aside>

      {drawer && (
        <div
          className="fixed inset-0 z-40 md:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Agents"
        >
          <button
            type="button"
            aria-label="Close sidebar"
            className="absolute inset-0 bg-black/50"
            onClick={() => setDrawer(false)}
          />
          <div className="relative h-full w-72 max-w-[85%] border-r border-line bg-bg">
            <button
              type="button"
              aria-label="Close"
              className="absolute right-2 top-2 rounded-lg p-2 text-muted hover:bg-surface-2"
              onClick={() => setDrawer(false)}
            >
              <X size={18} aria-hidden />
            </button>
            {sidebar}
          </div>
        </div>
      )}

      <section className="flex min-w-0 flex-1 flex-col" aria-label={`Chat with ${agent.name}`}>
        <ChatHeader
          agent={agent}
          isMock={chat.isMock}
          onOpenSidebar={() => setDrawer(true)}
          onNewConversation={chat.startNewConversation}
        />
        <ChatWindow
          agent={agent}
          messages={chat.messages}
          isLoading={chat.isLoading}
          isMock={chat.isMock}
          onSend={chat.sendMessage}
          onRetry={chat.retry}
          prompts={context?.prompts}
          notice={context?.notice}
        />
      </section>
    </div>
  );
}
