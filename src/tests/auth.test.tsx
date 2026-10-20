import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { AuthProvider } from '../auth/AuthContext';
import { RequireAuth } from '../auth/RequireAuth';
import { UserMenu } from '../components/layout/UserMenu';
import AuthCallbackPage from '../pages/AuthCallbackPage';
import { safeReturnTo } from '../auth/returnTo';
import { mockAuthService } from '../auth/mockAuthService';
import { noAuthService } from '../auth/noAuthService';
import type { AuthService } from '../types/auth';

const wrap = (service: AuthService, ui: React.ReactNode, path = '/chat') =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider service={service}>{ui}</AuthProvider>
    </MemoryRouter>,
  );

afterEach(() => sessionStorage.clear());

describe('safeReturnTo', () => {
  it('allows in-app paths only', () => {
    expect(safeReturnTo('/chat?x=1')).toBe('/chat?x=1');
    expect(safeReturnTo('https://evil.test')).toBe('/');
    expect(safeReturnTo('//evil.test')).toBe('/');
    expect(safeReturnTo('/\\evil')).toBe('/');
    expect(safeReturnTo(undefined)).toBe('/');
  });
});

describe('RequireAuth', () => {
  it('renders children when auth is disabled', () => {
    wrap(noAuthService, <RequireAuth>secret</RequireAuth>);
    expect(screen.getByText('secret')).toBeInTheDocument();
  });

  it('prompts for sign-in, then shows content after signing in', async () => {
    const user = userEvent.setup();
    wrap(mockAuthService, <RequireAuth>secret</RequireAuth>);
    expect(await screen.findByRole('heading', { name: 'Sign in to continue' })).toBeInTheDocument();
    expect(screen.getByText(/Access is by invitation only/)).toBeInTheDocument();
    expect(screen.queryByText('secret')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('secret')).toBeInTheDocument();
  });

  it('restores an existing session', async () => {
    await mockAuthService.signIn();
    wrap(mockAuthService, <RequireAuth>secret</RequireAuth>);
    expect(await screen.findByText('secret')).toBeInTheDocument();
  });

  it('shows a sign-in error', async () => {
    const failing: AuthService = {
      ...mockAuthService,
      init: async () => null,
      signIn: async () => {
        throw new Error('IdP unavailable');
      },
    };
    const user = userEvent.setup();
    wrap(failing, <RequireAuth>secret</RequireAuth>);
    await user.click(await screen.findByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('IdP unavailable');
  });
});

describe('UserMenu', () => {
  it('renders nothing when auth is disabled', () => {
    const { container } = wrap(noAuthService, <UserMenu />);
    expect(container).toBeEmptyDOMElement();
  });

  it('toggles between Sign in and Sign out', async () => {
    const user = userEvent.setup();
    wrap(mockAuthService, <UserMenu />);
    await user.click(await screen.findByRole('button', { name: /sign in/i }));
    await user.click(await screen.findByRole('button', { name: 'Sign out' }));
    expect(await screen.findByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });
});

describe('AuthCallbackPage', () => {
  function Where() {
    const l = useLocation();
    return <p>at {l.pathname}</p>;
  }

  it('completes sign-in and navigates to the return path', async () => {
    const service: AuthService = {
      ...mockAuthService,
      completeSignIn: async () => ({ user: { id: 'u' }, returnTo: '/chat/assistant' }),
    };
    render(
      <MemoryRouter initialEntries={['/auth/callback']}>
        <AuthProvider service={service}>
          <Routes>
            <Route path="/auth/callback" element={<AuthCallbackPage />} />
            <Route path="*" element={<Where />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('at /chat/assistant')).toBeInTheDocument());
  });

  it('shows an error when the callback fails', async () => {
    const service: AuthService = {
      ...mockAuthService,
      completeSignIn: async () => {
        throw new Error('bad code');
      },
    };
    wrap(service, <AuthCallbackPage />, '/auth/callback');
    expect(await screen.findByRole('alert')).toHaveTextContent('bad code');
  });
});

describe('httpChatService with auth', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.resetModules();
    vi.doUnmock('../services/authService');
  });

  async function load(token: string | null) {
    vi.resetModules();
    vi.doMock('../services/authService', () => ({
      authService: { getAccessToken: async () => token },
    }));
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.test');
    return (await import('../services/httpChatService')).httpChatService;
  }
  const req = { message: 'hi', sessionId: 's', agentId: 'assistant' };

  it('sends a bearer token when signed in', async () => {
    const svc = await load('tok123');
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ response: 'ok', sessionId: 's', agentId: 'assistant' })),
      );
    vi.stubGlobal('fetch', fetchMock);
    await svc.sendMessage(req);
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe('Bearer tok123');
  });

  it('omits Authorization with no token, and maps 401 to a sign-in message', async () => {
    const svc = await load(null);
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 401 }));
    vi.stubGlobal('fetch', fetchMock);
    await expect(svc.sendMessage(req)).rejects.toThrow(/sign in again/);
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBeUndefined();
  });
});
