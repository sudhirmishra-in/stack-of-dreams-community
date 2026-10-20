import type {
  Resource,
  ResourceSearchResponse,
  ResourceService,
  RouteResult,
} from '../features/aiForGood/types/resource';
import { authService } from './authService';
import { ResourceServiceError } from './resourceErrors';

const TIMEOUT_MS = 30_000;

/** Prefers the pilot platform URL; VITE_RESOURCE_API_BASE_URL is kept as a fallback for older setups. */
const base = () =>
  String(
    import.meta.env.VITE_PILOT_API_BASE_URL || import.meta.env.VITE_RESOURCE_API_BASE_URL || '',
  ).replace(/\/+$/, '');

const isSearchResponse = (d: unknown): d is ResourceSearchResponse => {
  const r = d as Partial<ResourceSearchResponse> | null;
  return !!r && Array.isArray(r.resources) && typeof r.totalResults === 'number';
};

interface ApiErrorBody {
  error?: { code?: string; message?: string; correlationId?: string };
}

function friendly(status: number, body: ApiErrorBody | null): ResourceServiceError {
  const msg = body?.error?.message;
  if (status === 401) return new ResourceServiceError('Please sign in to search resources.', 401);
  if (status === 403)
    return new ResourceServiceError(msg || 'Your account does not have access.', 403);
  if (status === 429)
    return new ResourceServiceError(msg || 'Daily limit reached. Please try again later.', 429);
  if (status === 503)
    return new ResourceServiceError(msg || 'The service is temporarily unavailable.', 503);
  if (status === 400) return new ResourceServiceError(msg || 'The search was not valid.', 400);
  return new ResourceServiceError(`The server responded with an error (HTTP ${status}).`, status);
}

async function request(path: string, init: RequestInit, signal?: AbortSignal): Promise<unknown> {
  const root = base();
  if (!root) {
    throw new ResourceServiceError(
      'The resource API is not configured. Set VITE_PILOT_API_BASE_URL or enable VITE_USE_MOCK_RESOURCES.',
    );
  }
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = await authService.getAccessToken().catch(() => null);
  if (token) headers.Authorization = `Bearer ${token}`;

  const timeout = AbortSignal.timeout(TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`${root}${path}`, {
      ...init,
      headers,
      signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    });
  } catch (err) {
    if (signal?.aborted) throw err;
    throw new ResourceServiceError(
      timeout.aborted
        ? 'The request timed out. Please try again.'
        : 'Could not reach the server. Check your connection and retry.',
    );
  }
  if (res.status === 404) return null;
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    if (res.ok) throw new ResourceServiceError('The server returned an unreadable response.');
  }
  if (!res.ok) throw friendly(res.status, body as ApiErrorBody | null);
  return body;
}

const isUndefinedFree = <T extends object>(o: T): T =>
  Object.fromEntries(Object.entries(o).filter(([, v]) => v !== undefined && v !== null)) as T;

/**
 * Pilot platform contract (see platform/docs/api-contracts.md):
 *   POST /api/v1/resources/search          -> ResourceSearchResponse   (deterministic, no LLM)
 *   GET  /api/v1/resources/{id}            -> { resource }             (404 when unknown)
 *   GET  /api/v1/route?fromZip&toResourceId&mode -> route summary      (Amazon Location)
 */
export const httpResourceService: ResourceService = {
  isMock: false,

  async search(req, signal) {
    const data = await request(
      '/api/v1/resources/search',
      { method: 'POST', body: JSON.stringify(isUndefinedFree({ ...req, limit: req.limit ?? 50 })) },
      signal,
    );
    if (!isSearchResponse(data))
      throw new ResourceServiceError('The server returned an unexpected response format.');
    return data;
  },

  async getResource(id, signal) {
    const data = (await request(
      `/api/v1/resources/${encodeURIComponent(id)}`,
      { method: 'GET' },
      signal,
    )) as {
      resource?: Resource;
    } | null;
    if (data === null) return null;
    const r = data.resource;
    if (!r || typeof r.id !== 'string' || typeof r.name !== 'string') {
      throw new ResourceServiceError('The server returned an unexpected response format.');
    }
    return r;
  },

  /** The coordinator dashboard shows demo inventory, so it asks for demo records explicitly. */
  async listResources(signal) {
    const data = await request(
      '/api/v1/resources/search',
      {
        method: 'POST',
        body: JSON.stringify({
          zipCode: '10027',
          resourceType: 'baby_formula',
          includeDemo: true,
          limit: 50,
        }),
      },
      signal,
    );
    if (!isSearchResponse(data))
      throw new ResourceServiceError('The server returned an unexpected response format.');
    return data;
  },

  async getRoute(zipCode, resourceId, mode, signal): Promise<RouteResult> {
    const q = new URLSearchParams({ fromZip: zipCode, toResourceId: resourceId, mode });
    const d = (await request(
      `/api/v1/route?${q}`,
      { method: 'GET' },
      signal,
    )) as Partial<RouteResult> | null;
    if (!d || typeof d.distanceMiles !== 'number' || typeof d.durationMinutes !== 'number') {
      throw new ResourceServiceError('No route is available for this provider.');
    }
    return {
      distanceMiles: d.distanceMiles,
      durationMinutes: d.durationMinutes,
      travelMode: mode,
      provider: d.provider ?? 'Amazon Location Service',
    };
  },
};
