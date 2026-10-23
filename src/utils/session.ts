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

// Browser storage is small (about 5 MB for the whole site), so a long chat keeps only its newest part.
const MAX_STORED_MESSAGES = 200;
const MAX_STORED_BYTES = 400_000;

/** The newest messages that fit the limits (the full conversation stays in memory while the tab is open). */
function trimForStorage(conversation: Conversation): Conversation {
  let messages = conversation.messages.slice(-MAX_STORED_MESSAGES);
  let json = JSON.stringify({ ...conversation, messages });
  while (json.length > MAX_STORED_BYTES && messages.length > 1) {
    messages = messages.slice(Math.max(1, Math.ceil(messages.length / 10)));
    json = JSON.stringify({ ...conversation, messages });
  }
  return { ...conversation, messages };
}

export function saveConversation(conversation: Conversation): void {
  try {
    const trimmed = trimForStorage(conversation);
    localStorage.setItem(STORAGE_PREFIX + conversation.agentId, JSON.stringify(trimmed));
  } catch {
    /* storage full or disabled: history just won't persist */
  }
}

/** Removes every saved chat from this browser (used on sign-out so the next person on this computer cannot read them). */
export function clearAllStoredConversations(): void {
  try {
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith(STORAGE_PREFIX)) localStorage.removeItem(key);
    }
  } catch {
    /* ignore */
  }
}

export function clearStoredConversation(agentId: string): void {
  try {
    localStorage.removeItem(STORAGE_PREFIX + agentId);
  } catch {
    /* ignore */
  }
}
