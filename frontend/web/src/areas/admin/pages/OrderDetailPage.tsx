import { apiErrorMessage, Badge, formatINR, Spinner } from '@shopdesk/shared';
import { Link, useParams } from 'react-router';

import { useOrder } from '../features/orders/api';

const PAYMENT = { cash: 'Cash', upi: 'UPI', card: 'Card' } as const;

export function OrderDetailPage() {
  const id = Number(useParams().id);
  const order = useOrder(id);

  if (order.isPending) {
    return (
      <div className="flex justify-center p-16">
        <Spinner label="Loading order" />
      </div>
    );
  }
  if (order.isError) {
    return <p className="p-8 text-center text-danger">{apiErrorMessage(order.error)}</p>;
  }
  const o = order.data;
  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-4">
      <div>
        <Link to="/admin/orders" className="text-sm text-primary">
          ← Orders
        </Link>
        <h1 className="flex flex-wrap items-center gap-3 text-2xl font-bold">
          <span className="font-mono">{o.order_number}</span>
          {o.status === 'confirmed' ? (
            <Badge tone="success">Confirmed</Badge>
          ) : (
            <Badge>Rejected</Badge>
          )}
        </h1>
        <p className="text-sm text-text-muted">
          {new Date(o.created_at).toLocaleString('en-IN', {
            timeZone: 'Asia/Kolkata',
            dateStyle: 'full',
            timeStyle: 'short',
          })}{' '}
          · cashier {o.cashier_name}
          {o.payment_mode && ` · ${PAYMENT[o.payment_mode]}`}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-border bg-surface p-4">
          <p className="text-xs text-text-muted uppercase">Customer</p>
          <p className="font-semibold">{o.customer_name}</p>
          {o.customer_phone && <p className="text-sm text-text-muted">{o.customer_phone}</p>}
        </div>
        <div className="rounded-xl border border-border bg-surface p-4">
          <p className="text-xs text-text-muted uppercase">Total</p>
          <p className="text-xl font-bold tabular-nums">{formatINR(o.total)}</p>
          {o.discount_applied && (
            <p className="text-sm text-discount">Discount −{formatINR(o.discount_amount)}</p>
          )}
        </div>
        <div className="rounded-xl border border-border bg-surface p-4">
          <p className="text-xs text-text-muted uppercase">Profit</p>
          <p className="text-xl font-bold tabular-nums">{o.profit ? formatINR(o.profit) : '—'}</p>
          <p className="text-sm text-text-muted">Cost {formatINR(o.total_cost)}</p>
        </div>
      </div>

      {o.reject_reason && (
        <p className="rounded-lg bg-bg px-3 py-2 text-sm">Reject reason: {o.reject_reason}</p>
      )}

      <div className="overflow-x-auto rounded-xl border border-border bg-surface">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-border text-xs text-text-muted uppercase">
            <tr>
              <th className="px-3 py-2">Product</th>
              <th className="px-3 py-2 text-right">Qty</th>
              <th className="px-3 py-2 text-right">Cost</th>
              <th className="px-3 py-2 text-right">MP</th>
              <th className="px-3 py-2 text-right">SP</th>
              <th className="px-3 py-2 text-right">Charged</th>
              <th className="px-3 py-2 text-right">Line total</th>
              <th className="px-3 py-2 text-right">Profit</th>
            </tr>
          </thead>
          <tbody>
            {(o.lines ?? []).map((l) => (
              <tr key={l.code} className="border-b border-border last:border-0 tabular-nums">
                <td className="px-3 py-2">
                  <Link to={`/admin/products/${l.product_id}`} className="hover:text-primary">
                    {l.name}
                  </Link>
                  <span className="block font-mono text-xs text-text-muted">{l.code}</span>
                </td>
                <td className="px-3 py-2 text-right">{l.qty}</td>
                <td className="px-3 py-2 text-right">{formatINR(l.unit_cost)}</td>
                <td className="px-3 py-2 text-right">{formatINR(l.unit_mp)}</td>
                <td className="px-3 py-2 text-right">{formatINR(l.unit_sp)}</td>
                <td className="px-3 py-2 text-right font-medium">{formatINR(l.unit_price)}</td>
                <td className="px-3 py-2 text-right">{formatINR(l.line_total)}</td>
                <td className="px-3 py-2 text-right">
                  {o.status === 'confirmed' ? formatINR(l.profit) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Link
        to={`/admin/audit?entity_type=order&entity_id=${o.id}`}
        className="self-start text-sm text-primary"
      >
        View in audit log →
      </Link>
    </section>
  );
}
