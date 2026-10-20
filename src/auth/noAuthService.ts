import type { AuthService } from '../types/auth';

/** Used when authentication is disabled: the app is public and sends no token. */
export const noAuthService: AuthService = {
  mode: 'none',
  init: async () => null,
  signIn: async () => {},
  completeSignIn: async () => ({ user: { id: 'anonymous' }, returnTo: '/' }),
  signOut: async () => {},
  getAccessToken: async () => null,
};
