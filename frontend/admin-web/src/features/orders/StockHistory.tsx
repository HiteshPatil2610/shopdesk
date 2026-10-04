import { apiErrorMessage, Badge, Spinner } from '@shopdesk/shared';
import { Link } from 'react-router';

import { useStockMovements } from './api';

const REASON_TONE = {
  initial: 'neutral',
  restock: 'success',
  sale: 'primary',
  adjustment: 'neutral',
  damage: 'danger',
  correction: 'warning',
} as const;

/** Read-only stock ledger for one product (spec 07 §7). */
export function StockHistory({ productId }: { productId: number }) {
  const moves = useStockMovements(productId);
  if (moves.isPending) {
    return (
      <div className="flex justify-center p-8">
        <Spinner label="Loading stock history" />
      </div>
    );
  }
  if (moves.isError) return <p className="text-danger">{apiErrorMessage(moves.error)}</p>;
  if (moves.data.items.length === 0) {
    return <p className="p-6 text-center text-text-muted">No stock changes yet.</p>;
  }
  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-surface">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-border text-xs text-text-muted uppercase">
          <tr>
            <th className="px-3 py-2">When</th>
            <th className="px-3 py-2">Reason</th>
            <th className="px-3 py-2 text-right">Change</th>
            <th className="px-3 py-2 text-right">Stock after</th>
            <th className="px-3 py-2">Note / reference</th>
          </tr>
        </thead>
        <tbody>
          {moves.data.items.map((m) => (
            <tr key={m.id} className="border-b border-border last:border-0">
              <td className="px-3 py-2 whitespace-nowrap">
                {new Date(m.created_at).toLocaleString('en-IN', {
                  timeZone: 'Asia/Kolkata',
                  dateStyle: 'medium',
                  timeStyle: 'short',
                })}
              </td>
              <td className="px-3 py-2">
                <Badge tone={REASON_TONE[m.reason as keyof typeof REASON_TONE] ?? 'neutral'}>
                  {m.reason}
                </Badge>
              </td>
              <td
                className={`px-3 py-2 text-right font-medium tabular-nums ${m.change < 0 ? 'text-danger' : 'text-success'}`}
              >
                {m.change > 0 ? `+${m.change}` : m.change}
              </td>
              <td className="px-3 py-2 text-right tabular-nums">{m.quantity_after}</td>
              <td className="px-3 py-2 text-text-muted">
                {m.reference_type === 'order' && m.reference_id ? (
                  <Link className="text-primary" to={`/orders/${m.reference_id}`}>
                    Order #{m.reference_id}
                  </Link>
                ) : (
                  (m.note ?? '—')
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
