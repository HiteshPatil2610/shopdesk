import { useApi, type PosProduct } from '@shopdesk/shared';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import type { Cart } from './cart';

export type QuoteLine = {
  code: string;
  name: string | null;
  thumb_url: string | null;
  qty: number;
  available: number;
  unit_mp: string;
  unit_sp: string;
  unit_price: string;
  line_total: string;
  status: 'ok' | 'not_found' | 'inactive' | 'insufficient_stock';
};
export type Quote = {
  discount_applied: boolean;
  lines: QuoteLine[];
  item_count: number;
  subtotal_mp: string;
  discount_amount: string;
  total: string;
  can_confirm: boolean;
};

export function useLookup() {
  const api = useApi();
  return useMutation({
    mutationFn: async (code: string) =>
      (await api.get<{ product: PosProduct }>('/api/products/lookup', { params: { code } })).data
        .product,
  });
}

export function useQuote(cart: Cart) {
  const api = useApi();
  const signature = JSON.stringify({
    items: cart.items.map(({ code, qty }) => ({ code, qty })),
    discount_applied: cart.discount,
  });
  const [debounced, setDebounced] = useState(signature);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(signature), 150);
    return () => window.clearTimeout(timer);
  }, [signature]);
  const query = useQuery({
    queryKey: ['cart-quote', signature],
    enabled: signature === debounced,
    queryFn: async ({ signal }) =>
      (await api.post<Quote>('/api/cart/quote', JSON.parse(signature), { signal })).data,
    staleTime: 0,
    gcTime: 0,
    retry: false,
  });
  return query;
}
