import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { AuthProvider } from '../auth/AuthContext';
import { RequireAuth } from '../auth/RequireAuth';
import AuthCallbackPage, { describeAuthError } from '../pages/AuthCallbackPage';
import { mockAuthService } from '../auth/mockAuthService';
import type { AuthService } from '../types/auth';

const redirects: Array<Record<string, unknown>> = [];
vi.mock('oidc-client-ts', () => ({
  InMemoryWebStorage: class {},
  WebStorageStateStore: class {},
  UserManager: class {
    async signinRedirect(args: Record<string, unknown>) {
      redirects.push(args);
    }
    async getUser() {
      return null;
    }
    async removeUser() {}
  },
}));

const wrap = (service: AuthService, ui: React.ReactNode, path = '/chat') =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider service={service}>{ui}</AuthProvider>
    </MemoryRouter>,
  );

const withGoogle = (signIn = vi.fn(async () => {})): AuthService => ({
  ...mockAuthService,
  init: async () => null,
  providers: ['google'],
  signIn,
});

describe('Continue with Google button', () => {
  it('is shown, alongside the normal sign-in, when Google is enabled', async () => {
    wrap(withGoogle(), <RequireAuth>secret</RequireAuth>);
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Continue with Google' })).toBeInTheDocument();
    expect(screen.getByText(/does not grant access by itself/)).toBeInTheDocument();
  });

  it('is hidden by default so invite-only sign-in is unchanged', async () => {
    wrap({ ...mockAuthService, init: async () => null }, <RequireAuth>secret</RequireAuth>);
    await screen.findByRole('button', { name: 'Sign in' });
    expect(screen.queryByRole('button', { name: 'Continue with Google' })).toBeNull();
  });

  it('starts Google sign-in and remembers where to return to', async () => {
    const signIn = vi.fn(async () => {});
    const user = userEvent.setup();
    wrap(withGoogle(signIn), <RequireAuth>secret</RequireAuth>, '/chat/assistant?x=1');
    await user.click(await screen.findByRole('button', { name: 'Continue with Google' }));
    expect(signIn).toHaveBeenCalledWith('/chat/assistant?x=1', 'google');
  });

  it('keeps the normal sign-in button working (no provider)', async () => {
    const signIn = vi.fn(async () => {});
    const user = userEvent.setup();
    wrap(withGoogle(signIn), <RequireAuth>secret</RequireAuth>);
    await user.click(await screen.findByRole('button', { name: 'Sign in' }));
    expect(signIn).toHaveBeenCalledWith('/chat', undefined);
  });
});

describe('oidc sign-in redirect', () => {
  beforeEach(() => {
    redirects.length = 0;
    vi.stubEnv('VITE_AUTH_AUTHORITY', 'https://cognito-idp.us-east-2.amazonaws.com/pool');
    vi.stubEnv('VITE_AUTH_CLIENT_ID', 'client');
  });
  afterEach(() => vi.unstubAllEnvs());

  async function service(google: boolean) {
    vi.stubEnv('VITE_AUTH_GOOGLE', google ? 'true' : 'false');
    const { createOidcAuthService } = await import('../auth/oidcAuthService');
    return createOidcAuthService();
  }

  it('sends the user straight to Google through Cognito (authorization code + PKCE via the library)', async () => {
    const s = await service(true);
    expect(s.providers).toEqual(['google']);
    await s.signIn('/chat', 'google');
    expect(redirects[0]).toMatchObject({
      state: '/chat',
      extraQueryParams: { identity_provider: 'Google' },
    });
  });

  it('uses the normal Cognito sign-in page when no provider is requested', async () => {
    const s = await service(true);
    await s.signIn('/chat');
    expect(redirects[0].extraQueryParams).toBeUndefined();
  });

  it('ignores a Google request when this build does not advertise Google', async () => {
    const s = await service(false);
    expect(s.providers).toEqual([]);
    await s.signIn('/chat', 'google');
    expect(redirects[0].extraQueryParams).toBeUndefined();
  });

  it('never forwards an open-redirect return path', async () => {
    const s = await service(true);
    await s.signIn('https://evil.test', 'google');
    expect(redirects[0].state).toBe('/');
  });
});

describe('callback errors', () => {
  it.each([
    ['PreSignUp failed with error not_invited.', /hasn't been invited/],
    ['PreSignUp failed with error signup_unavailable.', /temporarily unavailable/],
    ['access_denied', /cancelled or not allowed/],
    ['redirect_mismatch', /not set up for that sign-in method/],
    ['No matching state found in storage', /session expired/],
  ])('explains %s in plain language', (raw, expected) => {
    expect(describeAuthError(new Error(raw))).toMatch(expected);
  });

  it('shows the friendly message on the callback page', async () => {
    const service: AuthService = {
      ...mockAuthService,
      completeSignIn: async () => {
        throw new Error('access_denied');
      },
    };
    wrap(service, <AuthCallbackPage />, '/auth/callback');
    expect(await screen.findByRole('alert')).toHaveTextContent(/cancelled or not allowed/);
  });
});

describe('pending approval', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.resetModules();
    vi.doUnmock('../services/authService');
  });

  it('tells a pending user their account is waiting for approval, instead of showing quota', async () => {
    vi.resetModules();
    vi.doMock('../services/authService', () => ({
      authService: { getAccessToken: async () => 'tok', mode: 'oidc' },
      authMode: () => 'oidc',
    }));
    vi.stubEnv('VITE_PILOT_API_BASE_URL', 'https://pilot.test');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        Response.json({
          daily: { limit: 20, used: 0, remaining: 20, resetsAt: '2026-10-22T00:00:00Z' },
          monthly: { limit: 200, used: 0, remaining: 200, resetsAt: '2026-11-01T00:00:00Z' },
          tokensToday: {
            limit: 30000,
            used: 0,
            remaining: 30000,
            resetsAt: '2026-10-22T00:00:00Z',
          },
          maxQueryChars: 500,
          accountStatus: 'pending',
        }),
      ),
    );
    const { PilotUsageBadge: Badge } =
      await import('../features/aiForGood/components/PilotUsageBadge');
    render(<Badge />);
    expect(await screen.findByRole('status')).toHaveTextContent(/waiting for approval/);
    expect(screen.queryByText(/questions left today/)).toBeNull();
  });

  it('surfaces the server message when the API refuses a pending user (HTTP 403 pending_approval)', async () => {
    vi.resetModules();
    vi.doMock('../services/authService', () => ({
      authService: { getAccessToken: async () => 'tok', mode: 'oidc' },
      authMode: () => 'oidc',
    }));
    vi.stubEnv('VITE_PILOT_API_BASE_URL', 'https://pilot.test');
    const msg = 'Your account is waiting for approval.';
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        Response.json({ error: { code: 'pending_approval', message: msg } }, { status: 403 }),
      ),
    );
    const { pilotAssistantService } = await import('../services/pilotAssistantService');
    await expect(
      pilotAssistantService.sendMessage({ message: 'hi', sessionId: 's', agentId: 'assistant' }),
    ).rejects.toMatchObject({ message: msg });
  });

  it('unauthenticated API access is reported as sign-in required', async () => {
    vi.resetModules();
    vi.doMock('../services/authService', () => ({
      authService: { getAccessToken: async () => null, mode: 'oidc' },
      authMode: () => 'oidc',
    }));
    vi.stubEnv('VITE_PILOT_API_BASE_URL', 'https://pilot.test');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Response.json({ error: { code: 'unauthorized' } }, { status: 401 })),
    );
    const { pilotAssistantService } = await import('../services/pilotAssistantService');
    await expect(
      pilotAssistantService.sendMessage({ message: 'hi', sessionId: 's', agentId: 'assistant' }),
    ).rejects.toMatchObject({ status: 401 });
  });
});
