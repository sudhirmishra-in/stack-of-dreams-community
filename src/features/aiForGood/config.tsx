import { Link } from 'react-router';
import { DemoNotice } from './components/DemoNotice';
import { PilotUsageBadge } from './components/PilotUsageBadge';
import { AI_FOR_GOOD_STARTER_PROMPTS } from './utils/prompts';
import { chatService } from '../../services/chatService';
import { isPilotConfigured, pilotAssistantService } from '../../services/pilotAssistantService';
import type { ChatService } from '../../services/errors';
import type { ChatContext } from '../../types/chat';

/**
 * Which backend answers on /ai-for-good/assistant:
 *  - pilot API configured -> the community-navigator gateway/runtime (quotas, validation, grounding)
 *  - otherwise            -> the existing chat service, and the page SAYS so (never a silent substitute).
 */
export const aiForGoodService = (): ChatService =>
  isPilotConfigured() ? pilotAssistantService : chatService;

export function buildAiForGoodChat(): ChatContext {
  const pilot = isPilotConfigured();
  return {
    prompts: AI_FOR_GOOD_STARTER_PROMPTS,
    service: aiForGoodService(),
    conversationKey: pilot ? 'ai-for-good' : 'assistant',
    notice: (
      <div className="space-y-2">
        {pilot ? <PilotUsageBadge /> : null}
        <DemoNotice>
          {pilot
            ? 'Answers are AI-generated suggestions grounded in directory data and listed with their sources and caveats. They are not verified inventory.'
            : 'The Community Navigator service is not connected, so this uses the general demo assistant. Its answers are AI-generated suggestions, not verified inventory.'}{' '}
          For structured, filterable results use{' '}
          <Link to="/ai-for-good/find" className="text-accent underline">
            Find help
          </Link>
          . Resource data in this demo is synthetic unless labeled otherwise.
        </DemoNotice>
      </div>
    ),
  };
}

/** Evaluated once at load; the build-time env decides the backend. */
export const AI_FOR_GOOD_CHAT: ChatContext = buildAiForGoodChat();
