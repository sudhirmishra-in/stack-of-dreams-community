import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { authService as defaultService } from '../services/authService';
import type { AuthProvider, AuthService, AuthUser } from '../types/auth';
import { clearAllStoredConversations } from '../utils/session';

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

export interface AuthState {
  /** False when authentication is disabled (mode "none"): the app is public. */
  enabled: boolean;
  status: AuthStatus;
  user: AuthUser | null;
  error: string | null;
  /** Extra sign-in buttons to show (e.g. Google). Empty for invite-only sign-in. */
  providers: readonly AuthProvider[];
  signIn: (returnTo?: string, provider?: AuthProvider) => Promise<void>;
  signOut: () => Promise<void>;
  /** Called by the callback route after a redirect-based sign-in. */
  completeSignIn: () => Promise<string>;
}

const disabled: AuthState = {
  enabled: false,
  status: 'unauthenticated',
  user: null,
  error: null,
  providers: [],
  signIn: async () => {},
  signOut: async () => {},
  completeSignIn: async () => '/',
};

const AuthContext = createContext<AuthState>(disabled);

export function AuthProvider({
  children,
  service = defaultService,
}: {
  children: ReactNode;
  service?: AuthService;
}) {
  const enabled = service.mode !== 'none';
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<AuthStatus>(enabled ? 'loading' : 'unauthenticated');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    service
      .init()
      .then((u) => {
        if (cancelled) return;
        setUser(u);
        setStatus(u ? 'authenticated' : 'unauthenticated');
      })
      .catch(() => {
        if (cancelled) return;
        setStatus('unauthenticated');
      });
    return () => {
      cancelled = true;
    };
  }, [enabled, service]);

  const signIn = useCallback(
    async (returnTo?: string, provider?: AuthProvider) => {
      setError(null);
      try {
        const u = await service.signIn(returnTo, provider);
        if (u) {
          setUser(u);
          setStatus('authenticated');
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Sign-in failed.');
      }
    },
    [service],
  );

  const signOut = useCallback(async () => {
    // Before leaving: an identity-provider sign-out redirects the page and never returns here.
    clearAllStoredConversations();
    await service.signOut();
    setUser(null);
    setStatus('unauthenticated');
  }, [service]);

  const completeSignIn = useCallback(async () => {
    const { user: u, returnTo } = await service.completeSignIn();
    setUser(u);
    setStatus('authenticated');
    return returnTo;
  }, [service]);

  const value = useMemo<AuthState>(
    () => ({
      enabled,
      status,
      user,
      error,
      providers: service.providers ?? [],
      signIn,
      signOut,
      completeSignIn,
    }),
    [enabled, status, user, error, service, signIn, signOut, completeSignIn],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
