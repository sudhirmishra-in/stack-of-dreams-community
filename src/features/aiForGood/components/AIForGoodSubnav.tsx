import { NavLink } from 'react-router';

const ITEMS = [
  { to: '/ai-for-good', label: 'Overview', end: true },
  { to: '/ai-for-good/find', label: 'Find help', end: false },
  { to: '/ai-for-good/assistant', label: 'AI assistant', end: false },
  { to: '/ai-for-good/dashboard', label: 'Coordinator dashboard', end: false },
  { to: '/ai-for-good/volunteer', label: 'Volunteer', end: false },
];

export function AIForGoodSubnav() {
  return (
    <nav aria-label="Community Resource Navigator" className="border-b border-line bg-bg">
      <ul className="mx-auto flex max-w-6xl gap-1 overflow-x-auto px-4 py-2">
        {ITEMS.map((i) => (
          <li key={i.to} className="shrink-0">
            <NavLink
              to={i.to}
              end={i.end}
              className={({ isActive }) =>
                `inline-block rounded-lg px-3 py-2 text-sm transition ${isActive ? 'bg-surface-2 font-medium text-fg' : 'text-muted hover:bg-surface-2 hover:text-fg'}`
              }
            >
              {i.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
