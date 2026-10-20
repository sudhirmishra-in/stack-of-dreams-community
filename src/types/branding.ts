import type { LucideIcon } from 'lucide-react';
import type { Agent } from './agent';

export interface NavItem {
  to: string;
  label: string;
  end?: boolean;
}

export interface BrandTheme {
  /** Any valid CSS colors. Applied as CSS variables on the app shell. */
  accent?: string;
  accent2?: string;
  gradientFrom?: string;
  gradientTo?: string;
}

export interface BrandLogo {
  /** Lucide icon component, or an image URL (imageUrl wins when both are set). */
  icon?: LucideIcon;
  imageUrl?: string;
}

/** Everything that distinguishes one application built on this shell from another. */
export interface AppBranding {
  name: string;
  tagline: string;
  logo: BrandLogo;
  theme: BrandTheme;
  nav: NavItem[];
  /** Optional call-to-action button in the header. */
  primaryAction?: { label: string; to: string };
  footer: { prefix: string; linkLabel: string; linkUrl: string; note?: string };
  agents: Agent[];
  defaultAgentId: string;
}
