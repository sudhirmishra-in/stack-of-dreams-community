import { Suspense, lazy, useMemo, useState } from 'react';
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router';
import { MessageCircle, SearchX } from 'lucide-react';
import { Button, LinkButton } from '../../../components/ui/Button';
import { getCategory } from '../../../config/resourceCategories';
import { resourceService } from '../../../services/resourceService';
import { AIForGoodSubnav } from '../components/AIForGoodSubnav';
import { DEMO_APP_NOTICE, DemoBadge, DemoNotice } from '../components/DemoNotice';
import { ResourceCard } from '../components/ResourceCard';
import { ResourceFilters } from '../components/ResourceFilters';
import { ResultsSkeleton } from '../components/ResultsSkeleton';
import { useResourceSearch } from '../hooks/useResourceSearch';
import { filterByAvailability, type AvailabilityFilter } from '../utils/availability';
import { isMapConfigured, mappable } from '../utils/geo';
import { buildResourcePrompt, buildResultsPrompt } from '../utils/prompts';
import { parseSearchParams } from '../utils/searchParams';
import type { Resource, ResourceSearchRequest, SortBy } from '../types/resource';

// The map (MapLibre) is large: load it only when there is something to show.
const ResourceMap = lazy(() => import('../components/ResourceMap'));

export default function ResourceResultsPage() {
  const [params] = useSearchParams();
  const request = useMemo(() => parseSearchParams(params), [params]);
  if (!request) return <Navigate to="/ai-for-good/find" replace />;
  return <Results request={request} />;
}

const isDark = () => document.documentElement.classList.contains('dark');

function Results({ request }: { request: ResourceSearchRequest }) {
  const navigate = useNavigate();
  const { state } = useLocation();
  const notes = (state as { notes?: string } | null)?.notes;
  const [availability, setAvailability] = useState<AvailabilityFilter>('all');
  const [sortBy, setSortBy] = useState<SortBy>('nearest');
  const [radius, setRadius] = useState<number | undefined>();
  // Mock data is entirely demo data. Against the real API, demo inventory is an explicit opt-in.
  const [includeDemo, setIncludeDemo] = useState(resourceService.isMock);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mapFailed, setMapFailed] = useState(false);

  const search = useResourceSearch({ ...request, sortBy, radiusMiles: radius, includeDemo });
  const cat = getCategory(request.resourceType);
  const all = useMemo(() => search.data?.resources ?? [], [search.data]);
  const shown = useMemo(
    () => filterByAvailability(all, request.resourceType, availability),
    [all, request.resourceType, availability],
  );
  const origin = search.data?.origin;
  const showMap = isMapConfigured() && !mapFailed && mappable(shown).length > 0;

  const askAI = (prompt: string) =>
    navigate('/ai-for-good/assistant', { state: { initialPrompt: prompt } });

  const select = (id: string) => {
    setSelectedId(id);
    document
      .getElementById(`resource-${id}`)
      ?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };

  const list =
    shown.length === 0 ? (
      <div className="rounded-2xl border border-dashed border-line p-10 text-center">
        <SearchX size={28} className="mx-auto text-muted" aria-hidden />
        <h2 className="mt-3 font-semibold">No matching resources</h2>
        <p className="mx-auto mt-1 max-w-md text-sm text-muted">
          {all.length === 0
            ? 'No matching records were found for this search. Try a different resource type, remove the quantity or distance, or ask the AI assistant for ideas.'
            : 'No resources match this availability filter. Try "All".'}
        </p>
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          <LinkButton to="/ai-for-good/find" variant="secondary">
            New search
          </LinkButton>
          <Button variant="ghost" onClick={() => askAI(buildResultsPrompt([], request, notes))}>
            Ask AI
          </Button>
        </div>
      </div>
    ) : (
      <>
        <ul
          className={`grid gap-4 ${showMap ? 'xl:grid-cols-2' : 'md:grid-cols-2 lg:grid-cols-3'}`}
        >
          {shown.map((r: Resource) => (
            <li key={r.id}>
              <ResourceCard
                resource={r}
                type={request.resourceType}
                onAskAI={(x) => askAI(buildResourcePrompt(x))}
                selected={selectedId === r.id}
                onSelect={showMap ? select : undefined}
              />
            </li>
          ))}
        </ul>
        <div className="mt-8 text-center">
          <Button
            variant="secondary"
            onClick={() => askAI(buildResultsPrompt(shown, request, notes))}
          >
            <MessageCircle size={16} aria-hidden /> Ask AI which to contact first
          </Button>
          <p className="mt-2 text-xs text-muted">
            AI answers are suggestions based on the results above, not verified information.
          </p>
        </div>
      </>
    );

  return (
    <>
      <AIForGoodSubnav />
      <div className="mx-auto max-w-6xl px-4 py-10">
        <Link to="/ai-for-good/find" className="text-sm text-muted hover:text-fg">
          ← Change search
        </Link>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight">
          {cat.label} Near {request.zipCode}
        </h1>

        <ul aria-label="Search criteria" className="mt-3 flex flex-wrap gap-2 text-sm">
          {[
            cat.label,
            `ZIP ${request.zipCode}`,
            request.quantity
              ? `At least ${request.quantity} ${cat.quantityUnit ?? ''}`.trim()
              : null,
            request.formulaType ? `Formula: ${request.formulaType}` : null,
            request.urgency ? `Needed: ${request.urgency.replace('_', ' ')}` : null,
          ]
            .filter(Boolean)
            .map((c) => (
              <li key={c} className="rounded-full border border-line bg-surface px-3 py-1">
                {c}
              </li>
            ))}
        </ul>

        {!resourceService.isMock && (
          <label className="mt-4 flex min-h-11 cursor-pointer items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={includeDemo}
              onChange={(e) => setIncludeDemo(e.target.checked)}
              className="h-4 w-4"
            />
            Include DEMO data with sample inventory (fictional organizations)
          </label>
        )}

        {search.data?.isDemoData && (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <DemoBadge />
            <DemoNotice className="flex-1">
              {DEMO_APP_NOTICE}{' '}
              {origin?.geocoded
                ? 'Distances are straight-line estimates from the ZIP code center.'
                : 'Results are ordered by ZIP-code similarity; no real distances are calculated.'}
            </DemoNotice>
          </div>
        )}

        {search.data?.notes?.map((n) => (
          <DemoNotice key={n} className="mt-3">
            {n}
          </DemoNotice>
        ))}

        <div className="mt-6">
          <ResourceFilters
            availability={availability}
            onAvailability={setAvailability}
            sortBy={sortBy}
            onSortBy={setSortBy}
            showAvailability={request.resourceType !== 'food_assistance'}
            showRadius={!!origin?.geocoded}
            radiusMiles={radius}
            onRadius={setRadius}
          />
        </div>

        <div className="mt-6">
          {search.status === 'loading' && <ResultsSkeleton />}

          {search.status === 'error' && (
            <div
              role="alert"
              className="rounded-2xl border border-red-500/40 bg-red-500/10 p-6 text-center"
            >
              <h2 className="font-semibold">We couldn't load resources</h2>
              <p className="mt-1 text-sm text-muted">{search.error}</p>
              <Button className="mt-4" onClick={search.retry}>
                Try again
              </Button>
            </div>
          )}

          {search.status === 'success' && (
            <>
              <p role="status" className="mb-4 text-sm text-muted">
                {shown.length} matching {shown.length === 1 ? 'resource' : 'resources'}
                {shown.length !== all.length && ` (of ${all.length} found)`}
              </p>
              {showMap ? (
                <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
                  <div>{list}</div>
                  <div className="lg:sticky lg:top-20 lg:self-start">
                    <Suspense
                      fallback={
                        <div className="h-80 animate-pulse rounded-2xl border border-line bg-surface-2" />
                      }
                    >
                      <ResourceMap
                        resources={shown}
                        origin={origin}
                        selectedId={selectedId}
                        onSelect={select}
                        dark={isDark()}
                        onFailure={() => setMapFailed(true)}
                      />
                    </Suspense>
                  </div>
                </div>
              ) : (
                list
              )}
              {!!search.data?.attributions?.length && (
                <p className="mt-6 text-xs text-muted">
                  Data: {search.data.attributions.join(' · ')}
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
