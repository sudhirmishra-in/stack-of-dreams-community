import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { AppRoutes } from '../app/router';
import { PROJECTS } from '../data/projects';
import { DEFAULT_BRANDING, mergeBranding } from '../config/branding';
import { safeHttpUrl } from '../utils/url';

const renderAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  );

describe('AI for Good', () => {
  it('adds AI for Good to the main navigation', () => {
    renderAt('/');
    const link = screen.getAllByRole('link', { name: 'AI for Good' })[0];
    expect(link).toHaveAttribute('href', '/ai-for-good');
  });

  it('renders the landing page with challenge cards and the placeholder project', () => {
    renderAt('/ai-for-good/program');
    expect(screen.getByRole('heading', { level: 1, name: 'AI for Good' })).toBeInTheDocument();
    expect(
      screen.getByText('Building intelligent solutions for real-world challenges.'),
    ).toBeInTheDocument();
    for (const t of ['Education', 'Healthcare', 'Climate Resilience']) {
      expect(screen.getByRole('heading', { name: t })).toBeInTheDocument();
    }
    expect(screen.getByText(/Disaster preparedness/)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Hackathon Projects' })).toBeInTheDocument();
    expect(screen.getByText('AWS Breaking Barriers 2026')).toBeInTheDocument();
    expect(screen.getByText('Upcoming')).toBeInTheDocument();
    expect(screen.getByText(/Proposed architecture/i, { selector: 'p' })).toBeInTheDocument();
  });

  it('registry has the upcoming placeholder and no completion claims', () => {
    expect(PROJECTS[0]).toMatchObject({
      id: 'aws-breaking-barriers-2026',
      category: 'AI for Good',
      status: 'upcoming',
    });
    expect(PROJECTS.some((p) => p.status === 'completed')).toBe(false);
  });

  it('renders project detail with placeholders for missing info', () => {
    renderAt('/ai-for-good/projects/aws-breaking-barriers-2026');
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'AWS Breaking Barriers 2026',
    );
    for (const h of [
      'Project overview',
      'Problem statement',
      'Proposed solution',
      'Technology stack',
      'Architecture',
      'Team',
    ]) {
      expect(screen.getByRole('heading', { name: h })).toBeInTheDocument();
    }
    expect(screen.getByText('Demo: not available yet')).toBeInTheDocument();
    expect(screen.getByText('GitHub: not available yet')).toBeInTheDocument();
    expect(screen.getByText('Team information to be announced.')).toBeInTheDocument();
  });

  it('shows a not-found state for unknown projects', () => {
    renderAt('/ai-for-good/projects/nope');
    expect(screen.getByText('Project not found')).toBeInTheDocument();
  });

  it('reserves the application route with an honest placeholder', () => {
    renderAt('/ai-for-good/projects/aws-breaking-barriers-2026/app');
    expect(
      screen.getByText('Application development begins when the hackathon challenge is defined.'),
    ).toBeInTheDocument();
  });
});

describe('branding configuration', () => {
  it('merges overrides without losing defaults', () => {
    const b = mergeBranding(DEFAULT_BRANDING, {
      name: 'Climate Helper',
      theme: { accent: '#0a7' },
      nav: [{ to: '/', label: 'Start' }],
    });
    expect(b.name).toBe('Climate Helper');
    expect(b.theme.accent).toBe('#0a7');
    expect(b.agents).toBe(DEFAULT_BRANDING.agents);
    expect(b.footer.linkUrl).toBe(DEFAULT_BRANDING.footer.linkUrl);
  });

  it('only allows http(s) links from registry data', () => {
    expect(safeHttpUrl('https://github.com/x/y')).toBe('https://github.com/x/y');
    expect(safeHttpUrl('javascript:alert(1)')).toBeUndefined();
    expect(safeHttpUrl(undefined)).toBeUndefined();
    expect(safeHttpUrl('not a url')).toBeUndefined();
  });
});
