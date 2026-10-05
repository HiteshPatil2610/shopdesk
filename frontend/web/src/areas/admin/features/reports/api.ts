import { useApi } from '@shopdesk/shared';
import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query';

const REFRESH = 60_000; // spec 08: auto-refresh every 60 s

type DayTotals = {
  date: string;
  sales_total: string;
  profit_total: string;
  discount_total: string;
  orders_confirmed: number;
  orders_rejected: number;
  items_sold: number;
  avg_order_value: string;
};

export type Summary = DayTotals & {
  low_stock_count: number;
  out_of_stock_count: number;
  previous: DayTotals;
  change_pct: Record<'sales_total' | 'profit_total' | 'orders_confirmed', string | null>;
};

export type DayPoint = { date: string; sales_total: string; profit_total: string; orders: number };
export type TopProduct = {
  product_id: number;
  code: string;
  name: string;
  qty: number;
  revenue: string;
  profit: string;
};
export type LowStockItem = {
  id: number;
  code: string;
  name: string;
  quantity: number;
  reorder_level: number;
  unit: string;
  version: number;
};
export type CashierRow = {
  cashier_id: number;
  cashier: string;
  orders: number;
  sales_total: string;
  rejected: number;
  discount_orders: number;
  discounts_given: string;
};

export type Range = { from: string; to: string };

export function useSummary(date: string) {
  const api = useApi();
  return useQuery({
    queryKey: ['reports', 'summary', date],
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH,
    queryFn: async () => (await api.get<Summary>('/reports/summary', { params: { date } })).data,
  });
}

export function useSalesByDay(range: Range) {
  const api = useApi();
  return useQuery({
    queryKey: ['reports', 'sales-by-day', range],
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH,
    queryFn: async () =>
      (await api.get<{ items: DayPoint[] }>('/reports/sales-by-day', { params: range })).data.items,
  });
}

export function useTopProducts(range: Range, by: 'revenue' | 'qty' = 'revenue', limit = 5) {
  const api = useApi();
  return useQuery({
    queryKey: ['reports', 'top-products', range, by, limit],
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH,
    queryFn: async () =>
      (
        await api.get<{ items: TopProduct[] }>('/reports/top-products', {
          params: { ...range, by, limit },
        })
      ).data.items,
  });
}

export function useLowStock() {
  const api = useApi();
  return useQuery({
    queryKey: ['reports', 'low-stock'],
    refetchInterval: REFRESH,
    queryFn: async () =>
      (await api.get<{ items: LowStockItem[] }>('/reports/low-stock')).data.items,
  });
}

export function useCashierSummary(range: Range) {
  const api = useApi();
  return useQuery({
    queryKey: ['reports', 'cashiers', range],
    placeholderData: keepPreviousData,
    queryFn: async () =>
      (await api.get<{ items: CashierRow[] }>('/reports/cashiers', { params: range })).data.items,
  });
}

export function useExportSales() {
  const api = useApi();
  return useMutation({
    mutationFn: async (range: Range) => {
      const res = await api.get<Blob>('/reports/sales.csv', {
        params: range,
        responseType: 'blob',
        timeout: 120_000,
      });
      const url = URL.createObjectURL(res.data);
      const link = document.createElement('a');
      link.href = url;
      link.download = `shopdesk-sales-${range.from}-to-${range.to}.csv`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
  });
}

/** yyyy-mm-dd for a date in IST (the shop's calendar). */
export function istDate(d = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(d);
}

/** Shift a yyyy-mm-dd string by whole days. */
export function addDays(date: string, days: number): string {
  const d = new Date(`${date}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}
