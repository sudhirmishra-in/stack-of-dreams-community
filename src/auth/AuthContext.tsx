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
import type { AuthService, AuthUser } from '../types/auth';

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

export interface AuthState {
  /** False when authentication is disabled (mode "none"): the app is public. */
  enabled: boolean;
  status: AuthStatus;
  user: AuthUser | null;
  error: string | null;
  signIn: (returnTo?: string) => Promise<void>;
  signOut: () => Promise<void>;
  /** Called by the callback route after a redirect-based sign-in. */
  completeSignIn: () => Promise<string>;
}

const disabled: AuthState = {
  enabled: false,
  status: 'unauthenticated',
  user: null,
  error: null,
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
    async (returnTo?: string) => {
      setError(null);
      try {
        const u = await service.signIn(returnTo);
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
    () => ({ enabled, status, user, error, signIn, signOut, completeSignIn }),
    [enabled, status, user, error, signIn, signOut, completeSignIn],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
