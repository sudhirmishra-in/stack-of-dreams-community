import type { ChatRequest, ChatResponse } from '../types/chat';

export interface ChatService {
  /** True when responses are simulated locally and no backend is called. */
  readonly isMock: boolean;
  /** True if the service accepts recent conversation turns as context. */
  readonly supportsHistory?: boolean;
  sendMessage(request: ChatRequest, signal?: AbortSignal): Promise<ChatResponse>;
}

export class ChatServiceError extends Error {
  readonly status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = 'ChatServiceError';
    this.status = status;
  }
}
