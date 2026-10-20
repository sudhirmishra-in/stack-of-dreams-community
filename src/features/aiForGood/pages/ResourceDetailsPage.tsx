import { Link, useNavigate, useParams } from 'react-router';
import { MessageCircle } from 'lucide-react';
import { Button } from '../../../components/ui/Button';
import { AIForGoodSubnav } from '../components/AIForGoodSubnav';
import { DEMO_APP_NOTICE, DemoNotice } from '../components/DemoNotice';
import { ResourceDetails } from '../components/ResourceDetails';
import { RouteEstimate } from '../components/RouteEstimate';
import { useResource } from '../hooks/useResourceSearch';
import { buildResourcePrompt } from '../utils/prompts';

export default function ResourceDetailsPage() {
  const { resourceId = '' } = useParams();
  const navigate = useNavigate();
  const { status, data, error, retry } = useResource(resourceId);

  return (
    <>
      <AIForGoodSubnav />
      <div className="mx-auto max-w-3xl px-4 py-10">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="text-sm text-muted hover:text-fg"
        >
          ← Back to results
        </button>
        <div className="mt-4">
          {status === 'loading' && (
            <div
              role="status"
              aria-label="Loading resource"
              className="h-64 animate-pulse rounded-2xl border border-line bg-surface-2"
            />
          )}
          {status === 'error' && (
            <div
              role="alert"
              className="rounded-2xl border border-red-500/40 bg-red-500/10 p-6 text-center"
            >
              <h1 className="font-semibold">We couldn't load this resource</h1>
              <p className="mt-1 text-sm text-muted">{error}</p>
              <Button className="mt-4" onClick={retry}>
                Try again
              </Button>
            </div>
          )}
          {status === 'success' && !data && (
            <div className="py-16 text-center">
              <h1 className="text-2xl font-semibold">Resource not found</h1>
              <Link
                to="/ai-for-good/find"
                className="mt-4 inline-block text-accent hover:underline"
              >
                Start a new search
              </Link>
            </div>
          )}
          {status === 'success' && data && (
            <div className="space-y-6">
              <ResourceDetails resource={data} />
              <RouteEstimate resource={data} />
              <div className="flex flex-col gap-2">
                <Button
                  className="self-start"
                  onClick={() =>
                    navigate('/ai-for-good/assistant', {
                      state: { initialPrompt: buildResourcePrompt(data) },
                    })
                  }
                >
                  <MessageCircle size={16} aria-hidden /> Ask AI About This Resource
                </Button>
                <p className="text-xs text-muted">
                  The assistant is told to use only the details shown on this page.
                </p>
              </div>
              <DemoNotice>
                Contact the organization to confirm availability before traveling.
              </DemoNotice>
              {data.isDemoData && <DemoNotice>{DEMO_APP_NOTICE}</DemoNotice>}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
