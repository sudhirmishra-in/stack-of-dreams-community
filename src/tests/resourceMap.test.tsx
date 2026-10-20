/**
 * The real ResourceMap component against a faked MapLibre (jsdom has no WebGL). Guards the timing bug where the
 * map is created asynchronously (it waits for the access token) but markers were only placed on the first render,
 * so they never appeared.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, waitFor } from '@testing-library/react';

const h = vi.hoisted(() => ({
  maps: [] as {
    opts: Record<string, unknown>;
    fitBounds: unknown;
    easeTo: unknown;
    setStyle: unknown;
    removed: boolean;
  }[],
  markers: [] as { el: HTMLElement; lngLat: number[]; added: boolean; removed: boolean }[],
  token: 'tok-1' as string | null,
  tokenDelayMs: 20,
}));

vi.mock('maplibre-gl', () => {
  class FakeMap {
    removed = false;
    fitBounds = vi.fn();
    easeTo = vi.fn();
    setStyle = vi.fn();
    constructor(public opts: Record<string, unknown>) {
      h.maps.push(this as never);
    }
    addControl() {}
    on() {}
    remove() {
      this.removed = true;
    }
  }
  class FakeMarker {
    el: HTMLElement;
    lngLat: number[] = [];
    added = false;
    removed = false;
    constructor(o: { element: HTMLElement }) {
      this.el = o.element;
      h.markers.push(this as never);
    }
    setLngLat(l: number[]) {
      this.lngLat = l;
      return this;
    }
    addTo() {
      this.added = true;
      return this;
    }
    remove() {
      this.removed = true;
    }
    getElement() {
      return this.el;
    }
  }
  class FakeBounds {
    n = 0;
    extend() {
      this.n++;
    }
    isEmpty() {
      return this.n === 0;
    }
  }
  return {
    Map: FakeMap,
    Marker: FakeMarker,
    LngLatBounds: FakeBounds,
    NavigationControl: class {},
    setWorkerUrl: vi.fn(),
  };
});
vi.mock('maplibre-gl/dist/maplibre-gl-worker.mjs?url', () => ({ default: '/worker.mjs' }));
vi.mock('../services/authService', () => ({
  authService: {
    getAccessToken: () => new Promise((r) => setTimeout(() => r(h.token), h.tokenDelayMs)),
  },
}));

import ResourceMap from '../features/aiForGood/components/ResourceMap';
import type { Resource } from '../features/aiForGood/types/resource';

const res = (id: string, lat?: number, lon?: number): Resource => ({
  id,
  name: `Pantry ${id}`,
  city: 'New York',
  resourceTypes: ['food_assistance'],
  source: 's',
  verified: false,
  isDemoData: false,
  latitude: lat,
  longitude: lon,
});
const origin = { zipCode: '10027', latitude: 40.81, longitude: -73.95, geocoded: true };

beforeEach(() => {
  h.maps.length = 0;
  h.markers.length = 0;
  h.token = 'tok-1';
  vi.stubEnv('VITE_PILOT_API_BASE_URL', 'https://pilot.test');
  HTMLCanvasElement.prototype.getContext = (() => ({})) as never; // pretend WebGL exists
});

const props = { selectedId: null, onSelect: vi.fn(), dark: true };

describe('ResourceMap', () => {
  it('places a marker for every provider with coordinates even though the map is created after the token arrives', async () => {
    render(
      <ResourceMap
        {...props}
        resources={[res('a', 40.8, -73.95), res('b'), res('c', 40.7, -73.9)]}
        origin={origin}
      />,
    );
    await waitFor(() => expect(h.maps).toHaveLength(1));
    // 2 providers with coordinates + the ZIP-center dot; the provider without coordinates gets no marker
    await waitFor(() => expect(h.markers.filter((m) => m.added)).toHaveLength(3));
    const labels = h.markers.map((m) => m.el.getAttribute('aria-label'));
    expect(labels).toEqual(
      expect.arrayContaining([
        'Show Pantry a in the list',
        'Show Pantry c in the list',
        'Your ZIP code 10027',
      ]),
    );
    expect(labels).not.toContain('Show Pantry b in the list');
    expect(h.maps[0].fitBounds).toHaveBeenCalled();
  });

  it('sends the access token only to the map proxy', async () => {
    render(<ResourceMap {...props} resources={[res('a', 40.8, -73.95)]} />);
    await waitFor(() => expect(h.maps).toHaveLength(1));
    const t = h.maps[0].opts.transformRequest as (u: string) => unknown;
    expect(t('https://pilot.test/api/v1/maps/tiles/vector.basemap/1/0/0')).toEqual({
      url: 'https://pilot.test/api/v1/maps/tiles/vector.basemap/1/0/0',
      headers: { Authorization: 'Bearer tok-1' },
    });
    expect(t('https://other.example/x')).toBeUndefined();
  });

  it('highlights the selected marker and pans to it, including a selection made before the map existed', async () => {
    const { rerender } = render(
      <ResourceMap
        {...props}
        selectedId="c"
        resources={[res('a', 40.8, -73.95), res('c', 40.7, -73.9)]}
      />,
    );
    await waitFor(() => expect(h.markers.filter((m) => m.added)).toHaveLength(2));
    const byLabel = (n: string) =>
      h.markers.findLast(
        (m) => !m.removed && m.el.getAttribute('aria-label') === `Show Pantry ${n} in the list`,
      )!; // the CURRENT marker, not a removed earlier one;
    await waitFor(() => expect(byLabel('c').el.classList.contains('is-selected')).toBe(true));
    expect(byLabel('a').el.classList.contains('is-selected')).toBe(false);
    expect(h.maps[0].easeTo).toHaveBeenCalledWith(
      expect.objectContaining({ center: [-73.9, 40.7] }),
    );
    rerender(
      <ResourceMap
        {...props}
        selectedId="a"
        resources={[res('a', 40.8, -73.95), res('c', 40.7, -73.9)]}
      />,
    );
    await waitFor(() => expect(byLabel('a').el.classList.contains('is-selected')).toBe(true));
    expect(byLabel('c').el.classList.contains('is-selected')).toBe(false);
  });

  it('clicking a marker reports the selection', async () => {
    const onSelect = vi.fn();
    render(<ResourceMap {...props} onSelect={onSelect} resources={[res('a', 40.8, -73.95)]} />);
    await waitFor(() => expect(h.markers.some((m) => m.added)).toBe(true));
    h.markers.find((m) => m.el.getAttribute('aria-label')?.includes('Pantry a'))!.el.click();
    expect(onSelect).toHaveBeenCalledWith('a');
  });

  it('replaces markers when the results change and removes the old ones', async () => {
    const { rerender } = render(<ResourceMap {...props} resources={[res('a', 40.8, -73.95)]} />);
    await waitFor(() => expect(h.markers.filter((m) => m.added)).toHaveLength(1));
    rerender(<ResourceMap {...props} resources={[res('b', 40.7, -73.9), res('c', 40.6, -73.8)]} />);
    await waitFor(() => expect(h.markers.filter((m) => m.added && !m.removed)).toHaveLength(2));
    expect(
      h.markers.find((m) => m.el.getAttribute('aria-label')?.includes('Pantry a'))!.removed,
    ).toBe(true);
  });

  it('restyles only when the theme really changes (not right after the map is created)', async () => {
    const { rerender } = render(<ResourceMap {...props} resources={[res('a', 40.8, -73.95)]} />);
    await waitFor(() => expect(h.markers.some((m) => m.added)).toBe(true));
    const setStyle = h.maps[0].setStyle as ReturnType<typeof vi.fn>;
    expect(setStyle).not.toHaveBeenCalled();
    rerender(<ResourceMap {...props} dark={false} resources={[res('a', 40.8, -73.95)]} />);
    await waitFor(() => expect(setStyle).toHaveBeenCalledTimes(1));
    expect(setStyle.mock.calls[0][0]).toContain('scheme=Light');
  });

  it('does not create a map after unmounting mid token fetch', async () => {
    h.tokenDelayMs = 50;
    const { unmount } = render(<ResourceMap {...props} resources={[res('a', 40.8, -73.95)]} />);
    unmount();
    await act(async () => new Promise((r) => setTimeout(r, 120)));
    h.tokenDelayMs = 20;
    expect(h.maps).toHaveLength(0);
  });

  it('falls back to the list message when WebGL is unavailable', () => {
    HTMLCanvasElement.prototype.getContext = (() => null) as never;
    const { getByText } = render(<ResourceMap {...props} resources={[res('a', 40.8, -73.95)]} />);
    expect(getByText(/map is unavailable/i)).toBeInTheDocument();
    expect(h.maps).toHaveLength(0);
  });
});
