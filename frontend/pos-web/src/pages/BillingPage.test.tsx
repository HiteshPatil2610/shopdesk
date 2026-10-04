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
  expect((screen.getByRole('button', { name: /✓ Confirm/ }) as HTMLButtonElement).disabled).toBe(
    true,
  );
  fireEvent.change(screen.getByLabelText(/Customer name/), { target: { value: 'Test Buyer' } });
  fireEvent.change(screen.getByLabelText(/Product code/), { target: { value: 'P00042' } });
  fireEvent.change(screen.getByLabelText('Qty'), { target: { value: '2' } });
  fireEvent.click(screen.getByRole('button', { name: 'Add item' }));
  await waitFor(() =>
    expect((screen.getByRole('button', { name: /✓ Confirm/ }) as HTMLButtonElement).disabled).toBe(
      false,
    ),
  );
  fireEvent.click(screen.getByLabelText(/Apply Discount/));
  expect((screen.getByRole('button', { name: /✓ Confirm/ }) as HTMLButtonElement).disabled).toBe(
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

function quoteFor(body: { discount_applied: boolean; items: { code: string; qty: number }[] }) {
  return {
    discount_applied: body.discount_applied,
    lines: body.items.map((item) => ({
      ...item,
      name: 'Bottle',
      thumb_url: null,
      available: 14,
      unit_mp: '300.00',
      unit_sp: '265.00',
      unit_price: '300.00',
      line_total: '300.00',
      status: 'ok',
    })),
    total: '300.00',
    subtotal_mp: '300.00',
    discount_amount: '0.00',
    item_count: 1,
    can_confirm: body.items.length > 0,
  };
}

async function billWithOneBottle() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <BillingPage />
    </QueryClientProvider>,
  );
  fireEvent.change(screen.getByLabelText(/Customer name/), { target: { value: 'Amit Kumar' } });
  fireEvent.change(screen.getByLabelText(/Product code/), { target: { value: 'P00042' } });
  fireEvent.click(screen.getByRole('button', { name: 'Add item' }));
  await screen.findByText('P00042', { selector: 'span' });
  const confirm = screen.getByRole('button', { name: /✓ Confirm/ }) as HTMLButtonElement;
  await waitFor(() => expect(confirm.disabled).toBe(false));
  return confirm;
}

it('confirms an order, shows the receipt and starts a fresh bill', async () => {
  mocks.get.mockImplementation(async (url: string) =>
    url.includes('/receipt')
      ? {
          data: {
            shop: { name: 'Saree', address: '', phone: '', gstin: '', footer: 'Thanks' },
            order: {
              order_number: 'INV-20261005-0001',
              status: 'confirmed',
              customer_name: 'Amit Kumar',
              customer_phone: null,
              cashier_name: 'deepa',
              created_at: '2026-10-05T06:00:00Z',
              discount_applied: false,
              payment_mode: 'upi',
              item_count: 1,
              subtotal_mp: '300.00',
              discount_amount: '0.00',
              total: '300.00',
              lines: [
                {
                  code: 'P00042',
                  name: 'Bottle',
                  qty: 1,
                  unit_price: '300.00',
                  line_total: '300.00',
                },
              ],
            },
          },
        }
      : { data: { product: { code: 'P00042', name: 'Bottle', quantity: 14 } } },
  );
  mocks.post.mockImplementation(async (url: string, body) =>
    url.endsWith('/confirm')
      ? { data: { order: { order_number: 'INV-20261005-0001' } } }
      : { data: quoteFor(body) },
  );
  fireEvent.click(await billWithOneBottle());
  fireEvent.click(await screen.findByText('UPI'));
  fireEvent.click(screen.getByRole('button', { name: /Confirm ₹300.00/ }));
  await screen.findByText(/Order INV-20261005-0001 confirmed/);
  const call = mocks.post.mock.calls.find(([url]) => String(url).endsWith('/confirm'));
  expect(call?.[1]).toMatchObject({
    customer_name: 'Amit Kumar',
    payment_mode: 'upi',
    items: [{ code: 'P00042', qty: 1 }],
  });
  expect(call?.[1]).not.toHaveProperty('total');
  expect(call?.[1].idempotency_key).toMatch(/^[0-9a-f-]{36}$/);
  expect(await screen.findByText('Saree')).toBeDefined();
  expect(screen.queryByText('P00042', { selector: 'span' })).toBeNull(); // bill cleared
});

it('marks lines when another counter sold the stock first', async () => {
  mocks.get.mockResolvedValue({
    data: { product: { code: 'P00042', name: 'Bottle', quantity: 14 } },
  });
  mocks.post.mockImplementation(async (url: string, body) => {
    if (url.endsWith('/confirm')) {
      throw Object.assign(new Error('409'), {
        isAxiosError: true,
        response: {
          status: 409,
          data: {
            error: {
              code: 'INSUFFICIENT_STOCK',
              message: 'Not enough stock',
              details: [{ code: 'P00042', requested: 1, available: 0 }],
            },
          },
        },
      });
    }
    return { data: quoteFor(body) };
  });
  fireEvent.click(await billWithOneBottle());
  fireEvent.click(await screen.findByRole('button', { name: /Confirm ₹300.00/ }));
  expect(await screen.findByText('Only 0 available now')).toBeDefined();
  expect(screen.getByText('P00042', { selector: 'span' })).toBeDefined(); // bill kept
});

it('rejects a bill without confirming it', async () => {
  mocks.get.mockResolvedValue({
    data: { product: { code: 'P00042', name: 'Bottle', quantity: 14 } },
  });
  mocks.post.mockImplementation(async (url: string, body) =>
    url.endsWith('/reject')
      ? { data: { order: { order_number: 'REJ-20261005-0001' } } }
      : { data: quoteFor(body) },
  );
  await billWithOneBottle();
  fireEvent.click(screen.getByRole('button', { name: /✕ Reject/ }));
  fireEvent.change(await screen.findByPlaceholderText(/changed mind/), {
    target: { value: 'No cash' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Reject bill' }));
  expect(await screen.findByText(/REJ-20261005-0001/)).toBeDefined();
  const call = mocks.post.mock.calls.find(([url]) => String(url).endsWith('/reject'));
  expect(call?.[1]).toMatchObject({ reason: 'No cash', customer_name: 'Amit Kumar' });
});
