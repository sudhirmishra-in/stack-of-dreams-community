import { describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { useChat } from '../hooks/useChat';
import type { ChatService } from '../services/errors';

function fakeService(
  impl?: ChatService['sendMessage'],
): ChatService & { sendMessage: ReturnType<typeof vi.fn> } {
  return {
    isMock: true,
    sendMessage: vi.fn(
      impl ??
        (async (r) => ({
          response: `echo: ${r.message}`,
          sessionId: r.sessionId,
          agentId: r.agentId,
        })),
    ),
  };
}

describe('useChat', () => {
  it('reuses the session id for follow-up messages', async () => {
    const service = fakeService();
    const { result } = renderHook(() => useChat('assistant', service));
    await act(() => result.current.sendMessage('one'));
    await act(() => result.current.sendMessage('two'));
    const ids = service.sendMessage.mock.calls.map((c) => c[0].sessionId);
    expect(ids[0]).toBe(ids[1]);
    expect(ids[0]).toBe(result.current.sessionId);
    expect(result.current.messages).toHaveLength(4);
  });

  it('starts a new conversation with a new session id and no messages', async () => {
    const service = fakeService();
    const { result } = renderHook(() => useChat('assistant', service));
    await act(() => result.current.sendMessage('hello'));
    const before = result.current.sessionId;
    act(() => result.current.startNewConversation());
    expect(result.current.sessionId).not.toBe(before);
    expect(result.current.messages).toEqual([]);
  });

  it('clearConversation removes stored history', async () => {
    const service = fakeService();
    const { result } = renderHook(() => useChat('assistant', service));
    await act(() => result.current.sendMessage('hello'));
    act(() => result.current.clearConversation());
    expect(result.current.messages).toEqual([]);
    const stored = JSON.parse(localStorage.getItem('sal.conversation.assistant') ?? '{}');
    expect(stored.messages).toEqual([]);
  });

  it('stores failures as error messages and retries without duplicating the user message', async () => {
    let calls = 0;
    const service = fakeService(async (r) => {
      if (calls++ === 0) throw new Error('boom');
      return { response: 'recovered', sessionId: r.sessionId, agentId: r.agentId };
    });
    const { result } = renderHook(() => useChat('assistant', service));
    await act(() => result.current.sendMessage('hello'));
    expect(result.current.messages.at(-1)).toMatchObject({ status: 'error', error: 'boom' });

    await act(() => result.current.retry());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    const msgs = result.current.messages;
    expect(msgs.map((m) => m.role)).toEqual(['user', 'assistant']);
    expect(msgs[1].content).toBe('recovered');
  });

  it('ignores blank messages', async () => {
    const service = fakeService();
    const { result } = renderHook(() => useChat('assistant', service));
    await act(() => result.current.sendMessage('   '));
    expect(service.sendMessage).not.toHaveBeenCalled();
  });
});
