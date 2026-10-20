import { describe, expect, it } from 'vitest';
import {
  clearStoredConversation,
  createSessionId,
  loadConversation,
  newConversation,
  saveConversation,
} from '../utils/session';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

describe('session utils', () => {
  it('creates unique UUID v4 session ids', () => {
    const a = createSessionId();
    const b = createSessionId();
    expect(a).toMatch(UUID);
    expect(a).not.toBe(b);
  });

  it('creates an empty conversation with a new session id', () => {
    const c = newConversation('assistant');
    expect(c.messages).toEqual([]);
    expect(c.agentId).toBe('assistant');
    expect(c.sessionId).toMatch(UUID);
  });

  it('persists and restores a conversation, and clears it', () => {
    const c = newConversation('assistant');
    saveConversation(c);
    expect(loadConversation('assistant').sessionId).toBe(c.sessionId);
    clearStoredConversation('assistant');
    expect(loadConversation('assistant').sessionId).not.toBe(c.sessionId);
  });

  it('falls back to a fresh conversation when stored data is corrupt', () => {
    localStorage.setItem('sal.conversation.assistant', '{not json');
    expect(loadConversation('assistant').messages).toEqual([]);
  });
});
