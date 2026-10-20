import { Link, useParams } from 'react-router';
import { Hammer } from 'lucide-react';
import { AppShell } from '../app/AppShell';
import { BrandingProvider, DEFAULT_BRANDING, mergeBranding } from '../config/branding';
import { getProject } from '../data/projects';
import { useMemo } from 'react';

/**
 * Reserved route for a future nonprofit-specific application. It renders inside its own shell,
 * using the project's branding overrides (if any) on top of the defaults.
 */
export default function ProjectAppPage() {
  const { projectId } = useParams();
  const project = getProject(projectId);
  const branding = useMemo(
    () => mergeBranding(DEFAULT_BRANDING, project?.branding),
    [project?.branding],
  );

  return (
    <BrandingProvider branding={branding}>
      <AppShell>
        <div className="mx-auto max-w-xl px-4 py-24 text-center">
          <span className="brand-gradient mx-auto grid h-14 w-14 place-items-center rounded-2xl text-white">
            <Hammer size={24} aria-hidden />
          </span>
          {project ? (
            <>
              <p className="mt-5 text-sm text-accent-2">{project.name}</p>
              <h1 className="mt-1 text-2xl font-semibold tracking-tight">
                Application development begins when the hackathon challenge is defined.
              </h1>
              <p className="mt-3 text-sm text-muted">
                This route is reserved for the project's AI application. No functionality is
                implemented yet.
              </p>
              <Link
                to={`/ai-for-good/projects/${project.id}`}
                className="mt-6 inline-block text-accent hover:underline"
              >
                ← Back to project details
              </Link>
            </>
          ) : (
            <>
              <h1 className="mt-5 text-2xl font-semibold">Project not found</h1>
              <Link to="/ai-for-good" className="mt-6 inline-block text-accent hover:underline">
                Back to AI for Good
              </Link>
            </>
          )}
        </div>
      </AppShell>
    </BrandingProvider>
  );
}
