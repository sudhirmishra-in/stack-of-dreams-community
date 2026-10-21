import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { AppRoutes } from '../app/router';

function at(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe('public legal pages', () => {
  it('serves the privacy policy without signing in', async () => {
    at('/privacy');
    expect(await screen.findByRole('heading', { name: 'Privacy Policy' })).toBeInTheDocument();
    expect(screen.getByText(/Amazon Cognito/)).toBeInTheDocument();
  });

  it('serves the terms of service without signing in', async () => {
    at('/terms');
    expect(await screen.findByRole('heading', { name: 'Terms of Service' })).toBeInTheDocument();
    expect(screen.getByText(/Invitation-only pilot/)).toBeInTheDocument();
  });

  it('links both pages from the footer on every page', async () => {
    at('/about');
    const nav = await screen.findByRole('navigation', { name: 'Legal' });
    expect(nav.querySelector('a[href="/privacy"]')).not.toBeNull();
    expect(nav.querySelector('a[href="/terms"]')).not.toBeNull();
  });
});
