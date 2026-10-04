import { apiErrorMessage, Badge, Button, formatINR, Spinner } from '@shopdesk/shared';
import { useState } from 'react';
import { useNavigate } from 'react-router';

import { useOrders, type OrderQuery } from '../features/orders/api';
import { useDebounced } from '../lib/useDebounced';

const PAGE_SIZE = 25;

export function OrdersPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState<OrderQuery>({ page: 1, page_size: PAGE_SIZE });
  const q = useDebounced(search.trim(), 250);
  const orders = useOrders({ ...query, q: q || undefined });
  const total = orders.data?.total ?? 0;
  const page = query.page ?? 1;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <section className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold">Orders</h1>
        <p className="text-sm text-text-muted">
          Every bill from the Billing Counter, confirmed and rejected. Prices are as charged at the
          time of sale.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-surface p-3">
        <input
          type="search"
          aria-label="Search orders"
          placeholder="Customer name or order number…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="h-10 min-w-56 flex-1 rounded-lg border border-border bg-surface px-3 text-sm"
        />
        <select
          aria-label="Status"
          value={query.status ?? ''}
          onChange={(e) =>
            setQuery((s) => ({ ...s, page: 1, status: e.target.value || undefined }))
          }
          className="h-10 rounded-lg border border-border bg-surface px-2 text-sm"
        >
          <option value="">All</option>
          <option value="confirmed">Confirmed</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      <div className="overflow-x-auto rounded-xl border border-border bg-surface">
        {orders.isPending ? (
          <div className="flex justify-center p-12">
            <Spinner label="Loading orders" />
          </div>
        ) : orders.isError ? (
          <p className="p-8 text-center text-danger">{apiErrorMessage(orders.error)}</p>
        ) : orders.data.items.length === 0 ? (
          <p className="p-12 text-center text-text-muted">No orders yet.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-text-muted uppercase">
              <tr>
                <th className="px-3 py-3">Order</th>
                <th className="px-3 py-3">Date</th>
                <th className="px-3 py-3">Customer</th>
                <th className="px-3 py-3">Cashier</th>
                <th className="px-3 py-3 text-right">Items</th>
                <th className="px-3 py-3 text-right">Total</th>
                <th className="px-3 py-3 text-right">Profit</th>
                <th className="px-3 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {orders.data.items.map((o) => (
                <tr
                  key={o.id}
                  onClick={() => navigate(`/orders/${o.id}`)}
                  className="cursor-pointer border-b border-border last:border-0 hover:bg-bg"
                >
                  <td className="px-3 py-2 font-mono text-xs">{o.order_number}</td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    {new Date(o.created_at).toLocaleString('en-IN', {
                      timeZone: 'Asia/Kolkata',
                      dateStyle: 'medium',
                      timeStyle: 'short',
                    })}
                  </td>
                  <td className="px-3 py-2">{o.customer_name}</td>
                  <td className="px-3 py-2 text-text-muted">{o.cashier_name}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{o.item_count}</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {formatINR(o.total)}
                    {o.discount_applied && <span title="Discount applied"> %</span>}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {o.profit ? formatINR(o.profit) : '—'}
                  </td>
                  <td className="px-3 py-2">
                    {o.status === 'confirmed' ? (
                      <Badge tone="success">Confirmed</Badge>
                    ) : (
                      <Badge>Rejected</Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {pages > 1 && (
        <div className="flex items-center justify-end gap-2 text-sm">
          <Button
            size="sm"
            variant="secondary"
            disabled={page <= 1}
            onClick={() => setQuery((s) => ({ ...s, page: page - 1 }))}
          >
            ← Prev
          </Button>
          <span>
            Page {page} of {pages}
          </span>
          <Button
            size="sm"
            variant="secondary"
            disabled={page >= pages}
            onClick={() => setQuery((s) => ({ ...s, page: page + 1 }))}
          >
            Next →
          </Button>
        </div>
      )}
    </section>
  );
}
