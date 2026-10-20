export interface ChatRequest {
  message: string;
  sessionId: string;
  agentId: string;
  /** Only sent to services that declare supportsHistory (the pilot assistant). The /chat API never gets it. */
  history?: { role: MessageRole; content: string }[];
}

/** What a pilot answer was based on. Computed server-side from tool results, not claimed by the model. */
export interface Citation {
  sourceId: string;
  resourceId?: string;
  isDemoData: boolean;
  verification: 'verified' | 'unverified';
  freshness: 'fresh' | 'stale' | 'unknown';
}

export interface ChatResponse {
  response: string;
  sessionId: string;
  agentId: string;
  citations?: Citation[];
  uncertainty?: string[];
}

export type MessageRole = 'user' | 'assistant';
export type MessageStatus = 'sent' | 'error';

export interface ChatMessageModel {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: number;
  status: MessageStatus;
  /** Present on error messages so the UI can show the reason. */
  error?: string;
  /** True for responses produced by the local mock service. */
  mock?: boolean;
  citations?: Citation[];
  uncertainty?: string[];
}

export interface Conversation {
  sessionId: string;
  agentId: string;
  messages: ChatMessageModel[];
}

/** Optional customization when the chat experience is embedded in another section of the app. */
export interface ChatContext {
  prompts: string[];
  /** Overrides the chat service (e.g. the pilot assistant). Defaults to the existing /chat service. */
  service?: import('../services/errors').ChatService;
  /** Separate stored history when a different backend shares the same agent id. */
  conversationKey?: string;
  notice?: import('react').ReactNode;
}
