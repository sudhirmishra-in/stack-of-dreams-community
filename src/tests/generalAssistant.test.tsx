import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';

const auth = vi.hoisted(() => ({ token: 'tok-123' as string | null }));
vi.mock('../services/authService', () => ({
  authService: { getAccessToken: async () => auth.token, mode: 'oidc' },
  authMode: () => 'oidc',
}));

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const usageBody = (over: Record<string, unknown> = {}) => ({
  daily: { limit: 20, used: 3, remaining: 17, resetsAt: '2026-10-22T00:00:00Z' },
  monthly: { limit: 200, used: 3, remaining: 197, resetsAt: '2026-11-01T00:00:00Z' },
  tokensToday: { limit: 30000, used: 500, remaining: 29500, resetsAt: '2026-10-22T00:00:00Z' },
  maxQueryChars: 500,
  accountStatus: 'approved',
  ...over,
});

beforeEach(() => {
  auth.token = 'tok-123';
  vi.stubEnv('VITE_PILOT_API_BASE_URL', 'https://pilot.test');
  vi.stubEnv('VITE_USE_MOCK_API', 'false');
  vi.stubEnv('VITE_API_BASE_URL', 'https://oldchat.test');
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});

const req = { message: 'What is agentic AI?', sessionId: 'session-abcdef-1', agentId: 'assistant' };

describe('research assistant service (general chat behind the pilot API)', () => {
  it('POSTs agent "research" to the pilot assistant endpoint with history and the bearer token', async () => {
    const fetchMock = vi.fn(async () =>
      json({ response: 'Agentic AI is…', sessionId: 's', agentId: 'research' }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const { researchAssistantService } = await import('../services/pilotAssistantService');
    const res = await researchAssistantService.sendMessage({
      ...req,
      history: [{ role: 'user', content: 'hi' }],
    });
    expect(res.response).toBe('Agentic AI is…');
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('https://pilot.test/api/v1/assistant');
    const body = JSON.parse(String(init.body));
    expect(body).toMatchObject({
      agent: 'research',
      message: req.message,
      history: [{ role: 'user', content: 'hi' }],
    });
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok-123');
    expect(researchAssistantService.supportsHistory).toBe(true);
  });

  it('the navigator service still sends agent "navigator"', async () => {
    const fetchMock = vi.fn(async () =>
      json({ response: 'ok', sessionId: 's', agentId: 'community-navigator' }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const { pilotAssistantService } = await import('../services/pilotAssistantService');
    await pilotAssistantService.sendMessage(req);
    const body = JSON.parse(
      String((fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1].body),
    );
    expect(body.agent).toBe('navigator');
  });

  it("reads this assistant's own usage (?agent=research) and publishes it on its own event", async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.includes('/me/usage')
        ? json(usageBody())
        : json({
            response: 'x',
            sessionId: 's',
            agentId: 'research',
            remaining: usageBody({ daily: { limit: 20, used: 4, remaining: 16, resetsAt: 'x' } }),
          }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const mod = await import('../services/pilotAssistantService');
    await mod.getPilotUsage(undefined, 'research');
    expect(String(fetchMock.mock.calls[0][0])).toBe(
      'https://pilot.test/api/v1/me/usage?agent=research',
    );
    await mod.getPilotUsage();
    expect(String(fetchMock.mock.calls[1][0])).toBe('https://pilot.test/api/v1/me/usage');
    const seen: string[] = [];
    window.addEventListener(mod.researchUsageEvent, (e) =>
      seen.push('research:' + (e as CustomEvent).detail.daily.remaining),
    );
    window.addEventListener(mod.PILOT_USAGE_EVENT, () => seen.push('navigator'));
    await mod.researchAssistantService.sendMessage(req);
    expect(seen).toEqual(['research:16']);
  });

  it.each([
    [401, { error: { code: 'unauthorized' } }, /sign in again/i],
    [
      403,
      { error: { code: 'pending_approval', message: 'Your account is waiting for approval.' } },
      /waiting for approval/,
    ],
    [
      429,
      {
        error: {
          message: 'Daily request limit reached.',
          details: { reason: 'daily_requests', resetsAt: '2026-10-22T00:00:00Z' },
        },
      },
      /Daily request limit reached/,
    ],
    [503, { error: { message: 'The assistant is temporarily paused.' } }, /paused/],
  ])('shows a clear message for HTTP %i', async (status, body, text) => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => json(body, status as number)),
    );
    const { researchAssistantService } = await import('../services/pilotAssistantService');
    await expect(researchAssistantService.sendMessage(req)).rejects.toThrow(text);
  });
});

describe('the general AI Assistant page uses the quota-enforcing API', () => {
  async function renderAssistant(path = '/chat/assistant') {
    const { AppRoutes } = await import('../app/router');
    return render(
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>,
    );
  }

  it('sends the question to the pilot API (agent research), never to the old unmetered chat endpoint', async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.includes('/me/usage')
        ? json(usageBody())
        : json({
            response: 'Agentic AI means…',
            sessionId: 's',
            agentId: 'research',
            remaining: usageBody(),
          }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();
    await renderAssistant();
    await user.click(await screen.findByRole('button', { name: 'What is agentic AI?' }));
    expect(await screen.findByText('Agentic AI means…')).toBeInTheDocument();
    const urls = fetchMock.mock.calls.map((c) => String(c[0]));
    expect(urls.some((u) => u.startsWith('https://oldchat.test'))).toBe(false);
    const post = fetchMock.mock.calls.find((c) =>
      String(c[0]).endsWith('/api/v1/assistant'),
    ) as unknown as [string, RequestInit];
    expect(JSON.parse(String(post[1].body)).agent).toBe('research');
  });

  it('shows the user their remaining allowance for this assistant', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => json(usageBody())),
    );
    await renderAssistant();
    expect(await screen.findByText(/17 of 20 questions left today/)).toBeInTheDocument();
  });

  it('tells a pending Google user their account is waiting for approval', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => json(usageBody({ accountStatus: 'pending' }))),
    );
    await renderAssistant();
    await waitFor(() => expect(screen.getByText(/waiting for approval/)).toBeInTheDocument());
  });

  it('falls back to the existing chat service only when the pilot API is not configured', async () => {
    vi.stubEnv('VITE_PILOT_API_BASE_URL', '');
    const fetchMock = vi.fn(async () =>
      json({ response: 'old path', sessionId: 's', agentId: 'assistant' }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();
    await renderAssistant();
    await user.click(await screen.findByRole('button', { name: 'What is agentic AI?' }));
    expect(await screen.findByText('old path')).toBeInTheDocument();
    expect(String((fetchMock.mock.calls[0] as unknown as [string])[0])).toContain('oldchat.test');
  });

  it('/chat/ai-for-good still redirects to the navigator page, not the general chat', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => json(usageBody())),
    );
    await renderAssistant('/chat/ai-for-good');
    expect(
      await screen.findByRole('button', { name: /Find food pantries near ZIP 10027/ }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'What is agentic AI?' })).toBeNull();
  });
});
