import { STARTER_PROMPTS } from '../components/chat/SuggestedPrompts';
import { PilotUsageBadge } from '../features/aiForGood/components/PilotUsageBadge';
import { isPilotConfigured, researchAssistantService } from '../services/pilotAssistantService';
import type { ChatContext } from '../types/chat';

/**
 * The general AI Assistant. When the pilot API is configured it is served THROUGH that API, which enforces
 * sign-in, the pending-approval check, the kill switch and per-user daily/monthly quotas on the server. The older
 * /chat endpoint has none of those, so it is used only when the pilot API is not configured (local development)
 * or when mock mode is on.
 */
export function generalChatContext(): ChatContext | undefined {
  if (!isPilotConfigured()) return undefined;
  // Same rule as the chat service: mock mode is the default and is only turned off by an explicit "false".
  if (String(import.meta.env.VITE_USE_MOCK_API ?? 'true').toLowerCase() !== 'false')
    return undefined;
  return {
    prompts: STARTER_PROMPTS,
    service: researchAssistantService,
    conversationKey: 'assistant-research',
    notice: <PilotUsageBadge agent="research" />,
  };
}
