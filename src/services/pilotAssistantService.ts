import type { ChatRequest, ChatResponse } from '../types/chat';
import { authService } from './authService';
import { ChatServiceError, type ChatService } from './errors';

const TIMEOUT_MS = 60_000;
const KEY_WINDOW_MS = 120_000;

export const PILOT_USAGE_EVENT = 'pilot-usage';

export interface UsageLimit {
  limit: number;
  used: number;
  remaining: number;
  resetsAt: string;
}
export interface PilotUsage {
  daily: UsageLimit;
  monthly: UsageLimit;
  tokensToday: UsageLimit;
  maxQueryChars: number;
  disabled?: boolean;
}

export const pilotBase = () =>
  String(import.meta.env.VITE_PILOT_API_BASE_URL ?? '').replace(/\/+$/, '');
export const isPilotConfigured = () => pilotBase() !== '';

interface ApiErrorBody {
  error?: { code?: string; message?: string; details?: { reason?: string; resetsAt?: string } };
}

// One idempotency key per (session, message) for a short window: a retry after a timeout returns the stored
// answer instead of being charged twice, while a different question always gets a fresh key.
const keys = new Map<string, { key: string; at: number }>();
function idempotencyKey(sessionId: string, message: string): string {
  const id = `${sessionId}\u0000${message}`;
  const now = Date.now();
  const hit = keys.get(id);
  if (hit && now - hit.at < KEY_WINDOW_MS) return hit.key;
  const key = `k-${crypto.randomUUID()}`;
  keys.set(id, { key, at: now });
  for (const [k, v] of keys) if (now - v.at > KEY_WINDOW_MS) keys.delete(k);
  return key;
}

function formatReset(iso?: string): string {
  const d = iso ? new Date(iso) : null;
  return d && !Number.isNaN(d.getTime())
    ? ` It resets ${d.toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })}.`
    : '';
}

function friendly(status: number, body: ApiErrorBody | null): ChatServiceError {
  const e = body?.error;
  switch (status) {
    case 401:
      return new ChatServiceError(
        'Your session has expired or you are not signed in. Please sign in again.',
        401,
      );
    case 403:
      return new ChatServiceError(
        e?.message || 'Your account does not have access to the pilot.',
        403,
      );
    case 409:
      return new ChatServiceError(
        'That request is already being processed. Please wait a moment.',
        409,
      );
    case 429: {
      const reason = e?.details?.reason;
      if (reason === 'concurrent_request')
        return new ChatServiceError('Please wait for your previous question to finish.', 429);
      return new ChatServiceError(
        `${e?.message || 'Usage limit reached.'}${formatReset(e?.details?.resetsAt)}`,
        429,
      );
    }
    case 503:
      return new ChatServiceError(
        e?.message || 'The assistant is temporarily unavailable. Please try again.',
        503,
      );
    case 400:
      return new ChatServiceError(e?.message || 'That message could not be sent.', 400);
    default:
      return new ChatServiceError(`The server responded with an error (HTTP ${status}).`, status);
  }
}

async function call(
  path: string,
  init: RequestInit,
  signal?: AbortSignal,
): Promise<{ status: number; body: unknown }> {
  const root = pilotBase();
  if (!root)
    throw new ChatServiceError('The pilot API is not configured (VITE_PILOT_API_BASE_URL).');
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = await authService.getAccessToken().catch(() => null);
  if (token) headers.Authorization = `Bearer ${token}`;
  const timeout = AbortSignal.timeout(TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`${root}${path}`, {
      ...init,
      headers,
      signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    });
  } catch (err) {
    if (signal?.aborted) throw err;
    throw new ChatServiceError(
      timeout.aborted
        ? 'The request timed out. Please try again.'
        : 'Could not reach the server. Check your connection and retry.',
    );
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* handled below */
  }
  return { status: res.status, body };
}

export async function getPilotUsage(signal?: AbortSignal): Promise<PilotUsage> {
  const { status, body } = await call('/api/v1/me/usage', { method: 'GET' }, signal);
  if (status !== 200) throw friendly(status, body as ApiErrorBody | null);
  return body as PilotUsage;
}

/** The community-navigator assistant (validation gateway -> AgentCore runtime). Not the legacy /chat service. */
export const pilotAssistantService: ChatService = {
  isMock: false,
  supportsHistory: true,

  async sendMessage(request: ChatRequest, signal?: AbortSignal): Promise<ChatResponse> {
    const payload = {
      message: request.message,
      sessionId: request.sessionId,
      agentId: 'community-navigator',
      history: request.history ?? [],
      idempotencyKey: idempotencyKey(request.sessionId, request.message),
    };
    const { status, body } = await call(
      '/api/v1/assistant',
      { method: 'POST', body: JSON.stringify(payload) },
      signal,
    );

    // A polite refusal is a normal answer, not a failure: nothing to retry.
    if (status === 422) {
      const msg =
        (body as ApiErrorBody | null)?.error?.message ??
        'I can only help with community resources.';
      return {
        response: msg,
        sessionId: request.sessionId,
        agentId: request.agentId,
        uncertainty: [],
      };
    }
    if (status !== 200) throw friendly(status, body as ApiErrorBody | null);

    const b = body as Partial<ChatResponse> & { remaining?: PilotUsage };
    if (!b || typeof b.response !== 'string')
      throw new ChatServiceError('The server returned an unexpected response format.');
    if (b.remaining)
      window.dispatchEvent(new CustomEvent(PILOT_USAGE_EVENT, { detail: b.remaining }));
    return {
      response: b.response,
      sessionId: request.sessionId,
      agentId: request.agentId,
      citations: b.citations,
      uncertainty: b.uncertainty,
    };
  },
};
