import { Card } from '../../../components/ui/Card';
import { AVAILABILITY_LABELS, availabilityOf } from '../utils/availability';
import {
  directionsHref,
  formatNumber,
  formatUpdated,
  NOT_AVAILABLE,
  telHref,
} from '../utils/format';
import { RESOURCE_CATEGORIES } from '../../../config/resourceCategories';
import { DemoBadge } from './DemoNotice';
import { ExternalLinkButton } from '../../../components/ui/Button';
import type { Resource } from '../types/resource';

const Item = ({ label, children }: { label: string; children: React.ReactNode }) => (
  <div>
    <dt className="text-xs uppercase tracking-wider text-muted">{label}</dt>
    <dd className="mt-0.5 text-sm">{children}</dd>
  </div>
);

export function ResourceDetails({ resource: r }: { resource: Resource }) {
  const tel = telHref(r.phone);
  const maps = directionsHref(r);
  const confirm = 'Contact provider to confirm';
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-semibold tracking-tight">{r.name}</h1>
        {r.isDemoData && <DemoBadge />}
      </div>

      <Card>
        <h2 className="mb-3 font-semibold">Availability</h2>
        <dl className="grid gap-4 sm:grid-cols-2">
          {RESOURCE_CATEGORIES.filter((c) => c.id !== 'food_assistance').map((c) => {
            const qty = r.inventory?.[c.id];
            return (
              <Item key={c.id} label={c.label}>
                {qty === undefined ? (
                  <>{NOT_AVAILABLE} (not tracked)</>
                ) : (
                  <>
                    {formatNumber(qty, c.quantityUnit)} ·{' '}
                    {AVAILABILITY_LABELS[availabilityOf({ ...r, availableQuantity: qty }, c.id)]}
                  </>
                )}
              </Item>
            );
          })}
          <Item label="Weekly distribution capacity">
            {formatNumber(r.weeklyCapacity, 'households per week')}
          </Item>
          <Item label="Open days">
            {r.operatingDays?.length
              ? `${r.operatingDays.join(', ')}${r.isDemoData ? ' (demo data)' : ''}`
              : confirm}
          </Item>
        </dl>
      </Card>

      <Card>
        <h2 className="mb-3 font-semibold">Location and contact</h2>
        <dl className="grid gap-4 sm:grid-cols-2">
          <Item label="Area">{[r.borough ?? r.city, r.zipCode].filter(Boolean).join(' · ')}</Item>
          <Item label="Address">{r.address ?? confirm}</Item>
          <Item label="Phone">
            {tel ? (
              <a className="text-accent underline" href={tel}>
                {r.phone}
              </a>
            ) : (
              confirm
            )}
          </Item>
          <Item label="Hours">{r.hours ?? confirm}</Item>
          <Item label="Eligibility requirements">{r.eligibility ?? confirm}</Item>
        </dl>
        {maps && (
          <ExternalLinkButton href={maps} className="mt-4" variant="secondary">
            Directions
          </ExternalLinkButton>
        )}
      </Card>

      <Card>
        <h2 className="mb-3 font-semibold">About this information</h2>
        <dl className="grid gap-4 sm:grid-cols-2">
          <Item label="Inventory last updated">{formatUpdated(r.lastUpdated)}</Item>
          <Item label="Verification status">{r.verified ? 'Verified' : 'Not verified'}</Item>
          <Item label="Data source">{r.source}</Item>
        </dl>
      </Card>
    </div>
  );
}
