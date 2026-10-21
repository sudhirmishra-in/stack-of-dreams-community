import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';

const sendMessage = vi.fn();
vi.mock('../services/chatService', () => ({
  chatService: { isMock: true, sendMessage: (...a: unknown[]) => sendMessage(...a) },
}));
vi.mock('../services/resourceService', async () => {
  const actual = await vi.importActual<typeof import('../services/mockResourceService')>(
    '../services/mockResourceService',
  );
  return { resourceService: actual.createMockResourceService(0) };
});

import { AppRoutes } from '../app/router';
import { AI_FOR_GOOD_STARTER_PROMPTS } from '../features/aiForGood/utils/prompts';

const renderAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  );

beforeEach(() => {
  sendMessage.mockReset();
  sendMessage.mockImplementation(async (r) => ({
    response: 'ok',
    sessionId: r.sessionId,
    agentId: r.agentId,
  }));
});

describe('landing page', () => {
  it('renders hero, four category cards, steps and the demo notice', () => {
    renderAt('/ai-for-good');
    expect(
      screen.getByRole('heading', { level: 1, name: 'Find the Help You Need' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Find Assistance/ })).toHaveAttribute(
      'href',
      '/ai-for-good/find',
    );
    expect(screen.getByRole('link', { name: 'Explore AI Assistant' })).toHaveAttribute(
      'href',
      '/ai-for-good/assistant',
    );
    for (const t of ['Baby Formula', 'Groceries', 'Diapers', 'Food Banks']) {
      expect(screen.getByRole('heading', { name: t })).toBeInTheDocument();
    }
    expect(screen.getByText('Tell us what you need.')).toBeInTheDocument();
    expect(screen.getByText('Connect with a provider.')).toBeInTheDocument();
    expect(screen.getByRole('note')).toHaveTextContent('Resource availability must be verified');
  });

  it('category cards preselect the resource type in the search form', async () => {
    const user = userEvent.setup();
    renderAt('/ai-for-good');
    await user.click(screen.getByRole('link', { name: 'Find formula: Baby Formula' }));
    expect(screen.getByRole('radio', { name: 'Baby Formula' })).toBeChecked();
    expect(screen.getByLabelText('Formula type')).toBeInTheDocument();
  });
});

describe('guided search', () => {
  it('shows formula type only for baby formula, and picks categories', async () => {
    const user = userEvent.setup();
    renderAt('/ai-for-good/find');
    expect(screen.queryByLabelText('Formula type')).toBeNull();
    await user.click(screen.getByRole('radio', { name: 'Baby Formula' }));
    expect(screen.getByLabelText('Formula type')).toBeInTheDocument();
    await user.click(screen.getByRole('radio', { name: 'Groceries' }));
    expect(screen.queryByLabelText('Formula type')).toBeNull();
  });

  it('shows accessible validation messages and does not search', async () => {
    const user = userEvent.setup();
    renderAt('/ai-for-good/find');
    await user.type(screen.getByLabelText('ZIP code'), '123');
    await user.click(screen.getByRole('button', { name: 'Find Resources' }));
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('Choose the type of help you need.');
    expect(alert).toHaveTextContent('5-digit ZIP');
    expect(screen.getByLabelText('ZIP code')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.queryByRole('heading', { name: /Near/ })).toBeNull();
  });

  it('submits to results with criteria in the URL (no notes)', async () => {
    const user = userEvent.setup();
    renderAt('/ai-for-good/find');
    await user.click(screen.getByRole('radio', { name: 'Baby Formula' }));
    await user.type(screen.getByLabelText('ZIP code'), '10027');
    await user.type(screen.getByLabelText(/Additional notes/), 'secret note');
    await user.click(screen.getByRole('button', { name: 'Find Resources' }));
    expect(
      await screen.findByRole('heading', { name: 'Baby Formula Near 10027' }),
    ).toBeInTheDocument();
  });
});

describe('results', () => {
  it('renders demo cards without invented contact actions', async () => {
    renderAt('/ai-for-good/results?type=baby_formula&zip=10027');
    expect(await screen.findByText('Riverside Food Share')).toBeInTheDocument();
    expect(screen.getByRole('status', { name: '' })).toHaveTextContent('3 matching resources');
    expect(screen.getAllByText('Demo data').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Not available').length).toBeGreaterThan(0); // last updated
    expect(screen.queryByText(/Call provider/)).toBeNull();
    expect(screen.queryByText(/Directions/)).toBeNull();
    expect(screen.queryByText('Verified')).toBeNull();
  });

  it('filters by availability', async () => {
    const user = userEvent.setup();
    renderAt('/ai-for-good/results?type=baby_formula&zip=10027');
    await screen.findByText('Riverside Food Share');
    await user.click(screen.getByRole('button', { name: 'Low stock' }));
    expect(screen.getByText('Queens Neighbors Kitchen')).toBeInTheDocument();
    expect(screen.queryByText('Riverside Food Share')).toBeNull();
  });

  it('shows an empty state', async () => {
    renderAt('/ai-for-good/results?type=diapers&zip=10027');
    expect(await screen.findByText('No matching resources')).toBeInTheDocument();
  });

  it('shows an error state with retry', async () => {
    renderAt('/ai-for-good/results?type=baby_formula&zip=00000');
    expect(await screen.findByRole('alert')).toHaveTextContent("couldn't load resources");
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
  });

  it('redirects invalid criteria back to the form', () => {
    renderAt('/ai-for-good/results?type=nope&zip=1');
    expect(screen.getByRole('heading', { name: 'Find resources' })).toBeInTheDocument();
  });

  it('navigates to resource details', async () => {
    const user = userEvent.setup();
    renderAt('/ai-for-good/results?type=baby_formula&zip=10027');
    await screen.findByText('Riverside Food Share');
    await user.click(screen.getByRole('link', { name: /View details for Riverside Food Share/ }));
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Riverside Food Share' }),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Contact the organization to confirm availability before traveling.'),
    ).toBeInTheDocument();
    expect(screen.getAllByText('Contact provider to confirm').length).toBeGreaterThan(0); // address, phone, hours
  });
});

describe('details and assistant handoff', () => {
  it('shows not found for unknown resources', async () => {
    renderAt('/ai-for-good/resources/nope');
    expect(await screen.findByText('Resource not found')).toBeInTheDocument();
  });

  it('"Ask AI About This Resource" sends a guarded, context-rich prompt through the existing chat service', async () => {
    const user = userEvent.setup();
    renderAt('/ai-for-good/resources/fb-002');
    await user.click(await screen.findByRole('button', { name: 'Ask AI About This Resource' }));
    await screen.findByText('ok');
    expect(sendMessage).toHaveBeenCalledTimes(1);
    const req = sendMessage.mock.calls[0][0];
    expect(req.agentId).toBe('assistant');
    expect(req.message).toContain('Riverside Food Share');
    expect(req.message).toMatch(/Do not invent/);
    expect(req.message).toMatch(/DEMO DATA/);
  });

  it('assistant route keeps the standard chat working with AI for Good prompts', async () => {
    const user = userEvent.setup();
    renderAt('/ai-for-good/assistant');
    for (const prompt of AI_FOR_GOOD_STARTER_PROMPTS) {
      expect(screen.getByRole('button', { name: prompt })).toBeInTheDocument();
    }
    expect(
      screen.getByText(/AI-generated suggestions, not verified inventory/),
    ).toBeInTheDocument();
    await user.type(screen.getByLabelText('Message'), 'hello{Enter}');
    expect(await screen.findByText('ok')).toBeInTheDocument();
    expect(sendMessage.mock.calls[0][0]).toMatchObject({ message: 'hello', agentId: 'assistant' });
  });

  it('the original /chat route still uses the original starter prompts', () => {
    renderAt('/chat');
    expect(screen.getByRole('button', { name: 'What is agentic AI?' })).toBeInTheDocument();
  });
});

describe('dashboard and volunteer', () => {
  it('renders read-only KPIs, table, shortages and clearly-labelled recommendations', async () => {
    renderAt('/ai-for-good/dashboard');
    expect(await screen.findByText('Participating Food Banks')).toBeInTheDocument();
    const kpis = screen.getByText('Organizations With Low Inventory').closest('div')!;
    expect(within(kpis).getByText('3')).toBeInTheDocument();
    const table = screen.getByRole('table');
    expect(within(table).getAllByRole('row')).toHaveLength(6);
    expect(screen.getByText('Demo dashboard using synthetic inventory data.')).toBeInTheDocument();
    expect(screen.getByText(/not the output of an AI agent/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /transfer|update|edit/i })).toBeNull();
  });

  it('volunteer page is a placeholder with no inventory controls', () => {
    renderAt('/ai-for-good/volunteer');
    expect(screen.getByRole('heading', { name: 'Volunteer tools' })).toBeInTheDocument();
    expect(screen.queryByRole('textbox')).toBeNull();
  });
});
