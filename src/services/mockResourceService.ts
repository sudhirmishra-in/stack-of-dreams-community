import type {
  Resource,
  ResourceSearchRequest,
  ResourceSearchResponse,
  ResourceService,
  ResourceType,
} from '../features/aiForGood/types/resource';

export const DEMO_SOURCE = 'DEMO DATA: synthetic sample records (not real organizations)';

interface Seed {
  id: string;
  name: string;
  borough: string;
  zip: string;
  capacity: number;
  days: string[];
  produce: number;
  canned: number;
  dairy: number;
  formula: number;
}

/**
 * Fictional organizations. This intentionally mirrors the synthetic dataset behind the assistant's
 * lookup tool, so the structured results and the assistant describe the same demo records.
 * Nothing here is real: no addresses, phone numbers or hours are provided on purpose.
 */
const SEEDS: Seed[] = [
  {
    id: 'fb-001',
    name: 'Harbor Community Pantry',
    borough: 'Brooklyn',
    zip: '11201',
    capacity: 400,
    days: ['Mon', 'Wed', 'Sat'],
    produce: 1200,
    canned: 2500,
    dairy: 300,
    formula: 0,
  },
  {
    id: 'fb-002',
    name: 'Riverside Food Share',
    borough: 'Manhattan',
    zip: '10027',
    capacity: 650,
    days: ['Tue', 'Thu', 'Fri'],
    produce: 800,
    canned: 4000,
    dairy: 900,
    formula: 150,
  },
  {
    id: 'fb-003',
    name: 'Queens Neighbors Kitchen',
    borough: 'Queens',
    zip: '11375',
    capacity: 250,
    days: ['Mon', 'Fri', 'Sun'],
    produce: 150,
    canned: 600,
    dairy: 0,
    formula: 40,
  },
  {
    id: 'fb-004',
    name: 'Bronx Bread & Beyond',
    borough: 'Bronx',
    zip: '10451',
    capacity: 500,
    days: ['Wed', 'Thu', 'Sat'],
    produce: 2000,
    canned: 1800,
    dairy: 500,
    formula: 75,
  },
  {
    id: 'fb-005',
    name: 'Staten Island Helping Hands',
    borough: 'Staten Island',
    zip: '10301',
    capacity: 180,
    days: ['Tue', 'Sat'],
    produce: 90,
    canned: 700,
    dairy: 60,
    formula: 0,
  },
];

const toResource = (s: Seed): Resource => {
  const groceries = s.produce + s.canned + s.dairy;
  const types: ResourceType[] = ['food_assistance'];
  if (groceries > 0) types.push('groceries');
  if (s.formula > 0) types.push('baby_formula');
  return {
    id: s.id,
    name: s.name,
    city: s.borough === 'Staten Island' ? 'Staten Island' : s.borough,
    borough: s.borough,
    zipCode: s.zip,
    resourceTypes: types,
    // Diaper stock is not tracked in the demo dataset, so it is deliberately absent.
    inventory: { baby_formula: s.formula, groceries },
    weeklyCapacity: s.capacity,
    operatingDays: s.days,
    source: DEMO_SOURCE,
    verified: false,
    isDemoData: true,
  };
};

const ALL = SEEDS.map(toResource);

const zipDistance = (a: string, b: string) => Math.abs(Number(a) - Number(b));

export function searchDemoResources(req: ResourceSearchRequest): Resource[] {
  const type = req.resourceType;
  let list = ALL.filter((r) => r.resourceTypes.includes(type)).map<Resource>((r) => ({
    ...r,
    availableQuantity: r.inventory?.[type],
  }));
  if (req.quantity && type !== 'food_assistance') {
    list = list.filter((r) => (r.availableQuantity ?? 0) >= req.quantity!);
  }
  const sort = req.sortBy ?? 'nearest';
  // There is no geocoding in demo mode: "nearest" is a rough ZIP-code similarity, not a distance.
  const by: Record<string, (a: Resource, b: Resource) => number> = {
    nearest: (a, b) =>
      zipDistance(a.zipCode ?? '0', req.zipCode) - zipDistance(b.zipCode ?? '0', req.zipCode),
    availability: (a, b) => (b.availableQuantity ?? -1) - (a.availableQuantity ?? -1),
    capacity: (a, b) => (b.weeklyCapacity ?? 0) - (a.weeklyCapacity ?? 0),
  };
  return [...list].sort(by[sort] ?? by.nearest);
}

const delay = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException('Aborted', 'AbortError'));
    if (ms <= 0) return resolve();
    const t = setTimeout(resolve, ms);
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(t);
        reject(new DOMException('Aborted', 'AbortError'));
      },
      { once: true },
    );
  });

/** Typing this ZIP in demo mode makes the search fail, so the error state can be shown. */
export const MOCK_ERROR_ZIP = '00000';

export function createMockResourceService(delayMs = 700): ResourceService {
  const respond = (resources: Resource[]): ResourceSearchResponse => ({
    resources,
    totalResults: resources.length,
    dataSource: DEMO_SOURCE,
    isDemoData: true,
  });
  return {
    isMock: true,
    async search(request, signal) {
      await delay(delayMs, signal);
      if (request.zipCode === MOCK_ERROR_ZIP) throw new Error('Simulated demo failure.');
      return respond(searchDemoResources(request));
    },
    async getResource(id, signal) {
      await delay(delayMs / 2, signal);
      return ALL.find((r) => r.id === id) ?? null;
    },
    async listResources(signal) {
      await delay(delayMs, signal);
      return respond(ALL);
    },
  };
}

export const mockResourceService = createMockResourceService();
