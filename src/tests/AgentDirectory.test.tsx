import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { AgentDirectory } from '../components/agents/AgentDirectory';

describe('AgentDirectory', () => {
  it('renders the three agents with honest statuses', () => {
    render(
      <MemoryRouter>
        <AgentDirectory />
      </MemoryRouter>,
    );
    expect(screen.getByText('AI Assistant')).toBeInTheDocument();
    expect(screen.getByText('Research Agent')).toBeInTheDocument();
    expect(screen.getByText('Multi-Agent Orchestrator')).toBeInTheDocument();
    expect(screen.getByText('Demo available')).toBeInTheDocument();
    expect(screen.getAllByText('Coming soon')).toHaveLength(2);
  });

  it('only the AI Assistant is interactive', () => {
    render(
      <MemoryRouter>
        <AgentDirectory />
      </MemoryRouter>,
    );
    expect(screen.getByRole('link', { name: 'Try the demo' })).toHaveAttribute(
      'href',
      '/chat/assistant',
    );
    expect(screen.getAllByRole('button', { name: 'Not available yet' })).toHaveLength(2);
  });
});
