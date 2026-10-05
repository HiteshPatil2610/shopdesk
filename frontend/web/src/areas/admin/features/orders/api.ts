import { useApi, type Page, type Product } from '@shopdesk/shared';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

export type AdminOrderLine = {
  product_id: number;
  code: string;
  name: string;
  qty: number;
  unit_cost: string;
  unit_mp: string;
  unit_sp: string;
  unit_price: string;
  line_total: string;
  profit: string;
};

export type AdminOrder = {
  id: number;
  order_number: string;
  status: 'confirmed' | 'rejected';
  customer_name: string;
  customer_phone: string | null;
  cashier_id: number;
  cashier_name: string | null;
  created_at: string;
  discount_applied: boolean;
  payment_mode: 'cash' | 'upi' | 'card' | null;
  item_count: number;
  subtotal_mp: string;
  discount_amount: string;
  total: string;
  total_cost: string;
  profit: string | null;
  reject_reason: string | null;
  lines?: AdminOrderLine[];
};

export type OrderQuery = { status?: string; q?: string; page?: number; page_size?: number };

export function useOrders(query: OrderQuery) {
  const api = useApi();
  return useQuery({
    queryKey: ['orders', query],
    placeholderData: keepPreviousData,
    queryFn: async () =>
      (
        await api.get<Page<AdminOrder>>('/orders', {
          params: Object.fromEntries(Object.entries(query).filter(([, v]) => v)),
        })
      ).data,
  });
}

export function useOrder(id: number) {
  const api = useApi();
  return useQuery({
    queryKey: ['orders', 'detail', id],
    queryFn: async () => (await api.get<{ order: AdminOrder }>(`/orders/${id}`)).data.order,
  });
}

// --- stock -----------------------------------------------------------------------------

export type StockMovement = {
  id: number;
  change: number;
  quantity_after: number;
  reason: string;
  reference_type: string | null;
  reference_id: number | null;
  note: string | null;
  created_at: string;
};

export type AdjustInput = {
  type: 'restock' | 'damage' | 'correction';
  qty: number;
  note?: string;
};

export function useStockMovements(productId: number, enabled = true) {
  const api = useApi();
  return useQuery({
    queryKey: ['stock-movements', productId],
    enabled,
    queryFn: async () =>
      (
        await api.get<Page<StockMovement>>(`/stock/${productId}/movements`, {
          params: { page_size: 50 },
        })
      ).data,
  });
}

export function useAdjustStock(productId: number) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: AdjustInput) =>
      (await api.post<{ product: Product }>(`/stock/${productId}/adjust`, input)).data.product,
    onSuccess: (product) => {
      qc.setQueryData(['products', 'detail', product.id], product);
      void qc.invalidateQueries({ queryKey: ['products', 'list'] });
      void qc.invalidateQueries({ queryKey: ['stock-movements', product.id] });
    },
  });
}
