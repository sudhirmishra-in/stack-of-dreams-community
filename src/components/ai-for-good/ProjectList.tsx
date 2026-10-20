import { ProjectCard } from './ProjectCard';
import { PROJECTS } from '../../data/projects';
import type { HackathonProject } from '../../types/project';

export function ProjectList({ projects = PROJECTS }: { projects?: HackathonProject[] }) {
  if (projects.length === 0) {
    return <p className="text-sm text-muted">No projects have been registered yet.</p>;
  }
  return (
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-label="Hackathon projects">
      {projects.map((p) => (
        <li key={p.id}>
          <ProjectCard project={p} />
        </li>
      ))}
    </ul>
  );
}
