import type { Resource } from '../types/resource';

export interface MappableResource extends Resource {
  latitude: number;
  longitude: number;
}

/** Real coordinates only: in range and not the (0,0) "null island" placeholder. */
export function hasValidCoordinates(
  r: Pick<Resource, 'latitude' | 'longitude'>,
): r is { latitude: number; longitude: number } {
  const { latitude: lat, longitude: lon } = r;
  return (
    typeof lat === 'number' &&
    typeof lon === 'number' &&
    Number.isFinite(lat) &&
    Number.isFinite(lon) &&
    lat >= -90 &&
    lat <= 90 &&
    lon >= -180 &&
    lon <= 180 &&
    !(lat === 0 && lon === 0)
  );
}

export const mappable = (resources: Resource[]): MappableResource[] =>
  resources.filter((r): r is MappableResource => hasValidCoordinates(r));

const pilotBase = () => String(import.meta.env.VITE_PILOT_API_BASE_URL ?? '').replace(/\/+$/, '');

/**
 * The map is served through the pilot API (account policy blocks browser-side Amazon Location keys), so it is
 * only available when the real API is in use: a base URL is configured and mock resources are off.
 */
export const isMapConfigured = () =>
  pilotBase() !== '' &&
  String(import.meta.env.VITE_USE_MOCK_RESOURCES ?? 'true').toLowerCase() === 'false';

/** MapLibre style URL: our API rewrites the Amazon style so every tile/sprite/glyph URL points back at it. */
export const proxyStyleUrl = (scheme: 'Light' | 'Dark') =>
  `${pilotBase()}/api/v1/maps/style?scheme=${scheme}`;

/** Adds the user's access token, but only to requests that go to our own map proxy. */
export function authorizeMapRequest(
  url: string,
  token: string | null,
): { url: string; headers: Record<string, string> } | undefined {
  if (!token || !url.startsWith(`${pilotBase()}/api/v1/maps/`)) return undefined;
  return { url, headers: { Authorization: `Bearer ${token}` } };
}

export const supportsWebGL = (): boolean => {
  try {
    const c = document.createElement('canvas');
    return !!(c.getContext('webgl2') || c.getContext('webgl'));
  } catch {
    return false;
  }
};
