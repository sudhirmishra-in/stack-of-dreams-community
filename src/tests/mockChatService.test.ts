import { describe, expect, it } from 'vitest';
import { MOCK_BANNER, buildMockReply, mockChatService } from '../services/mockChatService';

describe('mockChatService', () => {
  it('is flagged as mock and echoes session and agent ids', async () => {
    expect(mockChatService.isMock).toBe(true);
    const res = await mockChatService.sendMessage({
      message: 'Hello',
      sessionId: 's-1',
      agentId: 'assistant',
    });
    expect(res.sessionId).toBe('s-1');
    expect(res.agentId).toBe('assistant');
    expect(res.response).toContain('Mock response');
  });

  it('always labels replies as mock, whatever the topic', () => {
    for (const q of [
      'hi',
      'agentcore',
      'strands',
      'code example',
      'agentic',
      'architecture',
      'zzz',
    ]) {
      expect(buildMockReply(q).startsWith(MOCK_BANNER)).toBe(true);
    }
  });

  it('fails on demand with /fail', async () => {
    await expect(
      mockChatService.sendMessage({ message: '/fail', sessionId: 's', agentId: 'assistant' }),
    ).rejects.toThrow(/Simulated/);
  });

  it('rejects when aborted', async () => {
    const ctrl = new AbortController();
    const p = mockChatService.sendMessage(
      { message: 'hi', sessionId: 's', agentId: 'a' },
      ctrl.signal,
    );
    ctrl.abort();
    await expect(p).rejects.toThrow();
  });
});
