import { useEffect, useRef, useState } from 'react';
import {
  LngLatBounds,
  Map as MapLibreMap,
  Marker,
  NavigationControl,
  setWorkerUrl,
} from 'maplibre-gl';
// MapLibre builds its worker URL at runtime, which bundlers cannot see: without this the worker file is neither
// served by the Vite dev server nor emitted into dist/, and the map hangs waiting for it. Importing it as an asset
// URL makes Vite serve it in dev and emit it (hashed) in production. The worker is self-contained.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
import 'maplibre-gl/dist/maplibre-gl.css';
import { authService } from '../../../services/authService';
import { authorizeMapRequest, mappable, proxyStyleUrl, supportsWebGL } from '../utils/geo';
import type { Resource, SearchOrigin } from '../types/resource';

setWorkerUrl(workerUrl);

interface Props {
  resources: Resource[];
  origin?: SearchOrigin;
  selectedId: string | null;
  onSelect: (id: string) => void;
  dark: boolean;
  onFailure?: () => void;
}

/**
 * Pan, zoom, markers and selection are all client-side: no LLM and no server call. Only the style/tile
 * requests go to Amazon Location (with a referrer-restricted key).
 */
export default function ResourceMap({
  resources,
  origin,
  selectedId,
  onSelect,
  dark,
  onFailure,
}: Props) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibreMap | null>(null);
  const markers = useRef<Map<string, Marker>>(new Map());
  const originMarker = useRef<Marker | null>(null);
  const onSelectRef = useRef(onSelect);
  const appliedStyle = useRef<string | null>(null);
  // transformRequest is synchronous, so the (short-lived) access token is kept in a ref and refreshed.
  const tokenRef = useRef<string | null>(null);
  const [failed, setFailed] = useState(() => !supportsWebGL());
  // The map is created asynchronously (it first needs the access token). Effects that draw on the map depend on
  // this flag so they run again once it exists; otherwise markers would only be attempted before it did.
  const [ready, setReady] = useState(false);

  useEffect(() => {
    onSelectRef.current = onSelect;
  });

  // Create the map once (after fetching a token); restyle when the theme changes.
  useEffect(() => {
    if (!el.current || map.current || failed) return;
    let cancelled = false;
    let refresh: ReturnType<typeof setInterval> | undefined;
    // Report failures asynchronously so state is never set synchronously inside the effect body.
    const fail = () =>
      queueMicrotask(() => {
        setFailed(true);
        onFailure?.();
      });

    void (async () => {
      tokenRef.current = await authService.getAccessToken().catch(() => null);
      if (cancelled || !el.current) return;
      try {
        appliedStyle.current = proxyStyleUrl(dark ? 'Dark' : 'Light');
        const m = new MapLibreMap({
          container: el.current,
          style: appliedStyle.current,
          transformRequest: (url) => authorizeMapRequest(url, tokenRef.current),
          center: [-73.95, 40.75],
          zoom: 9.5,
          attributionControl: { compact: true },
        });
        m.addControl(new NavigationControl({ showCompass: false }), 'top-right');
        m.on('error', (e: unknown) => {
          // Unauthorized, blocked or unreachable proxy: fall back to the list instead of looping.
          if ((e as { error?: { status?: number } }).error?.status) fail();
        });
        map.current = m;
        setReady(true);
        // Access tokens last about an hour: keep the one used for tile requests fresh.
        refresh = setInterval(() => {
          void authService.getAccessToken().then((t) => (tokenRef.current = t ?? tokenRef.current));
        }, 5 * 60_000);
      } catch {
        fail();
      }
    })();

    const current = markers.current;
    return () => {
      cancelled = true;
      if (refresh) clearInterval(refresh);
      current.clear();
      map.current?.remove();
      map.current = null;
      setReady(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const next = proxyStyleUrl(dark ? 'Dark' : 'Light');
    if (!map.current || next === appliedStyle.current) return; // only on a real theme change
    appliedStyle.current = next;
    map.current.setStyle(next);
  }, [dark, ready]);

  // Markers follow the results.
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    markers.current.forEach((x) => x.remove());
    markers.current.clear();
    originMarker.current?.remove();
    const pts = mappable(resources);
    pts.forEach((r) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.setAttribute('aria-label', `Show ${r.name} in the list`);
      btn.className = 'resource-marker';
      btn.addEventListener('click', () => onSelectRef.current(r.id));
      markers.current.set(
        r.id,
        new Marker({ element: btn }).setLngLat([r.longitude, r.latitude]).addTo(m),
      );
    });
    const bounds = new LngLatBounds();
    pts.forEach((r) => bounds.extend([r.longitude, r.latitude]));
    if (origin?.geocoded && origin.latitude !== undefined && origin.longitude !== undefined) {
      const dot = document.createElement('div');
      dot.className = 'origin-marker';
      dot.setAttribute('role', 'img');
      dot.setAttribute('aria-label', `Your ZIP code ${origin.zipCode}`);
      originMarker.current = new Marker({ element: dot })
        .setLngLat([origin.longitude, origin.latitude])
        .addTo(m);
      bounds.extend([origin.longitude, origin.latitude]);
    }
    if (!bounds.isEmpty()) m.fitBounds(bounds, { padding: 48, maxZoom: 14, duration: 0 });
  }, [resources, origin, ready]);

  // Selection styling + pan to the selected provider.
  useEffect(() => {
    markers.current.forEach((marker, id) =>
      marker.getElement().classList.toggle('is-selected', id === selectedId),
    );
    const r = selectedId ? mappable(resources).find((x) => x.id === selectedId) : undefined;
    if (r) map.current?.easeTo({ center: [r.longitude, r.latitude], duration: 300 });
  }, [selectedId, resources, ready]);

  if (failed) {
    return (
      <p
        role="status"
        className="rounded-2xl border border-dashed border-line p-6 text-center text-sm text-muted"
      >
        The map is unavailable right now. The list of providers still works.
      </p>
    );
  }
  return (
    <div
      ref={el}
      role="region"
      aria-label="Map of matching providers"
      className="h-80 w-full overflow-hidden rounded-2xl border border-line lg:h-[32rem]"
    />
  );
}
