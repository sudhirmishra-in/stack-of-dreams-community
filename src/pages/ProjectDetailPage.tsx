import { Link, useParams } from 'react-router';
import { ExternalLink, GitBranch } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { ExternalLinkButton, LinkButton } from '../components/ui/Button';
import { ArchitectureFlow, PROPOSED_NODES } from '../components/ui/ArchitectureFlow';
import { ProjectStatusBadge } from '../components/ai-for-good/ProjectStatusBadge';
import { getProject } from '../data/projects';
import { safeHttpUrl } from '../utils/url';
import type { ReactNode } from 'react';

const TBD = 'To be defined.';

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="mb-2 text-lg font-semibold">{title}</h2>
      {children}
    </section>
  );
}

export default function ProjectDetailPage() {
  const { projectId } = useParams();
  const project = getProject(projectId);

  if (!project) {
    return (
      <div className="mx-auto max-w-xl px-4 py-24 text-center">
        <h1 className="text-2xl font-semibold">Project not found</h1>
        <Link to="/ai-for-good" className="mt-4 inline-block text-accent hover:underline">
          Back to AI for Good
        </Link>
      </div>
    );
  }

  const d = project.details ?? {};
  const demo = safeHttpUrl(project.demoUrl);
  const repo = safeHttpUrl(project.repoUrl);
  const customArch = !!d.architecture?.length;

  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <Link to="/ai-for-good" className="text-sm text-muted hover:text-fg">
        ← AI for Good
      </Link>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-semibold tracking-tight">{project.name}</h1>
        <ProjectStatusBadge status={project.status} />
      </div>
      <p className="mt-1 text-sm text-accent-2">{project.category}</p>

      <Section title="Project overview">
        <p className="text-muted">{d.overview ?? project.description}</p>
      </Section>
      <Section title="Problem statement">
        <p className="text-muted">
          {d.problemStatement ?? `${TBD} The challenge will be defined when the hackathon begins.`}
        </p>
      </Section>
      <Section title="Proposed solution">
        <p className="text-muted">{d.proposedSolution ?? TBD}</p>
      </Section>

      <Section title="Technology stack">
        {d.techStack && d.techStack.length > 0 ? (
          <ul className="flex flex-wrap gap-2">
            {d.techStack.map((t) => (
              <li key={t} className="rounded-full border border-line bg-surface px-3 py-1 text-sm">
                {t}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-muted">{TBD}</p>
        )}
      </Section>

      <Section title="Architecture">
        <p className="mb-4 text-sm text-amber-700 dark:text-amber-300">
          {customArch ? 'Project architecture' : 'Proposed architecture (not deployed)'}
        </p>
        <ArchitectureFlow
          nodes={d.architecture?.length ? d.architecture : PROPOSED_NODES}
          compact
        />
      </Section>

      <Section title="Team">
        {d.team && d.team.length > 0 ? (
          <ul className="grid gap-2 sm:grid-cols-2">
            {d.team.map((m) => (
              <li key={m.name}>
                <Card className="!p-3 text-sm">
                  <span className="font-medium">{m.name}</span>
                  {m.role && <span className="text-muted"> — {m.role}</span>}
                </Card>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-muted">Team information to be announced.</p>
        )}
      </Section>

      <Section title="Links">
        <div className="flex flex-wrap gap-3">
          {demo ? (
            <ExternalLinkButton href={demo}>
              <ExternalLink size={16} aria-hidden /> Demo
            </ExternalLinkButton>
          ) : (
            <span className="rounded-xl border border-dashed border-line px-4 py-2.5 text-sm text-muted">
              Demo: not available yet
            </span>
          )}
          {repo ? (
            <ExternalLinkButton href={repo}>
              <GitBranch size={16} aria-hidden /> GitHub
            </ExternalLinkButton>
          ) : (
            <span className="rounded-xl border border-dashed border-line px-4 py-2.5 text-sm text-muted">
              GitHub: not available yet
            </span>
          )}
          <LinkButton to={`/ai-for-good/projects/${project.id}/app`} variant="ghost">
            Application workspace
          </LinkButton>
        </div>
        <p className="mt-3 text-sm text-muted">Agent: {project.agentId ?? 'not assigned yet'}</p>
      </Section>
    </div>
  );
}
