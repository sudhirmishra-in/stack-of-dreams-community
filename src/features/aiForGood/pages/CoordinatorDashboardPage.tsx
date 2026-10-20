import { AlertTriangle, Lightbulb } from 'lucide-react';
import { Link } from 'react-router';
import { Button, LinkButton } from '../../../components/ui/Button';
import { Card } from '../../../components/ui/Card';
import { AIForGoodSubnav } from '../components/AIForGoodSubnav';
import { DemoBadge, DemoNotice } from '../components/DemoNotice';
import { DashboardStats } from '../components/DashboardStats';
import { InventoryTable } from '../components/InventoryTable';
import { ResultsSkeleton } from '../components/ResultsSkeleton';
import { useAllResources } from '../hooks/useResourceSearch';
import { availabilityOf } from '../utils/availability';
import type { Resource } from '../types/resource';

/** Plain rule-based observations computed from the table data. These are NOT AI output. */
export function buildDemoRecommendations(resources: Resource[]): string[] {
  const units = (r: Resource) => r.inventory?.baby_formula ?? 0;
  const out = resources.filter((r) => units(r) === 0);
  const best = [...resources].sort((a, b) => units(b) - units(a))[0];
  const recs: string[] = [];
  if (best && units(best) > 0 && out.length > 0) {
    recs.push(
      `Review inventory distribution opportunities: ${best.name} lists ${units(best)} formula units while ${out.map((r) => r.name).join(' and ')} list none.`,
    );
  }
  const busiest = [...resources].sort(
    (a, b) => (b.weeklyCapacity ?? 0) - (a.weeklyCapacity ?? 0),
  )[0];
  if (busiest)
    recs.push(
      `Confirm that ${busiest.name} (highest weekly capacity, ${busiest.weeklyCapacity} households) has enough stock.`,
    );
  return recs;
}

export default function CoordinatorDashboardPage() {
  const { status, data, error, retry } = useAllResources();
  const resources = data?.resources ?? [];
  const shortages = resources.filter((r) =>
    ['low', 'out'].includes(availabilityOf(r, 'baby_formula')),
  );

  return (
    <>
      <AIForGoodSubnav />
      <div className="mx-auto max-w-6xl space-y-8 px-4 py-10">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-3xl font-semibold tracking-tight">Coordinator dashboard</h1>
            <DemoBadge />
          </div>
          <p className="mt-2 text-muted">Read-only overview of food bank inventory and capacity.</p>
          <DemoNotice className="mt-3">Demo dashboard using synthetic inventory data.</DemoNotice>
        </div>

        {status === 'loading' && <ResultsSkeleton count={4} />}
        {status === 'error' && (
          <div
            role="alert"
            className="rounded-2xl border border-red-500/40 bg-red-500/10 p-6 text-center"
          >
            <p className="font-semibold">We couldn't load the dashboard</p>
            <p className="mt-1 text-sm text-muted">{error}</p>
            <Button className="mt-4" onClick={retry}>
              Try again
            </Button>
          </div>
        )}

        {status === 'success' && (
          <>
            <DashboardStats resources={resources} />

            <section aria-labelledby="inv">
              <h2 id="inv" className="mb-3 text-xl font-semibold">
                Inventory Comparison
              </h2>
              <InventoryTable resources={resources} />
            </section>

            <div className="grid gap-6 lg:grid-cols-2">
              <section aria-labelledby="short">
                <h2 id="short" className="mb-3 flex items-center gap-2 text-xl font-semibold">
                  <AlertTriangle size={18} className="text-amber-500" aria-hidden /> Resource
                  Shortage Overview
                </h2>
                {shortages.length === 0 ? (
                  <Card className="text-sm text-muted">
                    No organizations are low on baby formula in this data.
                  </Card>
                ) : (
                  <ul className="space-y-2">
                    {shortages.map((r) => (
                      <li key={r.id}>
                        <Card className="!p-4 text-sm">
                          <Link
                            to={`/ai-for-good/resources/${r.id}`}
                            className="font-medium text-accent hover:underline"
                          >
                            {r.name}
                          </Link>
                          <span className="text-muted">
                            {' '}
                            —{' '}
                            {availabilityOf(r, 'baby_formula') === 'out'
                              ? 'no'
                              : 'only ' + r.inventory?.baby_formula}{' '}
                            baby formula units listed
                          </span>
                        </Card>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section aria-labelledby="recs">
                <h2 id="recs" className="mb-3 flex items-center gap-2 text-xl font-semibold">
                  <Lightbulb size={18} className="text-accent" aria-hidden /> Recommendations
                </h2>
                <DemoNotice className="mb-3">
                  Demo examples generated by simple rules from the table above. They are not the
                  output of an AI agent.
                </DemoNotice>
                <ul className="space-y-2">
                  {buildDemoRecommendations(resources).map((t) => (
                    <li key={t}>
                      <Card className="!p-4 text-sm">{t}</Card>
                    </li>
                  ))}
                </ul>
                <LinkButton to="/ai-for-good/assistant" variant="secondary" className="mt-3">
                  Ask the AI assistant
                </LinkButton>
              </section>
            </div>
          </>
        )}
      </div>
    </>
  );
}
