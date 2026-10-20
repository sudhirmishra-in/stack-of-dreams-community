import { createContext, useContext, useMemo, type CSSProperties, type ReactNode } from 'react';
import { Sparkles } from 'lucide-react';
import { AGENTS, DEFAULT_AGENT_ID } from '../data/agents';
import type { AppBranding } from '../types/branding';

export const DEFAULT_BRANDING: AppBranding = {
  name: 'Stack of Dreams Labs',
  tagline: 'Intelligent Agents. Real-World Impact.',
  logo: { icon: Sparkles },
  theme: {},
  nav: [
    { to: '/', label: 'Home', end: true },
    { to: '/agents', label: 'Agents' },
    { to: '/ai-for-good', label: 'AI for Good' },
    { to: '/architecture', label: 'Architecture' },
    { to: '/about', label: 'About' },
  ],
  primaryAction: { label: 'Launch Assistant', to: '/chat' },
  footer: {
    prefix: 'Built by',
    linkLabel: 'Sudhir Mishra',
    linkUrl: 'https://sudhirmishra.in',
    note: 'Experimental demo — not for sensitive data.',
  },
  agents: AGENTS,
  defaultAgentId: DEFAULT_AGENT_ID,
};

/** Shallow-merges overrides onto a base; `theme` and `logo` are merged one level deeper. */
export function mergeBranding(base: AppBranding, overrides?: Partial<AppBranding>): AppBranding {
  if (!overrides) return base;
  return {
    ...base,
    ...overrides,
    logo: { ...base.logo, ...overrides.logo },
    theme: { ...base.theme, ...overrides.theme },
    footer: { ...base.footer, ...overrides.footer },
  };
}

export function themeStyle(branding: AppBranding): CSSProperties {
  const t = branding.theme;
  const vars: Record<string, string> = {};
  if (t.accent) vars['--accent'] = t.accent;
  if (t.accent2) vars['--accent-2'] = t.accent2;
  if (t.gradientFrom) vars['--brand-from'] = t.gradientFrom;
  if (t.gradientTo) vars['--brand-to'] = t.gradientTo;
  return vars as CSSProperties;
}

const BrandingContext = createContext<AppBranding>(DEFAULT_BRANDING);

export function BrandingProvider({
  branding,
  children,
}: {
  branding: AppBranding;
  children: ReactNode;
}) {
  const style = useMemo(() => themeStyle(branding), [branding]);
  return (
    <BrandingContext.Provider value={branding}>
      <div style={style} className="min-h-full">
        {children}
      </div>
    </BrandingContext.Provider>
  );
}

export const useBranding = () => useContext(BrandingContext);
