import type { AuthService, AuthUser } from '../types/auth';
import { safeReturnTo } from './returnTo';

const KEY = 'sal.mockAuthUser';

export const MOCK_USER: AuthUser = {
  id: 'mock-user',
  name: 'Demo User',
  email: 'demo@example.test',
};

function read(): AuthUser | null {
  try {
    return sessionStorage.getItem(KEY) ? MOCK_USER : null;
  } catch {
    return null;
  }
}

/** Local, fake sign-in for development. It provides NO real security and issues no real token. */
export const mockAuthService: AuthService = {
  mode: 'mock',
  async init() {
    return read();
  },
  async signIn() {
    try {
      sessionStorage.setItem(KEY, '1');
    } catch {
      /* ignore */
    }
    return MOCK_USER;
  },
  async completeSignIn() {
    return { user: MOCK_USER, returnTo: safeReturnTo('/') };
  },
  async signOut() {
    try {
      sessionStorage.removeItem(KEY);
    } catch {
      /* ignore */
    }
  },
  async getAccessToken() {
    return read() ? 'mock-token' : null;
  },
};
