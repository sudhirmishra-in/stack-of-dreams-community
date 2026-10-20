import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { AlertTriangle, Bot, Check, Copy, RotateCw } from 'lucide-react';
import type { ChatMessageModel, Citation } from '../../types/chat';

interface Props {
  message: ChatMessageModel;
  onRetry?: () => void;
  canRetry?: boolean;
}

/** Raw HTML is never rendered: react-markdown ignores it unless rehype-raw is added. */
export function Markdown({ children }: { children: string }) {
  return (
    <div className="md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeHighlight, { detect: false, ignoreMissing: true }]]}
        skipHtml
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer nofollow">
              {children}
            </a>
          ),
          table: ({ children }) => (
            <div className="table-wrap">
              <table>{children}</table>
            </div>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}

function summarizeSources(citations: Citation[]): string {
  const demo = citations.filter((c) => c.isDemoData).length;
  const real = citations.length - demo;
  const parts = [];
  if (real)
    parts.push(
      `${real} directory ${real === 1 ? 'record' : 'records'} (community-sourced, unverified)`,
    );
  if (demo) parts.push(`${demo} demo ${demo === 1 ? 'record' : 'records'} (fictional sample data)`);
  return parts.join(' and ');
}

/** Server-computed provenance and caveats. Rendered only for answers that carry them (the pilot assistant). */
function Grounding({ citations, uncertainty }: { citations?: Citation[]; uncertainty?: string[] }) {
  const hasCaveats = !!uncertainty?.length;
  const hasSources = !!citations?.length;
  if (!hasCaveats && !hasSources) return null;
  return (
    <div
      className="mt-3 space-y-2 rounded-xl border border-line bg-surface-2 px-3 py-2 text-xs text-muted"
      data-testid="grounding"
    >
      {hasSources && (
        <p>
          <span className="font-medium text-fg">Based on:</span> {summarizeSources(citations!)}.
        </p>
      )}
      {hasCaveats && (
        <ul className="list-disc space-y-0.5 pl-4">
          {uncertainty!.map((u) => (
            <li key={u}>{u}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function ChatMessage({ message, onRetry, canRetry }: Props) {
  const [copied, setCopied] = useState(false);

  if (message.role === 'user') {
    return (
      <div className="animate-fade-up flex justify-end">
        <p className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md brand-gradient px-4 py-2.5 text-sm text-white">
          {message.content}
        </p>
      </div>
    );
  }

  if (message.status === 'error') {
    return (
      <div role="alert" className="animate-fade-up flex gap-3">
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-red-500/15 text-red-500">
          <AlertTriangle size={16} aria-hidden />
        </span>
        <div className="min-w-0 rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm">
          <p className="font-medium text-red-600 dark:text-red-300">Request failed</p>
          <p className="mt-1 text-muted">{message.error}</p>
          {canRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="mt-3 inline-flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-medium hover:bg-surface-2"
            >
              <RotateCw size={12} aria-hidden /> Retry
            </button>
          )}
        </div>
      </div>
    );
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <div className="animate-fade-up group flex gap-3">
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg brand-gradient text-white">
        <Bot size={16} aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <div className="text-sm">
          <Markdown>{message.content}</Markdown>
        </div>
        <Grounding citations={message.citations} uncertainty={message.uncertainty} />
        <button
          type="button"
          onClick={copy}
          aria-label="Copy response"
          className="mt-2 inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted transition hover:bg-surface-2 hover:text-fg"
        >
          {copied ? <Check size={12} aria-hidden /> : <Copy size={12} aria-hidden />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
    </div>
  );
}
