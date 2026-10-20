import type { ResourceService } from '../features/aiForGood/types/resource';
import { httpResourceService } from './httpResourceService';
import { mockResourceService } from './mockResourceService';

export { ResourceServiceError } from './resourceErrors';

export function isMockResources(): boolean {
  // Mock is the default; only an explicit "false" switches to the HTTP API.
  return String(import.meta.env.VITE_USE_MOCK_RESOURCES ?? 'true').toLowerCase() !== 'false';
}

export const createResourceService = (): ResourceService =>
  isMockResources() ? mockResourceService : httpResourceService;

export const resourceService: ResourceService = createResourceService();
