import { Link } from 'react-router';
import { Card } from '../ui/Card';
import { ProjectStatusBadge } from './ProjectStatusBadge';
import type { HackathonProject } from '../../types/project';

export function ProjectCard({ project }: { project: HackathonProject }) {
  return (
    <Card className="flex h-full flex-col gap-3 transition hover:border-accent/40">
      <div className="flex items-start justify-between gap-3">
        <span className="text-xs font-medium uppercase tracking-wider text-accent-2">
          {project.category}
        </span>
        <ProjectStatusBadge status={project.status} />
      </div>
      <div className="flex-1">
        <h3 className="font-semibold">{project.name}</h3>
        <p className="mt-1 text-sm text-muted">{project.description}</p>
      </div>
      <Link
        to={`/ai-for-good/projects/${project.id}`}
        className="text-sm font-medium text-accent hover:underline"
        aria-label={`View details for ${project.name}`}
      >
        View project details →
      </Link>
    </Card>
  );
}
