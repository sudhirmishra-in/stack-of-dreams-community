import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { AppRoutes } from '../app/router';
import {
  DATA_PIPELINE,
  GUARDRAILS,
  LAYERS,
  OBSERVABILITY,
  REQUEST_FLOW,
  STATUS,
} from '../components/architecture/architectureData';

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/architecture']}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe('architecture page', () => {
  it('describes the running system, not a plan that is unconnected', () => {
    renderPage();
    expect(screen.getByRole('heading', { level: 1, name: 'Architecture' })).toBeInTheDocument();
    expect(screen.getByText(/pilot is live/i)).toBeInTheDocument();
    expect(screen.queryByText(/Target Architecture/)).toBeNull();
    expect(screen.queryByText(/none of the AWS components below are connected/i)).toBeNull();
  });

  it('shows every layer with its components', () => {
    renderPage();
    for (const layer of LAYERS) {
      const region = screen.getByRole('region', { name: layer.title });
      for (const n of layer.nodes) expect(within(region).getByText(n.name)).toBeInTheDocument();
    }
  });

  it('names the components that actually exist', () => {
    renderPage();
    for (const name of [
      'React app on AWS Amplify',
      'Amazon Cognito',
      'API Lambda',
      'Usage ledger (DynamoDB)',
      'AI for Good: community_navigator runtime',
      'General AI Assistant: research harness',
      'Amazon Bedrock models',
      'Amazon Location Service',
    ])
      expect(screen.getAllByText(name).length).toBeGreaterThan(0);
    // the original design used API Gateway; the running system uses Lambda Function URLs
    expect(screen.queryByText(/Amazon API Gateway/)).toBeNull();
  });

  it('marks what is live, legacy, planned and disabled honestly', () => {
    renderPage();
    const table = screen.getByRole('table', { name: /status/i });
    for (const row of STATUS) expect(within(table).getByText(row.item)).toBeInTheDocument();
    const statuses = new Set(STATUS.map((s) => s.status));
    expect(statuses).toEqual(new Set(['live', 'legacy', 'planned', 'disabled']));
    // anything not built yet must say so
    expect(within(table).getAllByText('Planned').length).toBe(
      STATUS.filter((s) => s.status === 'planned').length,
    );
    expect(row('CloudWatch observability dashboard and new alarms').status).toBe('planned');
  });

  it('lists the request flow as ordered steps', () => {
    renderPage();
    const list = screen.getByRole('list', { name: /how a question flows/i });
    expect(within(list).getAllByRole('listitem')).toHaveLength(REQUEST_FLOW.length);
    expect(REQUEST_FLOW.map((s) => s.title)).toEqual([
      'Sign in',
      'Ask a question',
      'Verify and gate',
      'Reserve quota',
      'Route',
      'Answer',
      'Settle and measure',
    ]);
  });

  it('explains the data pipeline, observability and guardrails', () => {
    renderPage();
    for (const p of [DATA_PIPELINE, OBSERVABILITY]) {
      const region = screen.getByRole('region', { name: p.title });
      for (const s of p.steps) expect(within(region).getByText(s.name)).toBeInTheDocument();
    }
    for (const g of GUARDRAILS) expect(screen.getByText(g.title)).toBeInTheDocument();
  });

  it('never exposes account ids, endpoints or keys', () => {
    const { container } = renderPage();
    const text = container.textContent ?? '';
    expect(text).not.toMatch(/\b\d{12}\b/);
    expect(text).not.toMatch(/lambda-url|amazoncognito\.com|us-east-\d_[A-Za-z0-9]{9}/);
    expect(text).not.toMatch(/AKIA|ASIA[A-Z0-9]{8}/);
  });
});

function row(item: string) {
  const r = STATUS.find((s) => s.item === item);
  if (!r) throw new Error('missing row ' + item);
  return r;
}
