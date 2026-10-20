import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  createMockResourceService,
  searchDemoResources,
  MOCK_ERROR_ZIP,
} from '../services/mockResourceService';
import { httpResourceService } from '../services/httpResourceService';
import { ResourceServiceError } from '../services/resourceErrors';
import {
  parseSearchParams,
  toSearchParams,
  validateSearchForm,
} from '../features/aiForGood/utils/searchParams';
import { availabilityOf, filterByAvailability } from '../features/aiForGood/utils/availability';
import { directionsHref, telHref } from '../features/aiForGood/utils/format';
import { buildResourcePrompt, buildResultsPrompt } from '../features/aiForGood/utils/prompts';
import { buildDemoRecommendations } from '../features/aiForGood/pages/CoordinatorDashboardPage';
import { computeStats } from '../features/aiForGood/components/DashboardStats';

const base = { zipCode: '10027', resourceType: 'baby_formula' as const };

describe('mock resource service', () => {
  it('filters by resource type', () => {
    const ids = searchDemoResources(base).map((r) => r.id);
    expect(ids).toEqual(expect.arrayContaining(['fb-002', 'fb-003', 'fb-004']));
    expect(ids).not.toContain('fb-001'); // 0 formula units
    expect(ids).not.toContain('fb-005');
  });

  it('labels every record as unverified demo data', async () => {
    const res = await createMockResourceService(0).search(base);
    expect(res.isDemoData).toBe(true);
    expect(res.dataSource).toMatch(/DEMO DATA/);
    expect(res.resources.every((r) => r.isDemoData && !r.verified)).toBe(true);
    // No invented contact details
    expect(res.resources.every((r) => !r.phone && !r.address)).toBe(true);
    expect(res.totalResults).toBe(res.resources.length);
  });

  it('sorts by nearest ZIP, availability and capacity', () => {
    expect(searchDemoResources({ ...base, sortBy: 'nearest' })[0].id).toBe('fb-002');
    expect(searchDemoResources({ ...base, sortBy: 'availability' })[0].id).toBe('fb-002');
    const cap = searchDemoResources({ ...base, resourceType: 'groceries', sortBy: 'capacity' });
    expect(cap.map((r) => r.weeklyCapacity)).toEqual(
      [...cap.map((r) => r.weeklyCapacity)].sort((a, b) => b! - a!),
    );
  });

  it('applies the minimum quantity', () => {
    expect(searchDemoResources({ ...base, quantity: 100 }).map((r) => r.id)).toEqual(['fb-002']);
    expect(searchDemoResources({ ...base, quantity: 9999 })).toEqual([]);
  });

  it('does not invent diaper inventory', () => {
    expect(searchDemoResources({ ...base, resourceType: 'diapers' })).toEqual([]);
  });

  it('gets one resource, returns null for unknown ids, and can fail on demand', async () => {
    const svc = createMockResourceService(0);
    expect((await svc.getResource('fb-002'))?.name).toBe('Riverside Food Share');
    expect(await svc.getResource('nope')).toBeNull();
    await expect(svc.search({ ...base, zipCode: MOCK_ERROR_ZIP })).rejects.toThrow();
  });
});

describe('search form validation and URL state', () => {
  const ok = {
    resourceType: 'baby_formula' as const,
    zipCode: '10027',
    quantity: '',
    formulaType: 'sensitive',
    urgency: 'today' as const,
    notes: '',
  };

  it('requires a type and a 5-digit ZIP', () => {
    expect(validateSearchForm({ ...ok, resourceType: '', zipCode: '123' }).errors).toMatchObject({
      resourceType: expect.any(String),
      zipCode: expect.any(String),
    });
    expect(validateSearchForm({ ...ok, zipCode: '1002' }).request).toBeUndefined();
    expect(validateSearchForm({ ...ok, zipCode: '100270' }).request).toBeUndefined();
  });

  it('rejects non-positive or fractional quantities but allows blank', () => {
    for (const q of ['0', '-3', '2.5', 'abc'])
      expect(validateSearchForm({ ...ok, quantity: q }).errors.quantity).toBeDefined();
    expect(validateSearchForm({ ...ok, quantity: '' }).request?.quantity).toBeUndefined();
    expect(validateSearchForm({ ...ok, quantity: '12' }).request?.quantity).toBe(12);
  });

  it('only keeps formula type for baby formula', () => {
    expect(
      validateSearchForm({ ...ok, resourceType: 'groceries' }).request?.formulaType,
    ).toBeUndefined();
  });

  it('round-trips through the URL without notes', () => {
    const { request } = validateSearchForm({ ...ok, quantity: '5', notes: 'my private note' });
    const params = toSearchParams(request!);
    expect(params.toString()).not.toContain('private');
    expect(parseSearchParams(params)).toEqual(request);
  });

  it('rejects invalid URL params', () => {
    expect(parseSearchParams(new URLSearchParams('type=bogus&zip=10027'))).toBeNull();
    expect(parseSearchParams(new URLSearchParams('type=groceries&zip=12'))).toBeNull();
  });
});

describe('helpers', () => {
  it('computes availability status', () => {
    const [fb2, fb3] = searchDemoResources(base);
    expect(availabilityOf(fb2, 'baby_formula')).toBe('in_stock');
    expect(
      availabilityOf(
        searchDemoResources(base).find((r) => r.id === 'fb-003')!,
        'baby_formula',
      ),
    ).toBe('low');
    expect(fb3).toBeDefined();
    const list = searchDemoResources(base);
    expect(filterByAvailability(list, 'baby_formula', 'low').map((r) => r.id)).toEqual(['fb-003']);
  });

  it('only builds call and directions links from real, verified data', () => {
    expect(telHref(undefined)).toBeUndefined();
    expect(telHref('555')).toBeUndefined();
    expect(telHref('(212) 555-0100')).toBe('tel:2125550100');
    expect(
      directionsHref({ zipCode: '10027', verified: false, address: '1 Main St' }),
    ).toBeUndefined();
    expect(directionsHref({ zipCode: '10027', verified: true })).toBeUndefined();
    expect(directionsHref({ zipCode: '10027', verified: true, address: '1 Main St' })).toContain(
      'google.com/maps',
    );
  });

  it('assistant prompts carry guardrails, demo labels, and stay short', () => {
    const list = searchDemoResources(base);
    const p = buildResultsPrompt(list, { ...base }, 'note');
    expect(p).toMatch(/Do not invent/);
    expect(p).toMatch(/DEMO DATA/);
    expect(p).toContain('Riverside Food Share');
    expect(p.length).toBeLessThan(4000);
    expect(buildResourcePrompt(list[0])).toMatch(/Use only the facts/);
  });

  it('dashboard stats and rule-based recommendations come from the data', async () => {
    const { resources } = await createMockResourceService(0).listResources();
    expect(computeStats(resources)).toEqual({ orgs: 5, formula: 265, capacity: 1980, low: 3 });
    const recs = buildDemoRecommendations(resources);
    expect(recs[0]).toMatch(/Riverside Food Share/);
  });
});

describe('httpResourceService', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });
  const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status });

  it('POSTs the search to /api/v1/resources/search', async () => {
    vi.stubEnv('VITE_PILOT_API_BASE_URL', 'https://res.test/');
    const body = { resources: [], totalResults: 0, dataSource: 's', isDemoData: false };
    const f = vi.fn().mockResolvedValue(json(body));
    vi.stubGlobal('fetch', f);
    expect(await httpResourceService.search(base)).toEqual(body);
    expect(f.mock.calls[0][0]).toBe('https://res.test/api/v1/resources/search');
    expect(f.mock.calls[0][1].method).toBe('POST');
    expect(JSON.parse(f.mock.calls[0][1].body)).toEqual({ ...base, limit: 50 });
  });

  it('maps failures to friendly errors', async () => {
    vi.stubEnv('VITE_PILOT_API_BASE_URL', 'https://res.test');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({}, 500)));
    await expect(httpResourceService.search(base)).rejects.toMatchObject({ status: 500 });
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('x')));
    await expect(httpResourceService.search(base)).rejects.toThrow(/Could not reach/);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ nope: 1 })));
    await expect(httpResourceService.search(base)).rejects.toBeInstanceOf(ResourceServiceError);
  });

  it('is clear when not configured', async () => {
    vi.stubEnv('VITE_PILOT_API_BASE_URL', '');
    vi.stubEnv('VITE_RESOURCE_API_BASE_URL', '');
    await expect(httpResourceService.search(base)).rejects.toThrow(/not configured/);
  });
});
