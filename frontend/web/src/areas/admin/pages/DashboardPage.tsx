import {
  apiErrorMessage,
  Badge,
  Button,
  formatINR,
  Spinner,
  useMe,
  type Product,
} from '@shopdesk/shared';
import { useState } from 'react';
import { Link } from 'react-router';

import { StockAdjustModal } from '../features/orders/StockAdjustModal';
import {
  addDays,
  istDate,
  useLowStock,
  useSalesByDay,
  useSummary,
  useTopProducts,
  type LowStockItem,
} from '../features/reports/api';
import { BarChart } from '../features/reports/BarChart';
import { KpiTile } from '../features/reports/KpiTile';

const shortDay = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });

export function DashboardPage() {
  const { user } = useMe();
  const today = istDate();
  const [day, setDay] = useState(today);
  const [restocking, setRestocking] = useState<LowStockItem | null>(null);

  const summary = useSummary(day);
  const days = useSalesByDay({ from: addDays(day, -13), to: day });
  const top = useTopProducts({ from: addDays(day, -6), to: day });
  const low = useLowStock();
  const s = summary.data;

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Welcome, {user.full_name.split(' ')[0]}</h1>
          <p className="text-sm text-text-muted">
            {day === today ? "Today's" : shortDay(day)} business at a glance · refreshes every
            minute
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          Day
          <input
            type="date"
            value={day}
            max={today}
            onChange={(e) => setDay(e.target.value || today)}
            className="h-9 rounded-lg border border-border bg-surface px-2"
          />
        </label>
      </div>

      {summary.isError ? (
        <p className="text-danger">{apiErrorMessage(summary.error)}</p>
      ) : !s ? (
        <div className="flex justify-center p-8">
          <Spinner label="Loading summary" />
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiTile
            label="Sales"
            value={formatINR(s.sales_total)}
            change={s.change_pct.sales_total}
            sub={`Discounts given ${formatINR(s.discount_total)}`}
          />
          <KpiTile
            label="Profit"
            value={formatINR(s.profit_total)}
            change={s.change_pct.profit_total}
          />
          <KpiTile
            label="Orders"
            value={String(s.orders_confirmed)}
            change={s.change_pct.orders_confirmed}
            sub={`${s.orders_rejected} rejected · avg ${formatINR(s.avg_order_value)}`}
          />
          <KpiTile
            label="Low stock"
            value={String(s.low_stock_count)}
            sub={`${s.out_of_stock_count} out of stock`}
            tone={s.low_stock_count > 0 ? 'warning' : 'default'}
          />
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-border bg-surface p-4">
          {days.data ? (
            <BarChart
              title="Sales, last 14 days"
              labels={days.data.map((d) => shortDay(d.date))}
              values={days.data.map((d) => d.sales_total)}
              details={days.data.map(
                (d) =>
                  `${d.orders} order${d.orders === 1 ? '' : 's'} · profit ${formatINR(d.profit_total)}`,
              )}
            />
          ) : days.isError ? (
            <p className="text-danger">{apiErrorMessage(days.error)}</p>
          ) : (
            <Spinner label="Loading chart" />
          )}
        </div>
        <div className="rounded-xl border border-border bg-surface p-4">
          {top.data ? (
            top.data.length ? (
              <BarChart
                title="Top 5 products by sales, last 7 days"
                horizontal
                labels={top.data.map((p) => p.name)}
                values={top.data.map((p) => p.revenue)}
                details={top.data.map((p) => `${p.qty} sold · profit ${formatINR(p.profit)}`)}
              />
            ) : (
              <div>
                <p className="text-sm font-semibold">Top 5 products, last 7 days</p>
                <p className="py-12 text-center text-sm text-text-muted">
                  No sales in this period.
                </p>
              </div>
            )
          ) : top.isError ? (
            <p className="text-danger">{apiErrorMessage(top.error)}</p>
          ) : (
            <Spinner label="Loading chart" />
          )}
        </div>
      </div>

      <div className="rounded-xl border border-border bg-surface">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="font-semibold">Low stock</h2>
          <Link to="/admin/stock" className="text-sm text-primary">
            All stock →
          </Link>
        </div>
        {low.isPending ? (
          <div className="flex justify-center p-6">
            <Spinner label="Loading low stock" />
          </div>
        ) : low.isError ? (
          <p className="p-4 text-danger">{apiErrorMessage(low.error)}</p>
        ) : low.data.length === 0 ? (
          <p className="p-6 text-center text-sm text-text-muted">
            ✓ Everything is above its alert level.
          </p>
        ) : (
          <table className="w-full text-left text-sm">
            <tbody>
              {low.data.slice(0, 8).map((p) => (
                <tr key={p.id} className="border-b border-border last:border-0">
                  <td className="px-4 py-2 font-mono text-xs">{p.code}</td>
                  <td className="px-4 py-2">
                    <Link to={`/admin/products/${p.id}`} className="hover:text-primary">
                      {p.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {p.quantity === 0 ? (
                      <Badge tone="danger">0 · out</Badge>
                    ) : (
                      <Badge tone="warning">
                        {p.quantity} / {p.reorder_level}
                      </Badge>
                    )}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <Button size="sm" variant="secondary" onClick={() => setRestocking(p)}>
                      Restock
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <StockAdjustModal
        product={restocking ? (restocking as unknown as Product) : null}
        onClose={() => {
          setRestocking(null);
          void low.refetch();
          void summary.refetch();
        }}
      />
    </section>
  );
}
