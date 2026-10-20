import { useId, useState } from 'react';
import { Navigation } from 'lucide-react';
import { Button } from '../../../components/ui/Button';
import { Card } from '../../../components/ui/Card';
import { resourceService } from '../../../services/resourceService';
import { hasValidCoordinates } from '../utils/geo';
import type { Resource, RouteResult } from '../types/resource';

/**
 * Optional, on-demand travel estimate from a ZIP code (Amazon Location, via the API).
 * Nothing is shown unless the service really returns it: no estimated or invented travel times.
 */
export function RouteEstimate({ resource }: { resource: Resource }) {
  const id = useId();
  const [zip, setZip] = useState('');
  const [mode, setMode] = useState<'Car' | 'Pedestrian'>('Car');
  const [state, setState] = useState<{
    status: 'idle' | 'loading' | 'error' | 'done';
    route?: RouteResult;
    error?: string;
  }>({
    status: 'idle',
  });

  if (!resourceService.getRoute || !hasValidCoordinates(resource)) return null;
  const valid = /^\d{5}$/.test(zip);

  const run = async () => {
    setState({ status: 'loading' });
    try {
      const route = await resourceService.getRoute!(zip, resource.id, mode);
      setState({ status: 'done', route });
    } catch (e) {
      setState({
        status: 'error',
        error: e instanceof Error ? e.message : 'Route information is unavailable.',
      });
    }
  };

  return (
    <Card>
      <h2 className="mb-3 font-semibold">Travel estimate</h2>
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor={`${id}-zip`} className="mb-1 block text-sm">
            Starting ZIP code
          </label>
          <input
            id={`${id}-zip`}
            inputMode="numeric"
            maxLength={5}
            value={zip}
            onChange={(e) => setZip(e.target.value.replace(/\D/g, ''))}
            className="min-h-11 w-32 rounded-xl border border-line bg-surface px-3 text-sm"
          />
        </div>
        <div>
          <label htmlFor={`${id}-mode`} className="mb-1 block text-sm">
            Travel by
          </label>
          <select
            id={`${id}-mode`}
            value={mode}
            onChange={(e) => setMode(e.target.value as 'Car' | 'Pedestrian')}
            className="min-h-11 rounded-xl border border-line bg-surface px-3 text-sm"
          >
            <option value="Car">Car</option>
            <option value="Pedestrian">Walking</option>
          </select>
        </div>
        <Button variant="secondary" disabled={!valid || state.status === 'loading'} onClick={run}>
          <Navigation size={16} aria-hidden />{' '}
          {state.status === 'loading' ? 'Calculating…' : 'Get travel estimate'}
        </Button>
      </div>
      <div role="status" className="mt-3 text-sm">
        {state.status === 'done' && state.route && (
          <p>
            About {state.route.distanceMiles} miles, {Math.round(state.route.durationMinutes)}{' '}
            minutes by {state.route.travelMode === 'Car' ? 'car' : 'foot'} from the center of ZIP{' '}
            {zip}. Provided by {state.route.provider}.
          </p>
        )}
        {state.status === 'error' && (
          <p className="text-red-600 dark:text-red-300">{state.error}</p>
        )}
      </div>
    </Card>
  );
}
