import { createOidcAuthService } from '../auth/oidcAuthService';
import { mockAuthService } from '../auth/mockAuthService';
import { noAuthService } from '../auth/noAuthService';
import type { AuthMode, AuthService } from '../types/auth';

export function authMode(): AuthMode {
  const v = String(import.meta.env.VITE_AUTH_MODE ?? 'none').toLowerCase();
  return v === 'mock' || v === 'oidc' ? v : 'none';
}

export function createAuthService(): AuthService {
  const mode = authMode();
  if (mode === 'oidc') return createOidcAuthService();
  if (mode === 'mock') return mockAuthService;
  return noAuthService;
}

export const authService: AuthService = createAuthService();
