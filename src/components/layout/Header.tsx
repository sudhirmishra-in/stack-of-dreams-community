import { useState } from 'react';
import { Link, NavLink } from 'react-router';
import { Menu, X } from 'lucide-react';
import { Logo } from '../ui/Logo';
import { ThemeToggle } from '../ui/ThemeToggle';
import { LinkButton } from '../ui/Button';
import { UserMenu } from './UserMenu';
import { useBranding } from '../../config/branding';

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-2 text-sm transition ${
    isActive ? 'bg-surface-2 text-fg' : 'text-muted hover:bg-surface-2 hover:text-fg'
  }`;

export function Header() {
  const [open, setOpen] = useState(false);
  const { name, nav, primaryAction } = useBranding();
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <Link to="/" aria-label={`${name} home`} onClick={() => setOpen(false)}>
          <Logo />
        </Link>
        <nav aria-label="Primary" className="hidden items-center gap-1 md:flex">
          {nav.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={linkClass}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="flex items-center gap-1">
          <UserMenu />
          <ThemeToggle />
          {primaryAction && (
            <LinkButton to={primaryAction.to} className="hidden !py-1.5 sm:inline-flex">
              {primaryAction.label}
            </LinkButton>
          )}
          <button
            type="button"
            className="rounded-lg p-2 text-muted hover:bg-surface-2 md:hidden"
            aria-label={open ? 'Close menu' : 'Open menu'}
            aria-expanded={open}
            aria-controls="mobile-nav"
            onClick={() => setOpen((o) => !o)}
          >
            {open ? <X size={20} aria-hidden /> : <Menu size={20} aria-hidden />}
          </button>
        </div>
      </div>
      {open && (
        <nav
          id="mobile-nav"
          aria-label="Mobile"
          className="flex flex-col gap-1 border-t border-line bg-bg px-4 py-3 md:hidden"
        >
          {(primaryAction ? [...nav, { ...primaryAction, end: false }] : nav).map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={linkClass}
              onClick={() => setOpen(false)}
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
      )}
    </header>
  );
}
