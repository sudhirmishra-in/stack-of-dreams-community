import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { AppRoutes } from '../app/router';
import { AGENTS } from '../data/agents';
import { DEFAULT_BRANDING } from '../config/branding';
import { AI_FOR_GOOD_STARTER_PROMPTS } from '../features/aiForGood/utils/prompts';

describe('Community Navigator starter prompts', () => {
  it('only suggest questions the real directory data can answer', () => {
    expect(AI_FOR_GOOD_STARTER_PROMPTS).toEqual([
      'Find food pantries near ZIP 10027 in Manhattan.',
      'Which food banks are closest to ZIP 11201 in Brooklyn?',
      'Does the Community Kitchen and Pantry on West 116th Street have food today?',
      'How much food assistance activity has NYC reported recently?',
    ]);
    // Real providers have no inventory or capacity figures, so prompts must not ask for them as facts.
    const text = AI_FOR_GOOD_STARTER_PROMPTS.join(' ').toLowerCase();
    expect(text).not.toMatch(/baby formula|highest weekly capacity|compare the available/);
  });
});

describe('the general AI Assistant is left as it was', () => {
  it('keeps its description and the Launch Assistant button still opens it', () => {
    const general = AGENTS.find((a) => a.id === 'assistant');
    expect(general?.description).toBe(
      'General-purpose AI assistant powered by Amazon Bedrock AgentCore.',
    );
    expect(DEFAULT_BRANDING.primaryAction).toEqual({ label: 'Launch Assistant', to: '/chat' });
  });
});

describe('AI for Good Assistant agent', () => {
  const agent = AGENTS.find((a) => a.id === 'ai-for-good');

  it('is a separate, honestly labelled agent focused on the community use case', () => {
    expect(agent?.name).toBe('AI for Good Assistant');
    expect(agent?.interactive).toBe(true);
    expect(agent?.statusLabel).toBe('Pilot (invite-only)');
    expect(agent?.route).toBe('/ai-for-good/assistant');
    expect(agent?.description).toMatch(/food assistance/i);
  });

  it('never opens the general chat service: /chat/ai-for-good redirects to its own assistant page', async () => {
    render(
      <MemoryRouter initialEntries={['/chat/ai-for-good']}>
        <AppRoutes />
      </MemoryRouter>,
    );
    // The Community Navigator page shows its own starter prompts, not the general ones.
    expect(
      await screen.findByRole('button', { name: AI_FOR_GOOD_STARTER_PROMPTS[0] }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'What is agentic AI?' })).toBeNull();
  });
});
