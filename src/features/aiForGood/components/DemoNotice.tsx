import { Info } from 'lucide-react';

export function DemoBadge() {
  return (
    <span className="rounded-full border border-amber-500/50 bg-amber-500/10 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-300">
      Demo data
    </span>
  );
}

export function DemoNotice({
  children,
  className = '',
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <p
      role="note"
      className={`flex items-start gap-2 rounded-xl border border-line bg-surface-2 px-3 py-2 text-xs text-muted ${className}`}
    >
      <Info size={14} className="mt-0.5 shrink-0" aria-hidden />
      <span>{children}</span>
    </p>
  );
}

export const DEMO_APP_NOTICE =
  'This is a demonstration application. Resource availability must be verified with participating organizations.';
