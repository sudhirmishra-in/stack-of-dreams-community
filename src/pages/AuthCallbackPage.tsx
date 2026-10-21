import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { useAuth } from '../auth/AuthContext';

/** Turns OAuth error responses into something a person can act on; unknown errors keep their own message. */
export function describeAuthError(e: unknown): string {
  const text = e instanceof Error ? e.message : '';
  if (/access_denied/i.test(text))
    return 'Sign-in was cancelled or not allowed. You can try again.';
  if (/redirect_mismatch|redirect_uri/i.test(text))
    return 'This site is not set up for that sign-in method yet. Please contact the project owner.';
  if (/state|expired|no matching/i.test(text))
    return 'Your sign-in session expired. Please start again.';
  return text || 'Sign-in failed.';
}

export default function AuthCallbackPage() {
  const { completeSignIn } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    completeSignIn()
      .then((to) => active && navigate(to, { replace: true }))
      .catch((e) => active && setError(describeAuthError(e)));
    return () => {
      active = false;
    };
  }, [completeSignIn, navigate]);

  if (error) {
    return (
      <div role="alert" className="mx-auto max-w-md px-4 py-24 text-center">
        <h1 className="text-2xl font-semibold">Sign-in failed</h1>
        <p className="mt-2 text-sm text-muted">{error}</p>
        <Link to="/" className="mt-4 inline-block text-accent hover:underline">
          Back to home
        </Link>
      </div>
    );
  }
  return (
    <p role="status" className="p-8 text-center text-muted">
      Completing sign-in…
    </p>
  );
}
