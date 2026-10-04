import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BillingPage } from './BillingPage';
const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock('@shopdesk/shared', async (original) => ({
  ...(await original<typeof import('@shopdesk/shared')>()),
  useApi: () => mocks,
}));
vi.mock('../features/products/ProductPanel', () => ({
  ProductPanel: () => <aside>Products</aside>,
}));
afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.clearAllMocks();
});
it('looks up products, switches server quotes and keeps customer and cart on refresh', async () => {
  mocks.get.mockResolvedValue({
    data: { product: { code: 'P00042', name: 'Bottle', quantity: 14 } },
  });
  mocks.post.mockImplementation(async (_url, body) => ({
    data: {
      discount_applied: body.discount_applied,
      lines: body.items.map((item: { code: string; qty: number }) => ({
        ...item,
        name: 'Bottle',
        available: 14,
        unit_mp: '300.00',
        unit_sp: '265.00',
        unit_price: body.discount_applied ? '265.00' : '300.00',
        line_total: body.discount_applied ? '530.00' : '600.00',
        status: 'ok',
      })),
      total: body.discount_applied ? '530.00' : '600.00',
      subtotal_mp: '600.00',
      discount_amount: body.discount_applied ? '70.00' : '0.00',
      item_count: 2,
      can_confirm: body.items.length > 0,
    },
  }));
  const renderBill = () =>
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <BillingPage />
      </QueryClientProvider>,
    );
  const view = renderBill();
  expect((screen.getByRole('button', { name: /Review bill/ }) as HTMLButtonElement).disabled).toBe(
    true,
  );
  fireEvent.change(screen.getByLabelText(/Customer name/), { target: { value: 'Test Buyer' } });
  fireEvent.change(screen.getByLabelText(/Product code/), { target: { value: 'P00042' } });
  fireEvent.change(screen.getByLabelText('Qty'), { target: { value: '2' } });
  fireEvent.click(screen.getByRole('button', { name: 'Add item' }));
  await waitFor(() =>
    expect(
      (screen.getByRole('button', { name: /Review bill/ }) as HTMLButtonElement).disabled,
    ).toBe(false),
  );
  fireEvent.click(screen.getByLabelText(/Apply Discount/));
  expect((screen.getByRole('button', { name: /Review bill/ }) as HTMLButtonElement).disabled).toBe(
    true,
  );
  await waitFor(() => expect(screen.getByText(/You save/).textContent).toContain('70'));
  expect(mocks.post).toHaveBeenLastCalledWith(
    '/api/cart/quote',
    { discount_applied: true, items: [{ code: 'P00042', qty: 2 }] },
    expect.objectContaining({ signal: expect.any(AbortSignal) }),
  );
  view.unmount();
  renderBill();
  expect((screen.getByLabelText(/Customer name/) as HTMLInputElement).value).toBe('Test Buyer');
  expect((screen.getByLabelText('Quantity for P00042') as HTMLInputElement).value).toBe('2');
});

it('keeps the cart unchanged for unknown codes and excess stock', async () => {
  mocks.post.mockResolvedValue({
    data: {
      lines: [],
      can_confirm: false,
      item_count: 0,
      subtotal_mp: '0.00',
      discount_amount: '0.00',
      total: '0.00',
    },
  });
  mocks.get
    .mockRejectedValueOnce(new Error('Unknown product'))
    .mockResolvedValue({ data: { product: { code: 'P00042', name: 'Bottle', quantity: 14 } } });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <BillingPage />
    </QueryClientProvider>,
  );
  fireEvent.change(screen.getByLabelText(/Product code/), { target: { value: 'UNKNOWN' } });
  fireEvent.click(screen.getByRole('button', { name: 'Add item' }));
  await screen.findByRole('alert');
  expect(screen.queryByLabelText('Quantity for P00042')).toBeNull();
  fireEvent.change(screen.getByLabelText(/Product code/), { target: { value: 'P00042' } });
  fireEvent.change(screen.getByLabelText('Qty'), { target: { value: '20' } });
  fireEvent.click(screen.getByRole('button', { name: 'Add item' }));
  await screen.findByText(/Only 14 available/);
  expect(screen.queryByLabelText('Quantity for P00042')).toBeNull();
});
