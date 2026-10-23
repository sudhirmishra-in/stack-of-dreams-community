import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';
import { AuthProvider, useAuth } from '../auth/AuthContext';
import { mockAuthService } from '../auth/mockAuthService';
import type { AuthService } from '../types/auth';
import type { Conversation } from '../types/chat';
import {
  clearAllStoredConversations,
  loadConversation,
  newConversation,
  saveConversation,
} from '../utils/session';
import PrivacyPage from '../pages/PrivacyPage';

const sendMessage = vi.fn();
vi.mock('../services/chatService', () => ({
  chatService: { isMock: true, sendMessage: (...a: unknown[]) => sendMessage(...a) },
}));

import ChatPage from '../pages/ChatPage';

const renderChat = () =>
  render(
    <MemoryRouter initialEntries={['/chat/assistant']}>
      <Routes>
        <Route path="/chat/:agentId?" element={<ChatPage />} />
      </Routes>
    </MemoryRouter>,
  );

beforeEach(() => {
  localStorage.clear();
  sendMessage.mockReset();
  sendMessage.mockImplementation(async (r) => ({
    response: 'saved reply',
    sessionId: r.sessionId,
    agentId: r.agentId,
  }));
});
afterEach(() => localStorage.clear());

describe('the chat is kept in this browser until the user starts a new chat', () => {
  it('restores the whole conversation after the page is closed and reopened', async () => {
    const user = userEvent.setup();
    const first = renderChat();
    await user.type(screen.getByLabelText('Message'), 'remember me{Enter}');
    expect(await screen.findByText('saved reply')).toBeInTheDocument();
    first.unmount(); // closing the tab / reloading

    renderChat();
    expect(await screen.findByText('remember me')).toBeInTheDocument();
    expect(screen.getByText('saved reply')).toBeInTheDocument();
    expect(screen.queryByText('How can I help today?')).toBeNull();
  });

  it('keeps the same session id, so the assistant continues the same conversation', async () => {
    const user = userEvent.setup();
    const first = renderChat();
    await user.type(screen.getByLabelText('Message'), 'one{Enter}');
    await screen.findByText('saved reply');
    const sid = sendMessage.mock.calls[0][0].sessionId;
    first.unmount();

    renderChat();
    await user.type(await screen.findByLabelText('Message'), 'two{Enter}');
    await waitFor(() => expect(sendMessage).toHaveBeenCalledTimes(2));
    expect(sendMessage.mock.calls[1][0].sessionId).toBe(sid);
  });

  it('"New chat" discards the saved conversation, and the next visit starts empty', async () => {
    const user = userEvent.setup();
    const first = renderChat();
    await user.type(screen.getByLabelText('Message'), 'forget me{Enter}');
    await screen.findByText('saved reply');
    await user.click(screen.getByRole('button', { name: 'New chat' }));
    expect(screen.getByText('How can I help today?')).toBeInTheDocument();
    first.unmount();

    renderChat();
    expect(await screen.findByText('How can I help today?')).toBeInTheDocument();
    expect(screen.queryByText('forget me')).toBeNull();
  });

  it('tells the user it is saved and what New chat does', () => {
    renderChat();
    expect(screen.getByText(/saved in this browser/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'New chat' })).toHaveAttribute(
      'title',
      expect.stringMatching(/replace|discard|start/i),
    );
  });

  it("keeps each assistant's conversation separate", () => {
    saveConversation({
      ...newConversation('ai-for-good'),
      messages: [
        { id: '1', role: 'user', content: 'navigator chat', createdAt: 1, status: 'sent' },
      ],
    });
    expect(loadConversation('assistant').messages).toEqual([]);
    expect(loadConversation('ai-for-good').messages).toHaveLength(1);
  });
});

describe('storage hygiene', () => {
  const msg = (i: number) => ({
    id: String(i),
    role: 'user' as const,
    content: `m${i}`,
    createdAt: i,
    status: 'sent' as const,
  });

  it('stores only the newest messages so the browser quota is never exhausted', () => {
    const c: Conversation = {
      ...newConversation('assistant'),
      messages: Array.from({ length: 450 }, (_, i) => msg(i)),
    };
    saveConversation(c);
    const restored = loadConversation('assistant');
    expect(restored.sessionId).toBe(c.sessionId);
    expect(restored.messages.length).toBeLessThanOrEqual(200);
    expect(restored.messages.at(-1)?.content).toBe('m449'); // newest kept
    expect(restored.messages[0].content).not.toBe('m0'); // oldest dropped
  });

  it('also bounds the size in bytes (very long answers)', () => {
    const huge = (i: number) => ({ ...msg(i), content: 'x'.repeat(60_000) });
    saveConversation({
      ...newConversation('assistant'),
      messages: Array.from({ length: 30 }, (_, i) => huge(i)),
    });
    const raw = localStorage.getItem('sal.conversation.assistant') ?? '';
    expect(raw.length).toBeLessThanOrEqual(400_000);
    expect(loadConversation('assistant').messages.at(-1)?.id).toBe('29');
  });

  it('survives storage being unavailable', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota');
    });
    expect(() => saveConversation(newConversation('assistant'))).not.toThrow();
    spy.mockRestore();
  });

  it('clearAllStoredConversations removes every saved chat but nothing else', () => {
    saveConversation(newConversation('assistant'));
    saveConversation(newConversation('ai-for-good'));
    localStorage.setItem('sal.theme', 'dark');
    clearAllStoredConversations();
    expect(Object.keys(localStorage).filter((k) => k.startsWith('sal.conversation.'))).toEqual([]);
    expect(localStorage.getItem('sal.theme')).toBe('dark');
  });
});

describe('sign-out protects the next person on a shared computer', () => {
  function Probe() {
    const { signOut } = useAuth();
    return <button onClick={() => void signOut()}>sign out now</button>;
  }

  it('removes saved chats BEFORE leaving (a redirecting sign-out never returns)', async () => {
    saveConversation(newConversation('assistant'));
    const redirecting: AuthService = {
      ...mockAuthService,
      signOut: () => new Promise<void>(() => {}),
    };
    const user = userEvent.setup();
    render(
      <AuthProvider service={redirecting}>
        <Probe />
      </AuthProvider>,
    );
    await user.click(screen.getByRole('button', { name: 'sign out now' }));
    expect(Object.keys(localStorage).filter((k) => k.startsWith('sal.conversation.'))).toEqual([]);
  });
});

describe('privacy page discloses where chats live', () => {
  it('says chats are saved in the browser, until a new chat or sign-out, and mentions the 2-day answer copy', () => {
    render(
      <MemoryRouter>
        <PrivacyPage />
      </MemoryRouter>,
    );
    const text = document.body.textContent ?? '';
    expect(text).toMatch(/saved in your browser/i);
    expect(text).toMatch(/new chat or sign out/i);
    expect(text).toMatch(/about 2 days/i);
  });
});
