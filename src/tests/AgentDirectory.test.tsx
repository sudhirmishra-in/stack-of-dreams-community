import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { AgentDirectory } from '../components/agents/AgentDirectory';

describe('AgentDirectory', () => {
  it('renders the agents with honest statuses', () => {
    render(
      <MemoryRouter>
        <AgentDirectory />
      </MemoryRouter>,
    );
    expect(screen.getByText('AI Assistant')).toBeInTheDocument();
    expect(screen.getByText('AI for Good Assistant')).toBeInTheDocument();
    expect(screen.getByText('Research Agent')).toBeInTheDocument();
    expect(screen.getByText('Multi-Agent Orchestrator')).toBeInTheDocument();
    expect(screen.getByText('Demo available')).toBeInTheDocument();
    expect(screen.getByText('Pilot (invite-only)')).toBeInTheDocument();
    expect(screen.getAllByText('Coming soon')).toHaveLength(2);
  });

  it('the general AI Assistant is unchanged and the AI for Good Assistant is a separate agent', () => {
    render(
      <MemoryRouter>
        <AgentDirectory />
      </MemoryRouter>,
    );
    expect(screen.getByRole('link', { name: 'Try the demo' })).toHaveAttribute(
      'href',
      '/chat/assistant',
    );
    expect(screen.getByRole('link', { name: 'Open the AI for Good assistant' })).toHaveAttribute(
      'href',
      '/ai-for-good/assistant',
    );
    expect(screen.getAllByRole('button', { name: 'Not available yet' })).toHaveLength(2);
  });
});
