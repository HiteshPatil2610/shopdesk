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

// --- confirm / reject / receipts (spec 07) ----------------------------------------------

export type OrderLine = {
  code: string;
  name: string;
  qty: number;
  unit_price: string;
  line_total: string;
};

export type PosOrder = {
  id: number;
  order_number: string;
  status: 'confirmed' | 'rejected';
  customer_name: string;
  customer_phone: string | null;
  cashier_name: string | null;
  created_at: string;
  discount_applied: boolean;
  payment_mode: 'cash' | 'upi' | 'card' | null;
  item_count: number;
  subtotal_mp: string;
  discount_amount: string;
  total: string;
  reject_reason: string | null;
  lines: OrderLine[];
};

export type Receipt = {
  shop: { name: string; address: string; phone: string; gstin: string; footer: string };
  order: PosOrder;
};

export type PaymentMode = 'cash' | 'upi' | 'card';

export function useConfirmOrder() {
  const api = useApi();
  return useMutation({
    mutationFn: async (args: { cart: Cart; payment: PaymentMode }) =>
      (
        await api.post<{ order: PosOrder }>('/api/orders/confirm', {
          idempotency_key: args.cart.key,
          customer_name: args.cart.name.trim(),
          customer_phone: args.cart.phone.trim() || null,
          payment_mode: args.payment,
          discount_applied: args.cart.discount,
          items: args.cart.items.map(({ code, qty }) => ({ code, qty })),
        })
      ).data.order,
  });
}

export function useRejectOrder() {
  const api = useApi();
  return useMutation({
    mutationFn: async (args: { cart: Cart; reason: string }) =>
      (
        await api.post<{ order: PosOrder }>('/api/orders/reject', {
          idempotency_key: args.cart.key,
          customer_name: args.cart.name.trim() || null,
          discount_applied: args.cart.discount,
          items: args.cart.items.map(({ code, qty }) => ({ code, qty })),
          reason: args.reason.trim() || null,
        })
      ).data.order,
  });
}

export function useReceipt(orderNumber: string | null) {
  const api = useApi();
  return useQuery({
    queryKey: ['receipt', orderNumber],
    enabled: orderNumber !== null,
    queryFn: async () =>
      (await api.get<Receipt>(`/api/orders/${encodeURIComponent(orderNumber ?? '')}/receipt`)).data,
  });
}

export type MyOrder = {
  order_number: string;
  status: 'confirmed' | 'rejected';
  customer_name: string;
  created_at: string;
  total: string;
};

export function useMyOrders(enabled: boolean) {
  const api = useApi();
  return useQuery({
    queryKey: ['my-orders'],
    enabled,
    queryFn: async () => (await api.get<{ items: MyOrder[] }>('/api/orders/mine')).data.items,
  });
}
