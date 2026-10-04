import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { App } from './App';

vi.mock('./lib/api', () => ({
  fetchHealth: vi
    .fn()
    .mockResolvedValue({ status: 'ok', server: 'admin', db: 'ok', version: '0.1.0' }),
}));

describe('App', () => {
  it('shows the API OK badge when health is ok', async () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <App />
      </QueryClientProvider>,
    );
    expect(screen.getByRole('heading', { name: 'ShopDesk Admin' })).toBeDefined();
    expect(await screen.findByText(/API OK/)).toBeDefined();
  });
});
