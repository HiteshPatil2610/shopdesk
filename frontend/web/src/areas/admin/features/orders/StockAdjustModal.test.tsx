// @vitest-environment jsdom
import type { Product } from '@shopdesk/shared';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import { StockAdjustModal } from './StockAdjustModal';

const post = vi.fn();
vi.mock('@shopdesk/shared', async (original) => ({
  ...(await original<typeof import('@shopdesk/shared')>()),
  useApi: () => ({ post }),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const product = {
  id: 7,
  code: 'P00007',
  name: 'Steel bottle',
  quantity: 4,
  unit: 'pcs',
} as Product;

function renderModal(onClose = vi.fn()) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <StockAdjustModal product={product} onClose={onClose} />
    </QueryClientProvider>,
  );
  return onClose;
}

const save = () => screen.getByRole('button', { name: 'Save adjustment' }) as HTMLButtonElement;

it('previews the new stock and sends a restock', async () => {
  post.mockResolvedValue({ data: { product: { ...product, quantity: 6 } } });
  const onClose = renderModal();
  fireEvent.change(screen.getByLabelText('Quantity'), { target: { value: '2' } });
  expect(screen.getByText('6')).toBeDefined();
  fireEvent.click(save());
  await waitFor(() => expect(onClose).toHaveBeenCalled());
  expect(post).toHaveBeenCalledWith('/stock/7/adjust', {
    type: 'restock',
    qty: 2,
    note: undefined,
  });
});

it('blocks going below zero and requires a note for damage', () => {
  renderModal();
  fireEvent.click(screen.getByLabelText(/Damage/));
  fireEvent.change(screen.getByLabelText('Quantity'), { target: { value: '5' } });
  expect(screen.getByText(/can't go below 0/)).toBeDefined();
  expect(save().disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('Quantity'), { target: { value: '1' } });
  expect(save().disabled).toBe(true); // note still missing
  fireEvent.change(screen.getByLabelText(/Note/), { target: { value: 'Dented' } });
  expect(save().disabled).toBe(false);
});
