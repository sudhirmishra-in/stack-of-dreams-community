import { Card } from '../../../components/ui/Card';
import { availabilityOf } from '../utils/availability';
import { formatNumber } from '../utils/format';
import type { Resource } from '../types/resource';

export function computeStats(resources: Resource[]) {
  const formula = resources.reduce((n, r) => n + (r.inventory?.baby_formula ?? 0), 0);
  const capacity = resources.reduce((n, r) => n + (r.weeklyCapacity ?? 0), 0);
  const low = resources.filter((r) =>
    ['low', 'out'].includes(availabilityOf(r, 'baby_formula')),
  ).length;
  return { orgs: resources.length, formula, capacity, low };
}

export function DashboardStats({ resources }: { resources: Resource[] }) {
  const s = computeStats(resources);
  const items = [
    { label: 'Participating Food Banks', value: formatNumber(s.orgs) },
    { label: 'Available Baby Formula Units', value: formatNumber(s.formula) },
    { label: 'Weekly Distribution Capacity', value: formatNumber(s.capacity, 'households') },
    { label: 'Organizations With Low Inventory', value: formatNumber(s.low) },
  ];
  return (
    <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((i) => (
        <Card key={i.label}>
          <dt className="text-xs uppercase tracking-wider text-muted">{i.label}</dt>
          <dd className="mt-2 text-2xl font-semibold">{i.value}</dd>
        </Card>
      ))}
    </dl>
  );
}
