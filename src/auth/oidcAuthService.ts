import { InMemoryWebStorage, UserManager, WebStorageStateStore, type User } from 'oidc-client-ts';
import type { AuthProvider, AuthService, AuthUser } from '../types/auth';
import { safeReturnTo } from './returnTo';

const env = import.meta.env;

function toAuthUser(u: User): AuthUser {
  return {
    id: u.profile.sub,
    email: typeof u.profile.email === 'string' ? u.profile.email : undefined,
    name: typeof u.profile.name === 'string' ? u.profile.name : undefined,
  };
}

/**
 * Authorization Code + PKCE against Amazon Cognito (or any OIDC provider).
 * Tokens are kept in memory only (never localStorage), so a page reload re-runs sign-in,
 * which is quick while the identity provider's own session cookie is still valid.
 * No client secret is used or needed.
 */
function createOidcAuthService(): AuthService {
  const origin = window.location.origin;
  let manager: UserManager | null = null;
  let callbackPromise: ReturnType<AuthService['completeSignIn']> | null = null;

  const getManager = () => {
    if (!manager) {
      // Accept a pasted discovery URL too; the library appends this path itself.
      const authority = env.VITE_AUTH_AUTHORITY?.replace(
        /\/?\.well-known\/openid-configuration\/?$/,
        '',
      ).replace(/\/+$/, '');
      const clientId = env.VITE_AUTH_CLIENT_ID;
      if (!authority || !clientId) {
        throw new Error(
          'Authentication is not configured (VITE_AUTH_AUTHORITY / VITE_AUTH_CLIENT_ID).',
        );
      }
      manager = new UserManager({
        authority,
        client_id: clientId,
        redirect_uri: env.VITE_AUTH_REDIRECT_URI || `${origin}/auth/callback`,
        post_logout_redirect_uri: origin,
        response_type: 'code',
        scope: env.VITE_AUTH_SCOPE || 'openid email profile',
        userStore: new WebStorageStateStore({ store: new InMemoryWebStorage() }),
        automaticSilentRenew: false,
      });
    }
    return manager;
  };

  const providers: readonly AuthProvider[] = env.VITE_AUTH_GOOGLE === 'true' ? ['google'] : [];

  return {
    mode: 'oidc',
    providers,
    async init() {
      const u = await getManager().getUser();
      return u && !u.expired ? toAuthUser(u) : null;
    },
    async signIn(returnTo = '/', provider) {
      // Cognito skips its own sign-in page and goes straight to Google when told which provider to use.
      // Only providers this build advertises are honoured; anything else falls back to the normal sign-in page.
      const extraQueryParams =
        provider === 'google' && providers.includes('google')
          ? { identity_provider: 'Google' }
          : undefined;
      await getManager().signinRedirect({ state: safeReturnTo(returnTo), extraQueryParams });
    },
    completeSignIn() {
      // The auth code is single-use; share one in-flight call (React StrictMode runs effects twice).
      callbackPromise ??= getManager()
        .signinCallback()
        .then((u) => {
          if (!u) throw new Error('Sign-in did not return a user.');
          return { user: toAuthUser(u), returnTo: safeReturnTo(u.state) };
        });
      return callbackPromise;
    },
    async signOut() {
      const m = getManager();
      await m.removeUser();
      // Cognito does not expose an OIDC end_session endpoint; use its hosted /logout.
      const domain = env.VITE_AUTH_LOGOUT_DOMAIN;
      if (domain) {
        const url = new URL('/logout', domain);
        url.searchParams.set('client_id', env.VITE_AUTH_CLIENT_ID ?? '');
        url.searchParams.set('logout_uri', origin);
        window.location.assign(url.toString());
      }
    },
    async getAccessToken() {
      const m = getManager();
      let u = await m.getUser();
      if (u?.expired) {
        try {
          u = await m.signinSilent(); // uses the refresh token when one was issued
        } catch {
          u = null;
        }
      }
      return u && !u.expired ? u.access_token : null;
    },
  };
}

export { createOidcAuthService };
