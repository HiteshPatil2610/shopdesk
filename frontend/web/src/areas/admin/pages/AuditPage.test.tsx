import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router';

import { AuditPage } from './AuditPage';

const mocks = vi.hoisted(() => ({ role: 'manager', query: vi.fn(), download: vi.fn() }));
vi.mock('@shopdesk/shared', async (original) => ({
  ...(await original<typeof import('@shopdesk/shared')>()),
  useMe: () => ({ user: { role: mocks.role } }),
}));
vi.mock('../features/audit/api', () => ({
  useAudit: mocks.query,
  useExportAudit: () => ({ mutate: mocks.download }),
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

it('scopes product history and shows field changes without manager export access', () => {
  mocks.role = 'manager';
  mocks.query.mockReturnValue({
    data: {
      total: 1,
      page: 1,
      page_size: 25,
      items: [
        {
          id: 1,
          occurred_at: '2026-10-04T12:00:00Z',
          actor_username: 'owner',
          source: 'admin',
          action: 'product.update',
          entity_type: 'product',
          entity_id: '42',
          summary: 'Updated bottle',
          changes: { market_price: ['300.00', '320.00'] },
        },
      ],
    },
  });
  render(
    <MemoryRouter>
      <AuditPage productId={42} />
    </MemoryRouter>,
  );
  expect(mocks.query).toHaveBeenCalledWith(
    expect.objectContaining({ entity_type: 'product', entity_id: '42' }),
  );
  expect(screen.queryByRole('button', { name: 'Export CSV' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'View details' }));
  expect(screen.getByText('"300.00"')).toBeTruthy();
  expect(screen.getByText('"320.00"')).toBeTruthy();
});

it('exports the active URL filters for an admin and displays empty results', () => {
  mocks.role = 'admin';
  mocks.query.mockReturnValue({ data: { total: 0, page: 1, page_size: 25, items: [] } });
  render(
    <MemoryRouter initialEntries={['/audit?action=user.']}>
      <AuditPage />
    </MemoryRouter>,
  );
  expect(screen.getByText('No audit entries match these filters.')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Export CSV' }));
  expect(mocks.download).toHaveBeenCalledWith({ action: 'user.' });
});

it('converts IST date filters to UTC regardless of the browser timezone', () => {
  mocks.role = 'admin';
  mocks.query.mockReturnValue({ data: { total: 0, page: 1, page_size: 25, items: [] } });
  render(
    <MemoryRouter initialEntries={['/audit?from=2026-10-04T12:00:00Z']}>
      <AuditPage />
    </MemoryRouter>,
  );
  const input = screen.getByLabelText('From (IST)') as HTMLInputElement;
  expect(input.value).toBe('2026-10-04T17:30');
  fireEvent.change(input, { target: { value: '2026-10-04T18:00' } });
  expect(mocks.query).toHaveBeenLastCalledWith({ from: '2026-10-04T12:30:00.000Z' });
});
