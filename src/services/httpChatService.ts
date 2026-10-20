import type { ChatRequest, ChatResponse } from '../types/chat';
import { ChatServiceError, type ChatService } from './errors';
import { authService } from './authService';

const TIMEOUT_MS = 60_000;

function baseUrl(): string {
  return String(import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '');
}

function isChatResponse(data: unknown): data is ChatResponse {
  const d = data as Partial<ChatResponse> | null;
  return !!d && typeof d.response === 'string' && typeof d.sessionId === 'string';
}

export const httpChatService: ChatService = {
  isMock: false,

  async sendMessage(request: ChatRequest, signal?: AbortSignal): Promise<ChatResponse> {
    const base = baseUrl();
    if (!base) {
      throw new ChatServiceError(
        'The API is not configured. Set VITE_API_BASE_URL or enable VITE_USE_MOCK_API.',
      );
    }

    const timeout = AbortSignal.timeout(TIMEOUT_MS);
    const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;

    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    const token = await authService.getAccessToken().catch(() => null);
    if (token) headers.Authorization = `Bearer ${token}`;

    let res: Response;
    try {
      res = await fetch(`${base}/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify(request),
        signal: combined,
      });
    } catch (err) {
      if (signal?.aborted) throw err;
      if (timeout.aborted) throw new ChatServiceError('The request timed out. Please try again.');
      throw new ChatServiceError('Could not reach the server. Check your connection and retry.');
    }

    if (res.status === 401 || res.status === 403) {
      throw new ChatServiceError(
        'Your session has expired or you are not authorized. Please sign in again.',
        res.status,
      );
    }
    if (!res.ok) {
      throw new ChatServiceError(
        `The server responded with an error (HTTP ${res.status}).`,
        res.status,
      );
    }

    let data: unknown;
    try {
      data = await res.json();
    } catch {
      throw new ChatServiceError('The server returned an unreadable response.');
    }
    if (!isChatResponse(data)) {
      throw new ChatServiceError('The server returned an unexpected response format.');
    }
    return {
      response: data.response,
      sessionId: data.sessionId,
      agentId: data.agentId ?? request.agentId,
    };
  },
};
