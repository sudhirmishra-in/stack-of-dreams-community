import { GraduationCap, HeartPulse, CloudLightning } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { ProjectList } from '../components/ai-for-good/ProjectList';
import { ArchitectureFlow, PROPOSED_NODES } from '../components/ui/ArchitectureFlow';
import { CHALLENGES } from '../data/projects';

const ICONS: Record<string, typeof GraduationCap> = {
  education: GraduationCap,
  healthcare: HeartPulse,
  climate: CloudLightning,
};

export default function ProgramOverviewPage() {
  return (
    <>
      <section className="bg-grid">
        <div className="mx-auto max-w-4xl px-4 py-16 text-center sm:py-24">
          <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
            <span className="text-gradient">AI for Good</span>
          </h1>
          <p className="mt-4 text-xl sm:text-2xl">
            Building intelligent solutions for real-world challenges.
          </p>
          <p className="mx-auto mt-5 max-w-2xl text-muted">
            Explore how Agentic AI can support education, healthcare access, and climate resilience.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12" aria-labelledby="challenges">
        <h2 id="challenges" className="text-2xl font-semibold tracking-tight">
          Challenge areas
        </h2>
        <p className="mt-1 mb-6 text-sm text-muted">
          Potential application areas for exploration. These are not completed projects.
        </p>
        <ul className="grid gap-4 md:grid-cols-3">
          {CHALLENGES.map((c) => {
            const Icon = ICONS[c.id] ?? GraduationCap;
            return (
              <li key={c.id}>
                <Card className="h-full">
                  <Icon size={22} className="text-accent" aria-hidden />
                  <h3 className="mt-3 font-semibold">{c.title}</h3>
                  <ul className="mt-2 space-y-1 text-sm text-muted">
                    {c.areas.map((a) => (
                      <li key={a}>• {a}</li>
                    ))}
                  </ul>
                </Card>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-10" aria-labelledby="projects">
        <h2 id="projects" className="mb-6 text-2xl font-semibold tracking-tight">
          Hackathon Projects
        </h2>
        <ProjectList />
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12" aria-labelledby="proposed">
        <p className="inline-block rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-amber-700 dark:text-amber-300">
          Proposed architecture
        </p>
        <h2 id="proposed" className="mt-3 text-2xl font-semibold tracking-tight">
          Reusable foundation for hackathon applications
        </h2>
        <p className="mt-2 mb-8 max-w-2xl text-sm text-muted">
          A future project could reuse this stack with its own branding and agent. Nothing here is
          deployed.
        </p>
        <ArchitectureFlow nodes={PROPOSED_NODES} />
      </section>
    </>
  );
}
