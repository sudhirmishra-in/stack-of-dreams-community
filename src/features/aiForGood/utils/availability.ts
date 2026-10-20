import { getCategory } from '../../../config/resourceCategories';
import type { AvailabilityStatus, Resource, ResourceType } from '../types/resource';

export type AvailabilityFilter = 'all' | 'available' | 'low' | 'out';

export const AVAILABILITY_LABELS: Record<AvailabilityStatus, string> = {
  in_stock: 'In stock',
  low: 'Low stock',
  out: 'Out of stock',
  unknown: 'Contact provider to confirm',
};

export function availabilityOf(resource: Resource, type: ResourceType): AvailabilityStatus {
  const qty = resource.availableQuantity ?? resource.inventory?.[type];
  if (qty === undefined) return 'unknown';
  if (qty <= 0) return 'out';
  const low = getCategory(type).lowThreshold;
  return low !== undefined && qty < low ? 'low' : 'in_stock';
}

export function filterByAvailability(
  resources: Resource[],
  type: ResourceType,
  filter: AvailabilityFilter,
): Resource[] {
  if (filter === 'all') return resources;
  return resources.filter((r) => {
    const s = availabilityOf(r, type);
    if (filter === 'available') return s === 'in_stock' || s === 'low';
    return s === filter;
  });
}
