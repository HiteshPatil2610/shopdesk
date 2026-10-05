import { apiErrorMessage, Button, formatINR, Spinner, useMe } from '@shopdesk/shared';
import { useState } from 'react';

import {
  addDays,
  istDate,
  useCashierSummary,
  useExportSales,
  useSalesByDay,
  useTopProducts,
  type Range,
} from '../features/reports/api';
import { BarChart } from '../features/reports/BarChart';

const PRESETS = [
  { label: 'Last 7 days', days: 7 },
  { label: 'Last 30 days', days: 30 },
  { label: 'Last 90 days', days: 90 },
];

export function ReportsPage() {
  const { user } = useMe();
  const today = istDate();
  const [range, setRange] = useState<Range>({ from: addDays(today, -29), to: today });
  const [by, setBy] = useState<'revenue' | 'qty'>('revenue');
  const days = useSalesByDay(range);
  const top = useTopProducts(range, by, 10);
  const cashiers = useCashierSummary(range);
  const exportSales = useExportSales();
  const valid = range.from <= range.to;

  return (
    <section className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Reports</h1>
          <p className="text-sm text-text-muted">Confirmed sales only · dates in IST</p>
        </div>
        {user.role === 'admin' && (
          <Button
            variant="secondary"
            disabled={!valid || exportSales.isPending}
            onClick={() => exportSales.mutate(range)}
          >
            {exportSales.isPending ? 'Exporting…' : '⬇ Export sales CSV'}
          </Button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3 min-w-0 rounded-xl border border-border bg-surface p-3 text-sm">
        {PRESETS.map((p) => (
          <Button
            key={p.days}
            size="sm"
            variant="secondary"
            onClick={() => setRange({ from: addDays(today, -(p.days - 1)), to: today })}
          >
            {p.label}
          </Button>
        ))}
        <label className="flex items-center gap-2">
          From
          <input
            type="date"
            value={range.from}
            max={range.to}
            onChange={(e) => e.target.value && setRange((r) => ({ ...r, from: e.target.value }))}
            className="h-9 rounded-lg border border-border bg-surface px-2"
          />
        </label>
        <label className="flex items-center gap-2">
          To
          <input
            type="date"
            value={range.to}
            max={today}
            onChange={(e) => e.target.value && setRange((r) => ({ ...r, to: e.target.value }))}
            className="h-9 rounded-lg border border-border bg-surface px-2"
          />
        </label>
      </div>
      {exportSales.isError && (
        <p className="text-sm text-danger">{apiErrorMessage(exportSales.error)}</p>
      )}

      <div className="min-w-0 rounded-xl border border-border bg-surface p-4">
        {days.data ? (
          <BarChart
            title="Sales by day"
            labels={days.data.map((d) =>
              new Date(`${d.date}T00:00:00`).toLocaleDateString('en-IN', {
                day: 'numeric',
                month: 'short',
              }),
            )}
            values={days.data.map((d) => d.sales_total)}
            details={days.data.map(
              (d) => `${d.orders} orders · profit ${formatINR(d.profit_total)}`,
            )}
          />
        ) : days.isError ? (
          <p className="text-danger">{apiErrorMessage(days.error)}</p>
        ) : (
          <Spinner label="Loading" />
        )}
      </div>

      <div className="grid min-w-0 gap-4 lg:grid-cols-2">
        <div className="min-w-0 rounded-xl border border-border bg-surface">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <h2 className="font-semibold">Top products</h2>
            <select
              aria-label="Rank by"
              value={by}
              onChange={(e) => setBy(e.target.value as 'revenue' | 'qty')}
              className="h-8 rounded-md border border-border bg-surface px-2 text-sm"
            >
              <option value="revenue">By sales ₹</option>
              <option value="qty">By quantity</option>
            </select>
          </div>
          <div className="min-w-0 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-text-muted uppercase">
                <tr>
                  <th className="px-4 py-2">Product</th>
                  <th className="px-4 py-2 text-right">Qty</th>
                  <th className="px-4 py-2 text-right">Sales</th>
                  <th className="px-4 py-2 text-right">Profit</th>
                </tr>
              </thead>
              <tbody>
                {(top.data ?? []).map((p) => (
                  <tr key={p.product_id} className="border-t border-border tabular-nums">
                    <td className="px-4 py-2">
                      {p.name} <span className="font-mono text-xs text-text-muted">{p.code}</span>
                    </td>
                    <td className="px-4 py-2 text-right">{p.qty}</td>
                    <td className="px-4 py-2 text-right">{formatINR(p.revenue)}</td>
                    <td className="px-4 py-2 text-right">{formatINR(p.profit)}</td>
                  </tr>
                ))}
                {top.data?.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-text-muted">
                      No sales in this period.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="min-w-0 rounded-xl border border-border bg-surface">
          <h2 className="border-b border-border px-4 py-3 font-semibold">Cashiers</h2>
          <div className="min-w-0 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-text-muted uppercase">
                <tr>
                  <th className="px-4 py-2">Cashier</th>
                  <th className="px-4 py-2 text-right">Orders</th>
                  <th className="px-4 py-2 text-right">Sales</th>
                  <th className="px-4 py-2 text-right">Rejected</th>
                  <th className="px-4 py-2 text-right">Discounts</th>
                </tr>
              </thead>
              <tbody>
                {(cashiers.data ?? []).map((c) => (
                  <tr key={c.cashier_id} className="border-t border-border tabular-nums">
                    <td className="px-4 py-2">{c.cashier}</td>
                    <td className="px-4 py-2 text-right">{c.orders}</td>
                    <td className="px-4 py-2 text-right">{formatINR(c.sales_total)}</td>
                    <td className="px-4 py-2 text-right">{c.rejected}</td>
                    <td className="px-4 py-2 text-right">
                      {formatINR(c.discounts_given)}
                      <span className="block text-xs text-text-muted">
                        on {c.discount_orders} order{c.discount_orders === 1 ? '' : 's'}
                      </span>
                    </td>
                  </tr>
                ))}
                {cashiers.data?.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-text-muted">
                      No orders in this period.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  );
}
