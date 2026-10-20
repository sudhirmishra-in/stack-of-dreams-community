export type ResourceType = 'baby_formula' | 'groceries' | 'diapers' | 'food_assistance';
export type Urgency = 'today' | 'three_days' | 'this_week';
export type SortBy = 'nearest' | 'availability' | 'capacity';
export type AvailabilityStatus = 'in_stock' | 'low' | 'out' | 'unknown';

export interface ResourceSearchRequest {
  zipCode: string;
  resourceType: ResourceType;
  quantity?: number;
  formulaType?: string;
  urgency?: Urgency;
  sortBy?: SortBy;
  /** Only honored when the ZIP could be located; the server says so in `origin.geocoded`. */
  radiusMiles?: number;
  /** Real directory records never include inventory; demo records do and are always labeled. */
  includeDemo?: boolean;
  limit?: number;
  cursor?: string;
}

export interface Resource {
  id: string;
  name: string;
  city: string;
  borough?: string;
  /** Some real records have coordinates but no ZIP code. */
  zipCode?: string;
  address?: string;
  phone?: string;
  website?: string;
  latitude?: number;
  longitude?: number;
  resourceTypes: ResourceType[];
  /** Quantity of the *searched* resource type (set on search results). */
  availableQuantity?: number;
  /** Quantity per resource type, when the data source tracks it. */
  inventory?: Partial<Record<ResourceType, number>>;
  /** Households served per week. */
  weeklyCapacity?: number;
  operatingDays?: string[];
  hours?: string;
  eligibility?: string;
  lastUpdated?: string;
  source: string;
  verified: boolean;
  isDemoData: boolean;
  // Provenance, populated by the real API (all optional so the mock service still satisfies the type).
  sourceId?: string;
  sourceUrl?: string;
  attribution?: string;
  sourceUpdatedAt?: string;
  lastSyncedAt?: string;
  lastVerifiedAt?: string;
  freshness?: 'fresh' | 'stale' | 'unknown';
  distanceMiles?: number;
  inventoryIsDemo?: boolean;
}

export interface SearchOrigin {
  zipCode: string;
  latitude?: number;
  longitude?: number;
  /** False means distances are unavailable: nothing is estimated. */
  geocoded: boolean;
}

export interface ResourceSearchResponse {
  resources: Resource[];
  totalResults: number;
  dataSource: string;
  isDemoData: boolean;
  origin?: SearchOrigin;
  notes?: string[];
  attributions?: string[];
  nextCursor?: string;
  correlationId?: string;
}

export interface RouteResult {
  distanceMiles: number;
  durationMinutes: number;
  travelMode: 'Car' | 'Pedestrian';
  provider: string;
}

export interface ResourceService {
  /** True when data is generated locally. */
  readonly isMock: boolean;
  search(request: ResourceSearchRequest, signal?: AbortSignal): Promise<ResourceSearchResponse>;
  getResource(id: string, signal?: AbortSignal): Promise<Resource | null>;
  /** All resources with full inventory, for the coordinator dashboard. */
  listResources(signal?: AbortSignal): Promise<ResourceSearchResponse>;
  /** Optional: real travel distance/time from a ZIP (only the real API provides it). */
  getRoute?(
    zipCode: string,
    resourceId: string,
    mode: 'Car' | 'Pedestrian',
    signal?: AbortSignal,
  ): Promise<RouteResult>;
}
