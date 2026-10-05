import { apiErrorMessage, Button, formatINR, Modal, Spinner } from '@shopdesk/shared';
import { useState } from 'react';

import type { MyOrder, PaymentMode, Quote, Receipt } from '../cart/api';
import { useMyOrders } from '../cart/api';
import { ReceiptView } from './ReceiptView';

const MODES: { value: PaymentMode; label: string }[] = [
  { value: 'cash', label: 'Cash' },
  { value: 'upi', label: 'UPI' },
  { value: 'card', label: 'Card' },
];

type ConfirmProps = {
  open: boolean;
  customer: string;
  quote: Quote | undefined;
  busy: boolean;
  error: string | null;
  onCancel: () => void;
  onConfirm: (payment: PaymentMode) => void;
};

/** "Confirm ₹865.00 for Amit Kumar?" + payment mode. Enter confirms (spec 07 §7). */
export function ConfirmOrderDialog({
  open,
  customer,
  quote,
  busy,
  error,
  onCancel,
  onConfirm,
}: ConfirmProps) {
  const [payment, setPayment] = useState<PaymentMode>('cash');
  return (
    <Modal
      open={open}
      title="Confirm order"
      onClose={onCancel}
      footer={
        <>
          <Button variant="secondary" onClick={onCancel} disabled={busy}>
            Back to bill
          </Button>
          <Button
            variant="success"
            size="lg"
            type="submit"
            form="confirm-order-form"
            disabled={busy || !quote?.can_confirm}
          >
            {busy ? 'Saving…' : `Confirm ${quote ? formatINR(quote.total) : ''}`}
          </Button>
        </>
      }
    >
      <form
        id="confirm-order-form"
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (!busy && quote?.can_confirm) onConfirm(payment);
        }}
      >
        <p className="text-lg">
          Confirm <strong className="tabular-nums">{quote ? formatINR(quote.total) : '…'}</strong>{' '}
          for <strong>{customer}</strong>?
        </p>
        {quote && (
          <p className="text-sm text-text-muted">
            {quote.item_count} item(s){quote.discount_applied && ' · discount applied'}
          </p>
        )}
        <fieldset className="flex gap-2">
          <legend className="mb-2 text-sm font-medium">Payment</legend>
          {MODES.map((m) => (
            <label
              key={m.value}
              className={`flex cursor-pointer items-center gap-2 rounded-lg border px-4 py-2 ${
                payment === m.value ? 'border-primary bg-primary/10 font-semibold' : 'border-border'
              }`}
            >
              <input
                type="radio"
                name="payment"
                value={m.value}
                checked={payment === m.value}
                onChange={() => setPayment(m.value)}
                className="sr-only"
              />
              {m.label}
            </label>
          ))}
        </fieldset>
        {error && (
          <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}
        {/* Enter submits the form; the first focusable control is the Cash option. */}
        <button type="submit" className="sr-only" tabIndex={-1}>
          Confirm
        </button>
      </form>
    </Modal>
  );
}

type RejectProps = {
  open: boolean;
  busy: boolean;
  error: string | null;
  onCancel: () => void;
  onReject: (reason: string) => void;
};

export function RejectOrderDialog({ open, busy, error, onCancel, onReject }: RejectProps) {
  const [reason, setReason] = useState('');
  return (
    <Modal
      open={open}
      title="Reject this bill?"
      onClose={onCancel}
      footer={
        <>
          <Button variant="secondary" onClick={onCancel} disabled={busy}>
            Keep bill
          </Button>
          <Button variant="danger" type="submit" form="reject-order-form" disabled={busy}>
            {busy ? 'Saving…' : 'Reject bill'}
          </Button>
        </>
      }
    >
      <form
        id="reject-order-form"
        className="flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          onReject(reason);
        }}
      >
        <p className="text-sm">
          The bill is saved as <strong>rejected</strong> for the records and the screen is cleared.
          Stock is not changed.
        </p>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Reason (optional)
          <input
            value={reason}
            maxLength={255}
            onChange={(e) => setReason(e.target.value)}
            className="h-10 rounded-lg border border-border bg-surface px-3"
            placeholder="e.g. customer changed mind"
          />
        </label>
        {error && (
          <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}
      </form>
    </Modal>
  );
}

type ReceiptProps = {
  receipt: Receipt | undefined;
  loading: boolean;
  error: string | null;
  orderNumber: string | null;
  onNewOrder: () => void;
};

/** Shown after a successful confirm: Print or start a New order (N). */
export function ReceiptDialog({ receipt, loading, error, orderNumber, onNewOrder }: ReceiptProps) {
  return (
    <Modal
      open={orderNumber !== null}
      title={`Order ${orderNumber ?? ''} confirmed`}
      onClose={onNewOrder}
      footer={
        <>
          <Button variant="secondary" disabled={!receipt} onClick={() => window.print()}>
            Print receipt
          </Button>
          <Button onClick={onNewOrder}>
            New order <kbd className="ml-1 text-xs opacity-80">N</kbd>
          </Button>
        </>
      }
    >
      {loading ? (
        <div className="flex justify-center p-6">
          <Spinner label="Loading receipt" />
        </div>
      ) : error ? (
        <p className="text-sm text-danger">
          The order is saved, but the receipt couldn't load: {error}
        </p>
      ) : receipt ? (
        <div className="max-h-[60vh] overflow-y-auto rounded-lg border border-border">
          <ReceiptView receipt={receipt} />
        </div>
      ) : null}
    </Modal>
  );
}

export function MyOrdersDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const orders = useMyOrders(open);
  return (
    <Modal open={open} title="My orders today" onClose={onClose} size="lg">
      {orders.isPending ? (
        <div className="flex justify-center p-6">
          <Spinner label="Loading orders" />
        </div>
      ) : orders.isError ? (
        <p className="text-sm text-danger">{apiErrorMessage(orders.error)}</p>
      ) : orders.data.length === 0 ? (
        <p className="text-sm text-text-muted">No orders yet today.</p>
      ) : (
        <MyOrdersTable orders={orders.data} />
      )}
    </Modal>
  );
}

function MyOrdersTable({ orders }: { orders: MyOrder[] }) {
  const confirmed = orders.filter((o) => o.status === 'confirmed').length;
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-text-muted">
        {confirmed} confirmed · {orders.length - confirmed} rejected
      </p>
      <table className="mobile-records w-full text-left text-sm">
        <thead className="text-xs text-text-muted uppercase">
          <tr>
            <th className="py-1">Time</th>
            <th className="py-1">Order</th>
            <th className="py-1">Customer</th>
            <th className="py-1 text-right">Total</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((o) => (
            <tr key={o.order_number} className="border-t border-border">
              <td data-label="Time" className="py-1 tabular-nums">
                {new Date(o.created_at).toLocaleTimeString('en-IN', {
                  timeZone: 'Asia/Kolkata',
                  timeStyle: 'short',
                })}
              </td>
              <td data-label="Order" className="py-1 font-mono text-xs">
                {o.order_number}
                {o.status === 'rejected' && <span className="ml-1 text-danger">(rejected)</span>}
              </td>
              <td data-label="Customer" className="py-1">
                {o.customer_name}
              </td>
              <td data-label="Total" className="py-1 text-right tabular-nums">
                {formatINR(o.total)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
