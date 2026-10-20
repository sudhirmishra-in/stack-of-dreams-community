import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { httpChatService } from '../services/httpChatService';
import { ChatServiceError } from '../services/errors';

const req = { message: 'Hello', sessionId: 'sid', agentId: 'assistant' };
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

describe('httpChatService', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.test/');
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it('POSTs the request JSON to {base}/chat', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(json({ response: 'Hi!', sessionId: 'sid', agentId: 'assistant' }));
    vi.stubGlobal('fetch', fetchMock);
    const res = await httpChatService.sendMessage(req);
    expect(res.response).toBe('Hi!');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('https://api.test/chat');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual(req);
  });

  it('throws a ChatServiceError with status on HTTP errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({}, 500)));
    await expect(httpChatService.sendMessage(req)).rejects.toMatchObject({
      name: 'ChatServiceError',
      status: 500,
    });
  });

  it('throws a friendly error on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    await expect(httpChatService.sendMessage(req)).rejects.toThrow(/Could not reach/);
  });

  it('rejects malformed response bodies', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ nope: true })));
    await expect(httpChatService.sendMessage(req)).rejects.toBeInstanceOf(ChatServiceError);
  });

  it('fails clearly when the base URL is not configured', async () => {
    vi.stubEnv('VITE_API_BASE_URL', '');
    await expect(httpChatService.sendMessage(req)).rejects.toThrow(/not configured/);
  });
});
