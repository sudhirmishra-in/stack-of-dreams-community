import type { Conversation } from '../types/chat';

const STORAGE_PREFIX = 'sal.conversation.';

/** Generates a UUID, using crypto.randomUUID when available. */
export function createSessionId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  // Fallback for non-secure contexts (e.g. http on a LAN address).
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export function newConversation(agentId: string): Conversation {
  return { sessionId: createSessionId(), agentId, messages: [] };
}

export function loadConversation(agentId: string): Conversation {
  try {
    const raw = localStorage.getItem(STORAGE_PREFIX + agentId);
    if (raw) {
      const parsed = JSON.parse(raw) as Conversation;
      if (
        typeof parsed?.sessionId === 'string' &&
        parsed.agentId === agentId &&
        Array.isArray(parsed.messages)
      ) {
        return parsed;
      }
    }
  } catch {
    /* corrupted or unavailable storage: start fresh */
  }
  return newConversation(agentId);
}

export function saveConversation(conversation: Conversation): void {
  try {
    localStorage.setItem(STORAGE_PREFIX + conversation.agentId, JSON.stringify(conversation));
  } catch {
    /* storage full or disabled: history just won't persist */
  }
}

export function clearStoredConversation(agentId: string): void {
  try {
    localStorage.removeItem(STORAGE_PREFIX + agentId);
  } catch {
    /* ignore */
  }
}
