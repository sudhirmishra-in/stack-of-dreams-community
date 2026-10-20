import { resourceService as defaultService } from '../../../services/resourceService';
import type { ResourceSearchRequest, ResourceService } from '../types/resource';
import { useAsyncData } from './useAsyncData';

export function useResourceSearch(
  request: ResourceSearchRequest,
  service: ResourceService = defaultService,
) {
  return useAsyncData(JSON.stringify(request), (signal) => service.search(request, signal));
}

export function useResource(id: string, service: ResourceService = defaultService) {
  return useAsyncData(`resource:${id}`, (signal) => service.getResource(id, signal));
}

export function useAllResources(service: ResourceService = defaultService) {
  return useAsyncData('all', (signal) => service.listResources(signal));
}
