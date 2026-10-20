import { Link } from 'react-router';
import { Globe, MapPin, MessageCircle, Navigation, Phone } from 'lucide-react';
import { Card } from '../../../components/ui/Card';
import { getCategory } from '../../../config/resourceCategories';
import { availabilityOf, AVAILABILITY_LABELS } from '../utils/availability';
import { hasValidCoordinates } from '../utils/geo';
import { directionsHref, formatNumber, formatUpdated, telHref } from '../utils/format';
import { DemoBadge } from './DemoNotice';
import type { Resource, ResourceType } from '../types/resource';

const statusStyle = {
  in_stock: 'border-emerald-500/40 text-emerald-700 dark:text-emerald-300',
  low: 'border-amber-500/40 text-amber-700 dark:text-amber-300',
  out: 'border-red-500/40 text-red-700 dark:text-red-300',
  unknown: 'border-line text-muted',
} as const;

const Row = ({ label, children }: { label: string; children: React.ReactNode }) => (
  <div className="flex justify-between gap-3 text-sm">
    <dt className="text-muted">{label}</dt>
    <dd className="text-right">{children}</dd>
  </div>
);

interface Props {
  resource: Resource;
  type: ResourceType;
  onAskAI: (r: Resource) => void;
  /** Map synchronization (optional). When set, a "Show on map" action appears for providers with coordinates. */
  selected?: boolean;
  onSelect?: (id: string) => void;
}

export function ResourceCard({ resource: r, type, onAskAI, selected, onSelect }: Props) {
  const status = availabilityOf(r, type);
  const cat = getCategory(type);
  const tel = telHref(r.phone);
  const maps = directionsHref(r);
  const btn =
    'inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-line px-4 text-sm font-medium hover:bg-surface-2';

  return (
    <Card
      id={`resource-${r.id}`}
      className={`flex h-full flex-col gap-4 ${selected ? 'ring-2 ring-accent' : ''}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold">{r.name}</h3>
          <p className="text-sm text-muted">
            {[r.borough ?? r.city, r.zipCode].filter(Boolean).join(' · ')}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {r.isDemoData && <DemoBadge />}
          <span className={`rounded-full border px-2.5 py-0.5 text-xs ${statusStyle[status]}`}>
            {AVAILABILITY_LABELS[status]}
          </span>
        </div>
      </div>

      <dl className="space-y-1.5">
        {type !== 'food_assistance' && (
          <Row label={`Available ${cat.label.toLowerCase()}`}>
            {formatNumber(r.availableQuantity, cat.quantityUnit)}
          </Row>
        )}
        {r.distanceMiles !== undefined && (
          <Row label="Distance">{r.distanceMiles} mi (straight line)</Row>
        )}
        <Row label="Weekly capacity">{formatNumber(r.weeklyCapacity, 'households')}</Row>
        <Row label="Last updated">{formatUpdated(r.lastUpdated)}</Row>
        <Row label="Data source">{r.isDemoData ? 'Demo data' : r.source}</Row>
        {r.freshness && r.freshness !== 'unknown' && (
          <Row label="Freshness">
            {r.freshness === 'fresh' ? 'Recently synced' : 'May be out of date'}
          </Row>
        )}
        <Row label="Verification">{r.verified ? 'Verified' : 'Not verified'}</Row>
      </dl>

      <div className="mt-auto flex flex-wrap gap-2">
        <Link
          to={`/ai-for-good/resources/${r.id}`}
          aria-label={`View details for ${r.name}`}
          className={`${btn} brand-gradient border-transparent text-white`}
        >
          View details
        </Link>
        <button
          type="button"
          onClick={() => onAskAI(r)}
          aria-label={`Ask AI about ${r.name}`}
          className={btn}
        >
          <MessageCircle size={16} aria-hidden /> Ask AI
        </button>
        {onSelect && hasValidCoordinates(r) && (
          <button
            type="button"
            onClick={() => onSelect(r.id)}
            aria-pressed={!!selected}
            aria-label={`Show ${r.name} on the map`}
            className={btn}
          >
            <MapPin size={16} aria-hidden /> Show on map
          </button>
        )}
        {r.website && /^https?:\/\//i.test(r.website) && (
          <a href={r.website} target="_blank" rel="noopener noreferrer" className={btn}>
            <Globe size={16} aria-hidden /> Website
          </a>
        )}
        {tel && (
          <a href={tel} className={btn}>
            <Phone size={16} aria-hidden /> Call provider
          </a>
        )}
        {maps && (
          <a href={maps} target="_blank" rel="noopener noreferrer" className={btn}>
            <Navigation size={16} aria-hidden /> Directions
          </a>
        )}
      </div>
    </Card>
  );
}
