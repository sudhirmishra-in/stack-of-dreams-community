import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, renderHook, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';

const auth = vi.hoisted(() => ({ token: 'tok-123' as string | null }));
vi.mock('../services/authService', () => ({
  authService: { getAccessToken: async () => auth.token, mode: 'oidc' },
  authMode: () => 'oidc',
}));

const svc = vi.hoisted(() => ({
  current: null as unknown,
}));
vi.mock('../services/resourceService', () => ({
  get resourceService() {
    return svc.current;
  },
}));
vi.mock('../features/aiForGood/components/ResourceMap', () => ({
  default: (p: {
    resources: { id: string; name: string; latitude?: number }[];
    selectedId: string | null;
    onSelect: (id: string) => void;
  }) => (
    <div role="region" aria-label="Map of matching providers">
      {p.resources
        .filter((r) => r.latitude !== undefined)
        .map((r) => (
          <button
            key={r.id}
            data-testid={`marker-${r.id}`}
            data-selected={p.selectedId === r.id}
            onClick={() => p.onSelect(r.id)}
          >
            marker {r.name}
          </button>
        ))}
    </div>
  ),
}));

import {
  PILOT_USAGE_EVENT,
  getPilotUsage,
  pilotAssistantService,
} from '../services/pilotAssistantService';
import { httpResourceService } from '../services/httpResourceService';
import { ChatMessage } from '../components/chat/ChatMessage';
import { PilotUsageBadge } from '../features/aiForGood/components/PilotUsageBadge';
import { buildAiForGoodChat } from '../features/aiForGood/config';
import {
  authorizeMapRequest,
  hasValidCoordinates,
  isMapConfigured,
  mappable,
  proxyStyleUrl,
} from '../features/aiForGood/utils/geo';
import { useChat } from '../hooks/useChat';
import { chatService } from '../services/chatService';
import type { ChatService } from '../services/errors';
import type { Resource, ResourceService } from '../features/aiForGood/types/resource';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const req = {
  message: 'Which food banks near 10027?',
  sessionId: 'session-abcdef-1',
  agentId: 'assistant',
};

beforeEach(() => {
  auth.token = 'tok-123';
  vi.stubEnv('VITE_PILOT_API_BASE_URL', 'https://pilot.test/');
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe('geo helpers', () => {
  it('accepts real coordinates only', () => {
    expect(hasValidCoordinates({ latitude: 40.8, longitude: -73.9 })).toBe(true);
    for (const bad of [
      {},
      { latitude: 0, longitude: 0 },
      { latitude: 91, longitude: 0 },
      { latitude: 40, longitude: -181 },
      { latitude: NaN, longitude: 1 },
    ]) {
      expect(hasValidCoordinates(bad as never)).toBe(false);
    }
    expect(
      mappable([{ id: 'a', latitude: 40, longitude: -73 }, { id: 'b' }] as Resource[]).map(
        (r) => r.id,
      ),
    ).toEqual(['a']);
  });

  it('serves the map through the pilot API, not a browser-side AWS key', () => {
    expect(proxyStyleUrl('Dark')).toBe('https://pilot.test/api/v1/maps/style?scheme=Dark');
    expect(proxyStyleUrl('Light')).not.toContain('amazonaws.com');
  });

  it('only sends the access token to our own map proxy', () => {
    const own = 'https://pilot.test/api/v1/maps/tiles/vector.basemap/10/301/385';
    expect(authorizeMapRequest(own, 'tok')).toEqual({
      url: own,
      headers: { Authorization: 'Bearer tok' },
    });
    expect(
      authorizeMapRequest('https://pilot.test/api/v1/resources/search', 'tok'),
    ).toBeUndefined();
    expect(authorizeMapRequest('https://evil.example/api/v1/maps/x', 'tok')).toBeUndefined();
    expect(authorizeMapRequest(own, null)).toBeUndefined();
  });

  it('is available only with the real API (pilot URL set and mock resources off)', () => {
    expect(isMapConfigured()).toBe(false); // mock resources is the default
    vi.stubEnv('VITE_USE_MOCK_RESOURCES', 'false');
    expect(isMapConfigured()).toBe(true);
    vi.stubEnv('VITE_PILOT_API_BASE_URL', '');
    expect(isMapConfigured()).toBe(false);
  });
});

describe('pilot assistant service', () => {
  it('POSTs to /api/v1/assistant with the bearer token, history and an idempotency key', async () => {
    const f = vi.fn().mockResolvedValue(
      json({
        response: 'ok',
        citations: [
          { sourceId: 'osm', isDemoData: false, verification: 'unverified', freshness: 'fresh' },
        ],
        uncertainty: ['x'],
      }),
    );
    vi.stubGlobal('fetch', f);
    const res = await pilotAssistantService.sendMessage({
      ...req,
      history: [{ role: 'user', content: 'hi' }],
    });
    const [url, init] = f.mock.calls[0];
    expect(url).toBe('https://pilot.test/api/v1/assistant');
    expect(init.headers.Authorization).toBe('Bearer tok-123');
    const body = JSON.parse(init.body);
    expect(body).toMatchObject({
      message: req.message,
      sessionId: req.sessionId,
      agentId: 'community-navigator',
      history: [{ role: 'user', content: 'hi' }],
    });
    expect(body.idempotencyKey).toMatch(/^k-/);
    expect(res.citations?.[0].sourceId).toBe('osm');
    expect(res.uncertainty).toEqual(['x']);
  });

  it('reuses the key for an identical retry and uses a new one for a different question', async () => {
    const f = vi.fn().mockImplementation(async () => json({ response: 'ok' }));
    vi.stubGlobal('fetch', f);
    await pilotAssistantService.sendMessage(req);
    await pilotAssistantService.sendMessage(req);
    await pilotAssistantService.sendMessage({ ...req, message: 'something else about food' });
    const keys = f.mock.calls.map((c) => JSON.parse(c[1].body).idempotencyKey);
    expect(keys[0]).toBe(keys[1]);
    expect(keys[2]).not.toBe(keys[0]);
  });

  it('treats the 422 refusal as a normal answer, not an error to retry', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        json(
          {
            error: { code: 'out_of_scope', message: 'I can only help with community resources.' },
          },
          422,
        ),
      ),
    );
    const res = await pilotAssistantService.sendMessage(req);
    expect(res.response).toBe('I can only help with community resources.');
  });

  it.each([
    [401, {}, /sign in again/],
    [403, { error: { message: 'Pilot access is disabled for this account.' } }, /disabled/],
    [
      429,
      {
        error: {
          message: 'Daily request limit reached.',
          details: { reason: 'daily_requests', resetsAt: '2030-01-02T00:00:00Z' },
        },
      },
      /Daily request limit reached\..*resets/,
    ],
    [429, { error: { details: { reason: 'concurrent_request' } } }, /previous question/],
    [503, { error: { message: 'The assistant is temporarily paused.' } }, /paused/],
    [500, {}, /HTTP 500/],
  ])('maps HTTP %i to a friendly error', async (status, body, pattern) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(body, status as number)));
    await expect(
      pilotAssistantService.sendMessage({
        ...req,
        message: `q${status}${JSON.stringify(body).length}`,
      }),
    ).rejects.toThrow(pattern as RegExp);
  });

  it('publishes remaining quota for the badge and handles network failure', async () => {
    const remaining = {
      daily: { limit: 20, used: 1, remaining: 19, resetsAt: 'x' },
      monthly: { limit: 200, used: 1, remaining: 199, resetsAt: 'x' },
    };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ response: 'ok', remaining })));
    const got = vi.fn();
    window.addEventListener(PILOT_USAGE_EVENT, got);
    await pilotAssistantService.sendMessage({ ...req, message: 'usage event question' });
    window.removeEventListener(PILOT_USAGE_EVENT, got);
    expect(got).toHaveBeenCalled();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('x')));
    await expect(pilotAssistantService.sendMessage({ ...req, message: 'net' })).rejects.toThrow(
      /Could not reach/,
    );
  });

  it('is clear when the pilot API is not configured', async () => {
    vi.stubEnv('VITE_PILOT_API_BASE_URL', '');
    await expect(pilotAssistantService.sendMessage(req)).rejects.toThrow(/not configured/);
  });
});

describe('answer grounding display', () => {
  it('shows sources and caveats only when the answer carries them', () => {
    const base = {
      id: '1',
      role: 'assistant' as const,
      content: 'Answer',
      createdAt: 0,
      status: 'sent' as const,
    };
    const { rerender } = render(<ChatMessage message={base} />);
    expect(screen.queryByTestId('grounding')).toBeNull(); // legacy /chat answers look exactly as before
    rerender(
      <ChatMessage
        message={{
          ...base,
          citations: [
            { sourceId: 'osm', isDemoData: false, verification: 'unverified', freshness: 'fresh' },
            {
              sourceId: 'demo',
              isDemoData: true,
              verification: 'unverified',
              freshness: 'unknown',
            },
            {
              sourceId: 'demo',
              isDemoData: true,
              verification: 'unverified',
              freshness: 'unknown',
            },
          ],
          uncertainty: [
            'Some results are DEMO DATA (fictional sample records), not real inventory.',
          ],
        }}
      />,
    );
    const g = screen.getByTestId('grounding');
    expect(g).toHaveTextContent(
      '1 directory record (community-sourced, unverified) and 2 demo records (fictional sample data)',
    );
    expect(g).toHaveTextContent('DEMO DATA');
  });
});

describe('usage badge', () => {
  it('shows server-reported remaining quota and updates after each answer', async () => {
    const usage = {
      daily: { limit: 20, used: 5, remaining: 15, resetsAt: 'x' },
      monthly: { limit: 200, used: 5, remaining: 195, resetsAt: 'x' },
      tokensToday: { limit: 30000, used: 1, remaining: 1, resetsAt: 'x' },
      maxQueryChars: 500,
    };
    const f = vi.fn().mockImplementation(async () => json(usage));
    vi.stubGlobal('fetch', f);
    render(<PilotUsageBadge />);
    expect(await screen.findByRole('status')).toHaveTextContent(
      '15 of 20 questions left today · 195 this month',
    );
    expect(f.mock.calls[0][0]).toBe('https://pilot.test/api/v1/me/usage');
    act(() =>
      window.dispatchEvent(
        new CustomEvent(PILOT_USAGE_EVENT, {
          detail: { ...usage, daily: { ...usage.daily, remaining: 2 } },
        }),
      ),
    );
    expect(screen.getByRole('status')).toHaveTextContent('2 of 20');
    expect((await getPilotUsage()).maxQueryChars).toBe(500);
  });

  it('renders nothing when the usage call fails (informational only)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({}, 401)));
    const { container } = render(<PilotUsageBadge />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});

describe('assistant backend selection is explicit, never silent', () => {
  it('uses the pilot service and its own stored conversation when configured', () => {
    const c = buildAiForGoodChat();
    expect(c.service).toBe(pilotAssistantService);
    expect(c.conversationKey).toBe('ai-for-good');
  });

  it('falls back to the existing chat service AND says so when the pilot API is not configured', () => {
    vi.stubEnv('VITE_PILOT_API_BASE_URL', '');
    const c = buildAiForGoodChat();
    expect(c.service).toBe(chatService);
    expect(c.conversationKey).toBe('assistant');
    render(<MemoryRouter>{c.notice}</MemoryRouter>);
    expect(screen.getByRole('note')).toHaveTextContent(
      'Community Navigator service is not connected',
    );
  });
});

describe('useChat with the pilot assistant', () => {
  const make = (extra: Partial<ChatService> = {}) => {
    const sendMessage = vi.fn(async (r) => ({
      response: 'ok',
      sessionId: r.sessionId,
      agentId: r.agentId,
      citations: [
        {
          sourceId: 'osm',
          isDemoData: false,
          verification: 'unverified' as const,
          freshness: 'fresh' as const,
        },
      ],
      uncertainty: ['u'],
    }));
    return { sendMessage, isMock: false, ...extra } as ChatService & {
      sendMessage: ReturnType<typeof vi.fn>;
    };
  };

  it('sends only the recent turns before the new message, and only to services that accept history', async () => {
    const withHistory = make({ supportsHistory: true });
    const { result } = renderHook(() => useChat('assistant', withHistory, 'ai-for-good'));
    for (const m of ['one', 'two', 'three', 'four', 'five'])
      await act(() => result.current.sendMessage(m));
    const last = withHistory.sendMessage.mock.calls.at(-1)![0];
    expect(last.history).toHaveLength(4);
    expect(last.history.at(-1)).toEqual({ role: 'assistant', content: 'ok' });
    expect(withHistory.sendMessage.mock.calls[0][0].history).toEqual([]);

    const legacy = make();
    const h2 = renderHook(() => useChat('assistant', legacy));
    await act(() => h2.result.current.sendMessage('hello'));
    await act(() => h2.result.current.sendMessage('again'));
    expect('history' in legacy.sendMessage.mock.calls[1][0]).toBe(false); // /chat contract untouched
  });

  it('keeps pilot and general conversations in separate storage and carries citations through', async () => {
    const pilot = make({ supportsHistory: true });
    const a = renderHook(() => useChat('assistant', pilot, 'ai-for-good'));
    await act(() => a.result.current.sendMessage('pilot question'));
    expect(a.result.current.messages.at(-1)).toMatchObject({
      citations: [{ sourceId: 'osm' }],
      uncertainty: ['u'],
    });
    expect(localStorage.getItem('sal.conversation.ai-for-good')).toContain('pilot question');
    expect(localStorage.getItem('sal.conversation.assistant')).toBeNull();
    const b = renderHook(() => useChat('assistant', make()));
    expect(b.result.current.messages).toEqual([]); // the general chat does not see pilot messages
    act(() => a.result.current.clearConversation());
    expect(JSON.parse(localStorage.getItem('sal.conversation.ai-for-good')!).messages).toEqual([]);
  });
});

describe('resource HTTP service against the pilot API', () => {
  it('maps auth, quota and unavailable errors to friendly messages', async () => {
    const q = { zipCode: '10027', resourceType: 'food_assistance' as const };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({}, 401)));
    await expect(httpResourceService.search(q)).rejects.toThrow(/sign in/);
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          json({ error: { message: 'Daily limit reached for this action.' } }, 429),
        ),
    );
    await expect(httpResourceService.search(q)).rejects.toThrow(/Daily limit/);
  });

  it('unwraps single resources, requests routes with query params, and returns null for 404', async () => {
    const f = vi.fn().mockResolvedValueOnce(json({ resource: { id: 'r1', name: 'R' } }));
    vi.stubGlobal('fetch', f);
    expect((await httpResourceService.getResource('r1'))?.name).toBe('R');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({}, 404)));
    expect(await httpResourceService.getResource('nope')).toBeNull();
    const g = vi
      .fn()
      .mockResolvedValue(
        json({ distanceMiles: 2, durationMinutes: 10, provider: 'Amazon Location Service' }),
      );
    vi.stubGlobal('fetch', g);
    const r = await httpResourceService.getRoute!('10027', 'r1', 'Pedestrian');
    expect(r).toMatchObject({ distanceMiles: 2, durationMinutes: 10, travelMode: 'Pedestrian' });
    expect(g.mock.calls[0][0]).toBe(
      'https://pilot.test/api/v1/route?fromZip=10027&toResourceId=r1&mode=Pedestrian',
    );
  });
});

// ---------------- results page with map, details with route ----------------

import ResourceResultsPage from '../features/aiForGood/pages/ResourceResultsPage';
import ResourceDetailsPage from '../features/aiForGood/pages/ResourceDetailsPage';
import { Route, Routes } from 'react-router';

const res = (over: Partial<Resource>): Resource => ({
  id: 'r1',
  name: 'Pantry One',
  city: 'New York',
  zipCode: '10026',
  resourceTypes: ['food_assistance'],
  source: 'OpenStreetMap (community-sourced, unverified)',
  sourceId: 'osm',
  verified: false,
  isDemoData: false,
  attribution: '© OpenStreetMap contributors',
  ...over,
});

function fakeService(over: Partial<ResourceService> = {}): ResourceService {
  return {
    isMock: false,
    search: vi.fn(async () => ({
      resources: [
        res({
          id: 'r1',
          name: 'Pantry One',
          latitude: 40.8,
          longitude: -73.95,
          distanceMiles: 0.4,
        }),
        res({ id: 'r2', name: 'Pantry Two' }),
      ],
      totalResults: 2,
      dataSource: 'Real directory records',
      isDemoData: false,
      origin: { zipCode: '10027', latitude: 40.81, longitude: -73.95, geocoded: true },
      notes: ['Some providers have no map coordinates.'],
      attributions: ['© OpenStreetMap contributors'],
    })),
    getResource: vi.fn(async () => res({ id: 'r1', latitude: 40.8, longitude: -73.95 })),
    listResources: vi.fn(),
    getRoute: vi.fn(async (_zip: string, _id: string, mode: 'Car' | 'Pedestrian') => ({
      distanceMiles: 3,
      durationMinutes: 11.4,
      travelMode: mode,
      provider: 'Amazon Location Service',
    })),
    ...over,
  } as ResourceService;
}

const renderResults = () =>
  render(
    <MemoryRouter initialEntries={['/ai-for-good/results?type=food_assistance&zip=10027']}>
      <Routes>
        <Route path="/ai-for-good/results" element={<ResourceResultsPage />} />
      </Routes>
    </MemoryRouter>,
  );

describe('results page with the real API', () => {
  it('renders the map, syncs card and marker selection, shows notes, distance and attribution', async () => {
    vi.stubEnv('VITE_USE_MOCK_RESOURCES', 'false');
    svc.current = fakeService();
    const user = userEvent.setup();
    renderResults();
    expect(await screen.findByText('Pantry One')).toBeInTheDocument();
    expect(
      await screen.findByRole('region', { name: 'Map of matching providers' }),
    ).toBeInTheDocument();
    expect(screen.getByText('0.4 mi (straight line)')).toBeInTheDocument();
    expect(screen.getByText('Some providers have no map coordinates.')).toBeInTheDocument();
    expect(screen.getByText(/Data: © OpenStreetMap contributors/)).toBeInTheDocument();
    // only providers with real coordinates get markers / a "Show on map" action
    expect(screen.queryByTestId('marker-r2')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Show Pantry Two on the map' })).toBeNull();

    await user.click(screen.getByRole('button', { name: 'Show Pantry One on the map' }));
    expect(screen.getByTestId('marker-r1')).toHaveAttribute('data-selected', 'true');
    await user.click(screen.getByTestId('marker-r1'));
    expect(screen.getByRole('button', { name: 'Show Pantry One on the map' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('offers the demo opt-in and the distance filter, and sends them to the API', async () => {
    vi.stubEnv('VITE_USE_MOCK_RESOURCES', 'false');
    const s = fakeService();
    svc.current = s;
    const user = userEvent.setup();
    renderResults();
    await screen.findByText('Pantry One');
    await user.click(screen.getByLabelText(/Include DEMO data/));
    await user.selectOptions(screen.getByLabelText('Within'), '3');
    await waitFor(() =>
      expect(s.search).toHaveBeenLastCalledWith(
        expect.objectContaining({ includeDemo: true, radiusMiles: 3 }),
        expect.anything(),
      ),
    );
  });

  it('hides the distance filter and map when the ZIP could not be located or no key is configured', async () => {
    svc.current = fakeService({
      search: vi.fn(async () => ({
        resources: [res({ id: 'r2', name: 'Pantry Two' })],
        totalResults: 1,
        dataSource: 'x',
        isDemoData: false,
        origin: { zipCode: '10027', geocoded: false },
      })),
    });
    renderResults();
    expect(await screen.findByText('Pantry Two')).toBeInTheDocument();
    expect(screen.queryByLabelText('Within')).toBeNull();
    expect(screen.queryByRole('region', { name: 'Map of matching providers' })).toBeNull();
  });

  it('no map in mock mode even when coordinates exist (the list still works)', async () => {
    svc.current = fakeService();
    renderResults();
    expect(await screen.findByText('Pantry One')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Map of matching providers' })).toBeNull();
  });
});

describe('details route estimate', () => {
  const renderDetails = () =>
    render(
      <MemoryRouter initialEntries={['/ai-for-good/resources/r1']}>
        <Routes>
          <Route path="/ai-for-good/resources/:resourceId" element={<ResourceDetailsPage />} />
        </Routes>
      </MemoryRouter>,
    );

  it('returns real service values on demand', async () => {
    const s = fakeService();
    svc.current = s;
    const user = userEvent.setup();
    renderDetails();
    await screen.findByRole('heading', { level: 1, name: 'Pantry One' });
    const btn = screen.getByRole('button', { name: /Get travel estimate/ });
    expect(btn).toBeDisabled();
    await user.type(screen.getByLabelText('Starting ZIP code'), '10027');
    await user.selectOptions(screen.getByLabelText('Travel by'), 'Pedestrian');
    await user.click(btn);
    expect(await screen.findByText(/About 3 miles, 11 minutes by foot/)).toBeInTheDocument();
    expect(s.getRoute).toHaveBeenCalledWith('10027', 'r1', 'Pedestrian');
  });

  it('shows the error instead of any estimate when location is unavailable', async () => {
    svc.current = fakeService({
      getRoute: vi.fn(async () => {
        throw new Error('Route information is unavailable right now.');
      }),
    });
    const user = userEvent.setup();
    renderDetails();
    await screen.findByRole('heading', { level: 1, name: 'Pantry One' });
    await user.type(screen.getByLabelText('Starting ZIP code'), '10027');
    await user.click(screen.getByRole('button', { name: /Get travel estimate/ }));
    expect(
      await screen.findByText('Route information is unavailable right now.'),
    ).toBeInTheDocument();
    expect(screen.queryByText(/About \d+ miles/)).toBeNull();
  });

  it('is absent for the mock service or providers without coordinates', async () => {
    svc.current = fakeService({ getRoute: undefined });
    renderDetails();
    await screen.findByRole('heading', { level: 1, name: 'Pantry One' });
    expect(screen.queryByText('Travel estimate')).toBeNull();
    svc.current = fakeService({ getResource: vi.fn(async () => res({ id: 'r1' })) });
    const again = within(renderDetails().container);
    await waitFor(() => expect(again.queryByText('Travel estimate')).toBeNull());
  });
});
