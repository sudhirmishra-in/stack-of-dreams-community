import type { ReactNode } from 'react';
import { useLocation } from 'react-router';
import { Lock } from 'lucide-react';
import { useAuth } from './AuthContext';
import { Button } from '../components/ui/Button';
import { GoogleIcon } from '../components/ui/GoogleIcon';
import { useBranding } from '../config/branding';

/** Renders children when auth is disabled or the user is signed in; otherwise a sign-in prompt. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { enabled, status, error, providers, signIn } = useAuth();
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
        {providers.includes('google') &&
          ' Signing in with Google confirms who you are but does not grant access by itself: new accounts wait for approval.'}
      </p>
      {error && (
        <p role="alert" className="mt-4 text-sm text-red-600 dark:text-red-300">
          {error}
        </p>
      )}
      <div className="mt-6 flex flex-col items-center gap-3">
        <Button onClick={() => signIn(pathname + search)}>Sign in</Button>
        {providers.includes('google') && (
          <Button variant="secondary" onClick={() => signIn(pathname + search, 'google')}>
            <GoogleIcon />
            Continue with Google
          </Button>
        )}
      </div>
    </div>
  );
}
