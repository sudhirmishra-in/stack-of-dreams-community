import { useId } from 'react';
import type { AvailabilityFilter } from '../utils/availability';
import type { SortBy } from '../types/resource';

interface Props {
  availability: AvailabilityFilter;
  onAvailability: (f: AvailabilityFilter) => void;
  sortBy: SortBy;
  onSortBy: (s: SortBy) => void;
  showAvailability: boolean;
  /** Distance filter: only offered when the server could locate the ZIP code. */
  showRadius?: boolean;
  radiusMiles?: number;
  onRadius?: (miles: number | undefined) => void;
}

const FILTERS: { value: AvailabilityFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'available', label: 'Available now' },
  { value: 'low', label: 'Low stock' },
  { value: 'out', label: 'Out of stock' },
];

const RADII = [1, 3, 5, 10];
const selectClass = 'min-h-11 rounded-xl border border-line bg-surface px-3 text-sm';

export function ResourceFilters({
  availability,
  onAvailability,
  sortBy,
  onSortBy,
  showAvailability,
  showRadius,
  radiusMiles,
  onRadius,
}: Props) {
  const sortId = useId();
  const radiusId = useId();
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      {showAvailability ? (
        <div role="group" aria-label="Filter by availability" className="flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              aria-pressed={availability === f.value}
              onClick={() => onAvailability(f.value)}
              className={`min-h-11 rounded-full border px-4 text-sm transition ${
                availability === f.value
                  ? 'border-accent bg-surface-2 font-medium'
                  : 'border-line hover:bg-surface-2'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      ) : (
        <span />
      )}
      <div className="flex flex-wrap items-center gap-4">
        {showRadius && onRadius && (
          <div>
            <label htmlFor={radiusId} className="mr-2 text-sm text-muted">
              Within
            </label>
            <select
              id={radiusId}
              value={radiusMiles ?? ''}
              onChange={(e) => onRadius(e.target.value ? Number(e.target.value) : undefined)}
              className={selectClass}
            >
              <option value="">Any distance</option>
              {RADII.map((r) => (
                <option key={r} value={r}>
                  {r} {r === 1 ? 'mile' : 'miles'}
                </option>
              ))}
            </select>
          </div>
        )}
        <div>
          <label htmlFor={sortId} className="mr-2 text-sm text-muted">
            Sort by
          </label>
          <select
            id={sortId}
            value={sortBy}
            onChange={(e) => onSortBy(e.target.value as SortBy)}
            className={selectClass}
          >
            <option value="nearest">Closest ZIP code</option>
            <option value="availability">Most available</option>
            <option value="capacity">Highest weekly capacity</option>
          </select>
        </div>
      </div>
    </div>
  );
}
