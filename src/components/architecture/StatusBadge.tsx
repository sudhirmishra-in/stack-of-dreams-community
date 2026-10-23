import type { Status } from './architectureData';

const LABEL: Record<Status, string> = {
  live: 'Live',
  legacy: 'Legacy',
  planned: 'Planned',
  disabled: 'Off',
};

const STYLE: Record<Status, string> = {
  live: 'border-emerald-500/40 text-emerald-700 dark:text-emerald-300',
  legacy: 'border-sky-500/40 text-sky-700 dark:text-sky-300',
  planned: 'border-amber-500/40 text-amber-700 dark:text-amber-300',
  disabled: 'border-line text-muted',
};

export function StatusBadge({ status }: { status: Status }) {
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs ${STYLE[status]}`}>
      {LABEL[status]}
    </span>
  );
}
