import { useNavigate, useSearchParams } from 'react-router';
import { isResourceType } from '../../../config/resourceCategories';
import { AIForGoodSubnav } from '../components/AIForGoodSubnav';
import { DEMO_APP_NOTICE, DemoNotice } from '../components/DemoNotice';
import { ResourceSearchForm } from '../components/ResourceSearchForm';
import { toSearchParams } from '../utils/searchParams';

export default function FindResourcesPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const type = params.get('type');

  return (
    <>
      <AIForGoodSubnav />
      <div className="mx-auto max-w-2xl px-4 py-10">
        <h1 className="text-3xl font-semibold tracking-tight">Find resources</h1>
        <p className="mt-2 mb-8 text-muted">
          Tell us what you need and where. We only ask for what we need to search — no names, phone
          numbers, or health details.
        </p>
        <ResourceSearchForm
          initial={isResourceType(type) ? { resourceType: type } : undefined}
          onSubmit={(request, notes) =>
            // Notes may be sensitive, so they travel in navigation state, never in the URL.
            navigate(`/ai-for-good/results?${toSearchParams(request)}`, { state: { notes } })
          }
        />
        <DemoNotice className="mt-8">{DEMO_APP_NOTICE}</DemoNotice>
      </div>
    </>
  );
}
