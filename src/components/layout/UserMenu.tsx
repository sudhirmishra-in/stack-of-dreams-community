import { LogIn, LogOut } from 'lucide-react';
import { useAuth } from '../../auth/AuthContext';

export function UserMenu() {
  const { enabled, status, user, signIn, signOut } = useAuth();
  if (!enabled || status === 'loading') return null;

  if (!user) {
    return (
      <button
        type="button"
        onClick={() => signIn()}
        className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-sm text-muted hover:bg-surface-2 hover:text-fg"
      >
        <LogIn size={16} aria-hidden /> Sign in
      </button>
    );
  }
  return (
    <div className="flex items-center gap-1">
      <span
        className="hidden max-w-[10rem] truncate text-xs text-muted lg:inline"
        title={user.email}
      >
        {user.name ?? user.email ?? user.id}
      </span>
      <button
        type="button"
        onClick={() => signOut()}
        aria-label="Sign out"
        className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-sm text-muted hover:bg-surface-2 hover:text-fg"
      >
        <LogOut size={16} aria-hidden /> <span className="hidden sm:inline">Sign out</span>
      </button>
    </div>
  );
}
