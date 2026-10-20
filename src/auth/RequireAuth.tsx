import type { ReactNode } from 'react';
import { useLocation } from 'react-router';
import { Lock } from 'lucide-react';
import { useAuth } from './AuthContext';
import { Button } from '../components/ui/Button';
import { useBranding } from '../config/branding';

/** Renders children when auth is disabled or the user is signed in; otherwise a sign-in prompt. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { enabled, status, error, signIn } = useAuth();
  const { pathname, search } = useLocation();
  const { name } = useBranding();

  if (!enabled || status === 'authenticated') return <>{children}</>;

  if (status === 'loading') {
    return (
      <p role="status" className="p-8 text-center text-muted">
        Checking your session…
      </p>
    );
  }

  return (
    <div className="mx-auto max-w-md px-4 py-24 text-center">
      <span className="brand-gradient mx-auto grid h-14 w-14 place-items-center rounded-2xl text-white">
        <Lock size={22} aria-hidden />
      </span>
      <h1 className="mt-5 text-2xl font-semibold tracking-tight">Sign in to continue</h1>
      <p className="mt-2 text-sm text-muted">
        {name} requires you to sign in before chatting with an agent.
      </p>
      <p className="mt-2 text-xs text-muted">
        Access is by invitation only. If you were invited, sign in with your invited account; if
        not, contact the project owner to request access.
      </p>
      {error && (
        <p role="alert" className="mt-4 text-sm text-red-600 dark:text-red-300">
          {error}
        </p>
      )}
      <Button className="mt-6" onClick={() => signIn(pathname + search)}>
        Sign in
      </Button>
    </div>
  );
}
