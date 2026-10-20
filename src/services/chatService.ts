import { httpChatService } from './httpChatService';
import { mockChatService } from './mockChatService';
import type { ChatService } from './errors';

export { ChatServiceError, type ChatService } from './errors';

export function isMockMode(): boolean {
  // Mock is the default; it is only disabled by an explicit "false".
  return String(import.meta.env.VITE_USE_MOCK_API ?? 'true').toLowerCase() !== 'false';
}

export function createChatService(): ChatService {
  return isMockMode() ? mockChatService : httpChatService;
}

export const chatService: ChatService = createChatService();
