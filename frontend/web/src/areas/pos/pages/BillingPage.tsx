import {
  apiErrorCode,
  apiErrorMessage,
  Button,
  formatINR,
  Spinner,
  type PosProduct,
} from '@shopdesk/shared';
import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useReducer, useRef, useState } from 'react';
import {
  useConfirmOrder,
  useLookup,
  useQuote,
  useReceipt,
  useRejectOrder,
  type PaymentMode,
} from '../features/cart/api';
import { cartReducer, isScan, loadCart, storageKey, validCustomer } from '../features/cart/cart';
import { useHotkeys } from '../features/cart/useHotkeys';
import {
  ConfirmOrderDialog,
  MyOrdersDialog,
  ReceiptDialog,
  RejectOrderDialog,
} from '../features/orders/OrderDialogs';
import { ProductPanel } from '../features/products/ProductPanel';

type StockProblem = { code: string; requested: number; available: number };

export function BillingPage() {
  const [cart, dispatch] = useReducer(cartReducer, undefined, loadCart);
  const [code, setCode] = useState('');
  const [qty, setQty] = useState('1');
  const [error, setError] = useState('');
  const [selected, setSelected] = useState('');
  const [dialog, setDialog] = useState<'confirm' | 'reject' | 'mine' | null>(null);
  const [receiptFor, setReceiptFor] = useState<string | null>(null);
  const [stockProblems, setStockProblems] = useState<Record<string, number>>({});
  const [notice, setNotice] = useState('');
  const queryClient = useQueryClient();
  const confirmOrder = useConfirmOrder();
  const rejectOrder = useRejectOrder();
  const receipt = useReceipt(receiptFor);
  const codeInput = useRef<HTMLInputElement>(null);
  const qtyInput = useRef<HTMLInputElement>(null);
  const nameInput = useRef<HTMLInputElement>(null);
  const times = useRef<number[]>([]);
  const busy = useRef(false);
  const lookup = useLookup();
  const quote = useQuote(cart);
  const latest = !quote.isFetching ? quote.data : undefined;
  const ready = Boolean(latest?.can_confirm && validCustomer(cart.name, cart.phone));
  const field = 'h-11 rounded-lg border border-border bg-surface px-3';
  useEffect(() => {
    nameInput.current?.focus();
  }, []);
  useEffect(() => {
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(cart));
    } catch {
      /* Keep the in-memory bill if browser storage is unavailable. */
    }
  }, [cart]);

  async function add(value: string, quantity: number) {
    if (busy.current) return;
    if (!value.trim()) {
      setError('Enter a product code or barcode.');
      return;
    }
    busy.current = true;
    try {
      const product = await lookup.mutateAsync(value.trim());
      const existing = cart.items.find((item) => item.code === product.code)?.qty ?? 0;
      if (
        !Number.isInteger(quantity) ||
        quantity < 1 ||
        existing + quantity > Math.min(product.quantity, 10000)
      ) {
        setError(
          `Only ${Math.min(product.quantity, 10000)} available for ${product.code}. Enter a whole quantity of at least 1.`,
        );
        return;
      }
      if (!existing && cart.items.length >= 100) {
        setError('A bill can contain up to 100 products.');
        return;
      }
      dispatch({
        type: 'ADD',
        key: crypto.randomUUID(),
        item: {
          code: product.code,
          qty: quantity,
          name: product.name,
          available: product.quantity,
        },
      });
      setSelected(product.code);
      setCode('');
      setQty('1');
      setError('');
      times.current = [];
      codeInput.current?.focus();
    } catch (reason) {
      setError(apiErrorMessage(reason));
      codeInput.current?.focus();
    } finally {
      busy.current = false;
    }
  }
  function startNewOrder() {
    setReceiptFor(null);
    setNotice('');
    nameInput.current?.focus();
  }

  async function confirm(payment: PaymentMode) {
    try {
      const order = await confirmOrder.mutateAsync({ cart, payment });
      dispatch({ type: 'RESET' });
      setStockProblems({});
      setDialog(null);
      setReceiptFor(order.order_number);
      void queryClient.invalidateQueries({ queryKey: ['pos-products'] });
    } catch (reason) {
      if (apiErrorCode(reason) === 'INSUFFICIENT_STOCK') {
        // Another counter sold it first: mark the lines, keep the bill, refresh the totals.
        const details = (
          reason as { response?: { data?: { error?: { details?: StockProblem[] } } } }
        ).response?.data?.error?.details;
        setStockProblems(Object.fromEntries((details ?? []).map((d) => [d.code, d.available])));
        setDialog(null);
        void queryClient.invalidateQueries({ queryKey: ['cart-quote'] });
      }
    }
  }

  async function reject(reason: string) {
    try {
      const order = await rejectOrder.mutateAsync({ cart, reason });
      dispatch({ type: 'RESET' });
      setStockProblems({});
      setDialog(null);
      setNotice(`Bill saved as rejected (${order.order_number}).`);
      nameInput.current?.focus();
    } catch {
      /* error shown in the dialog */
    }
  }

  useHotkeys((event) => {
    if (receiptFor) {
      if (event.key === 'n' || event.key === 'N') {
        event.preventDefault();
        startNewOrder();
      }
      return;
    }
    if (dialog) return;
    const keys: Record<string, () => void> = {
      F2: () => codeInput.current?.focus(),
      F3: () => document.querySelector<HTMLInputElement>('[aria-label="Search products"]')?.focus(),
      F4: () => nameInput.current?.focus(),
      F8: () => dispatch({ type: 'TOGGLE_DISCOUNT' }),
      F9: () => {
        if (ready) {
          confirmOrder.reset();
          setDialog('confirm');
        }
      },
      Escape: () => {
        if (cart.items.length) {
          rejectOrder.reset();
          setDialog('reject');
        }
      },
    };
    if (keys[event.key]) {
      event.preventDefault();
      keys[event.key]?.();
      return;
    }
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes((event.target as HTMLElement).tagName)) return;
    if (event.key === 'Delete' && selected) {
      event.preventDefault();
      dispatch({ type: 'REMOVE', code: selected });
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      const index = cart.items.findIndex((item) => item.code === selected);
      const next = Math.max(
        0,
        Math.min(cart.items.length - 1, index + (event.key === 'ArrowDown' ? 1 : -1)),
      );
      setSelected(cart.items[next]?.code ?? '');
    }
  });
  return (
    <div className="grid min-h-[calc(100dvh-57px)] grid-cols-1 lg:grid-cols-[320px_minmax(0,1fr)]">
      <ProductPanel
        onPick={(product: PosProduct) => {
          void add(product.code, 1);
        }}
      />
      <section className="flex min-w-0 flex-col gap-4 p-3 sm:gap-5 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h1 className="text-2xl font-bold">New bill</h1>
          <Button variant="secondary" size="sm" onClick={() => setDialog('mine')}>
            My orders today
          </Button>
        </div>
        {notice && (
          <p role="status" className="rounded-lg bg-success/10 p-3 text-sm text-success">
            {notice}
          </p>
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="grid gap-1 text-sm font-medium">
            Customer name (required) <kbd>F4</kbd>
            <input
              ref={nameInput}
              className={field}
              value={cart.name}
              maxLength={120}
              onChange={(e) =>
                dispatch({ type: 'SET_CUSTOMER', name: e.target.value, phone: cart.phone })
              }
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  codeInput.current?.focus();
                }
              }}
            />
          </label>
          <label className="grid gap-1 text-sm font-medium">
            Phone (optional)
            <input
              className={field}
              value={cart.phone}
              inputMode="tel"
              maxLength={10}
              onChange={(e) =>
                dispatch({ type: 'SET_CUSTOMER', name: cart.name, phone: e.target.value })
              }
            />
          </label>
        </div>
        {cart.phone && !/^[6-9]\d{9}$/.test(cart.phone) && (
          <p className="text-sm text-danger">
            Enter a 10 digit mobile number starting with 6, 7, 8 or 9.
          </p>
        )}
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            void add(code, Number(qty));
          }}
        >
          <label className="grid min-w-0 basis-full gap-1 text-sm font-medium sm:flex-1 sm:basis-auto">
            Product code / barcode <kbd>F2</kbd>
            <input
              ref={codeInput}
              className={field}
              value={code}
              maxLength={64}
              onChange={(e) => {
                setCode(e.target.value);
                if (!e.target.value) times.current = [];
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  if (isScan(times.current, performance.now())) void add(code, 1);
                  else qtyInput.current?.focus();
                  times.current = [];
                } else if (e.key.length === 1) times.current.push(performance.now());
                else if (e.key === 'Backspace' || e.key === 'Delete') times.current = [];
              }}
            />
          </label>
          <label className="grid gap-1 text-sm font-medium">
            Qty
            <input
              ref={qtyInput}
              type="number"
              min={1}
              max={10000}
              className={`${field} w-24`}
              value={qty}
              onChange={(e) => setQty(e.target.value)}
            />
          </label>
          <Button type="submit" disabled={lookup.isPending}>
            Add item
          </Button>
        </form>
        {error && (
          <p role="alert" className="rounded-lg bg-danger/10 p-3 text-sm text-danger">
            {error}
          </p>
        )}
        <div
          className="flex-1 overflow-x-auto rounded-xl border border-border bg-surface"
          aria-label="Bill items. Arrow keys select, Delete removes"
        >
          {!cart.items.length ? (
            <p className="p-12 text-center text-text-muted">
              Enter a code or choose a product to start this bill.
            </p>
          ) : (
            <table className="mobile-records w-full text-left text-sm">
              <thead className="border-b border-border text-text-muted">
                <tr>
                  <th className="p-3">Product</th>
                  <th>Qty</th>
                  <th>Unit price</th>
                  <th>Amount</th>
                  <th>
                    <span className="sr-only">Remove</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {cart.items.map((item) => {
                  const line = latest?.lines.find((value) => value.code === item.code);
                  const available = line?.available ?? item.available;
                  const reported = stockProblems[item.code];
                  // A 409 from confirm: only relevant while the bill still asks for more than that.
                  const soldOut =
                    reported !== undefined && item.qty > reported ? reported : undefined;
                  const problem = (line && line.status !== 'ok') || soldOut !== undefined;
                  return (
                    <tr
                      key={item.code}
                      className={`border-b border-border ${problem ? 'bg-danger/10' : selected === item.code ? 'bg-primary/5' : ''}`}
                    >
                      <td data-label="Product" className="p-3">
                        <button
                          type="button"
                          className="text-left"
                          onClick={() => setSelected(item.code)}
                        >
                          {line?.name ?? item.name}
                          <span className="block font-mono text-xs text-text-muted">
                            {item.code}
                          </span>
                        </button>
                        {problem && (
                          <span role="alert" className="block text-danger">
                            {soldOut !== undefined && (!line || line.status === 'ok')
                              ? `Only ${soldOut} available now`
                              : !line
                                ? ''
                                : line.status === 'insufficient_stock'
                                  ? `Only ${line.available} left`
                                  : line.status === 'inactive'
                                    ? 'No longer sold'
                                    : 'Product not found'}
                          </span>
                        )}
                      </td>
                      <td data-label="Quantity">
                        <input
                          aria-label={`Quantity for ${item.code}`}
                          className={`${field} w-20`}
                          type="number"
                          min={1}
                          max={Math.min(available, 10000)}
                          value={item.qty}
                          onChange={(e) => {
                            const value = Number(e.target.value);
                            if (
                              !Number.isInteger(value) ||
                              value < 1 ||
                              value > Math.min(available, 10000)
                            ) {
                              setError(
                                `Quantity for ${item.code} must be 1–${Math.min(available, 10000)}.`,
                              );
                              return;
                            }
                            dispatch({ type: 'SET_QTY', code: item.code, qty: value });
                            setError('');
                          }}
                        />
                      </td>
                      <td data-label="Unit price" className="tabular-nums">
                        {line ? formatINR(line.unit_price) : '…'}
                      </td>
                      <td data-label="Amount" className="font-semibold tabular-nums">
                        {line ? formatINR(line.line_total) : '…'}
                      </td>
                      <td data-label="Remove">
                        <Button
                          variant="ghost"
                          size="sm"
                          aria-label={`Remove ${item.code}`}
                          onClick={() => dispatch({ type: 'REMOVE', code: item.code })}
                        >
                          ×
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
        <label className="flex flex-wrap items-center gap-3 font-semibold">
          <input
            type="checkbox"
            checked={cart.discount}
            onChange={() => dispatch({ type: 'TOGGLE_DISCOUNT' })}
            className="h-5 w-5 accent-primary"
          />
          Apply Discount <kbd className="text-xs text-text-muted">F8</kbd>
          {cart.discount && latest && (
            <span className="rounded-full bg-primary/10 px-3 py-1 text-sm text-primary">
              You save {formatINR(latest.discount_amount)}
            </span>
          )}
        </label>
        {quote.isError ? (
          <div role="alert" className="flex items-center justify-between text-danger">
            <span>{apiErrorMessage(quote.error)} Your bill is kept.</span>
            <Button
              variant="secondary"
              onClick={() => {
                void quote.refetch();
              }}
            >
              Retry quote
            </Button>
          </div>
        ) : !latest ? (
          <Spinner label="Updating totals" />
        ) : (
          <dl className="ml-auto grid w-full max-w-sm grid-cols-2 gap-2 tabular-nums">
            <dt>Items</dt>
            <dd className="text-right">{latest.item_count}</dd>
            <dt>Subtotal (MP)</dt>
            <dd className="text-right">{formatINR(latest.subtotal_mp)}</dd>
            <dt>Discount</dt>
            <dd className="text-right">− {formatINR(latest.discount_amount)}</dd>
            <dt className="text-2xl font-bold">TOTAL</dt>
            <dd className="text-right text-2xl font-bold">{formatINR(latest.total)}</dd>
          </dl>
        )}
        <div className="grid grid-cols-2 gap-2 border-t border-border pt-4 sm:flex sm:justify-between">
          <Button
            variant="danger"
            size="lg"
            disabled={!cart.items.length}
            onClick={() => {
              rejectOrder.reset();
              setDialog('reject');
            }}
          >
            ✕ Reject <kbd className="ml-1 text-xs opacity-80">Esc</kbd>
          </Button>
          <Button
            variant="success"
            size="lg"
            disabled={!ready}
            onClick={() => {
              confirmOrder.reset();
              setDialog('confirm');
            }}
          >
            ✓ Confirm <kbd className="ml-1 text-xs opacity-80">F9</kbd>
          </Button>
        </div>
        <p className="hidden text-xs text-text-muted lg:block">
          F3 Search products · Arrow keys select a line · Delete removes the selected line
        </p>
      </section>
      <ConfirmOrderDialog
        open={dialog === 'confirm'}
        customer={cart.name.trim()}
        quote={latest}
        busy={confirmOrder.isPending}
        error={
          confirmOrder.isError && apiErrorCode(confirmOrder.error) !== 'INSUFFICIENT_STOCK'
            ? apiErrorMessage(confirmOrder.error) +
              (apiErrorCode(confirmOrder.error) ? '' : ' Your bill is kept. Try again.')
            : null
        }
        onCancel={() => setDialog(null)}
        onConfirm={(payment) => void confirm(payment)}
      />
      <RejectOrderDialog
        open={dialog === 'reject'}
        busy={rejectOrder.isPending}
        error={rejectOrder.isError ? apiErrorMessage(rejectOrder.error) : null}
        onCancel={() => setDialog(null)}
        onReject={(reason) => void reject(reason)}
      />
      <ReceiptDialog
        orderNumber={receiptFor}
        receipt={receipt.data}
        loading={receipt.isPending && receiptFor !== null}
        error={receipt.isError ? apiErrorMessage(receipt.error) : null}
        onNewOrder={startNewOrder}
      />
      <MyOrdersDialog open={dialog === 'mine'} onClose={() => setDialog(null)} />
    </div>
  );
}
