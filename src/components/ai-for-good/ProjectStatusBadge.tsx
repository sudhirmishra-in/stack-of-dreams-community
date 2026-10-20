import { STATUS_LABELS } from '../../data/projects';
import type { ProjectStatus } from '../../types/project';

const styles: Record<ProjectStatus, string> = {
  upcoming: 'border-amber-500/40 text-amber-700 dark:text-amber-300',
  'in-progress': 'border-blue-500/40 text-blue-700 dark:text-blue-300',
  completed: 'border-emerald-500/40 text-emerald-700 dark:text-emerald-300',
  archived: 'border-line text-muted',
};

export function ProjectStatusBadge({ status }: { status: ProjectStatus }) {
  return (
    <span className={`rounded-full border px-2.5 py-0.5 text-xs ${styles[status]}`}>
      {STATUS_LABELS[status]}
    </span>
  );
}
