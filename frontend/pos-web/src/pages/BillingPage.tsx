import {
  apiErrorMessage,
  Button,
  formatINR,
  Modal,
  Spinner,
  type PosProduct,
} from '@shopdesk/shared';
import { useEffect, useReducer, useRef, useState } from 'react';
import { useLookup, useQuote } from '../features/cart/api';
import { cartReducer, isScan, loadCart, storageKey, validCustomer } from '../features/cart/cart';
import { useHotkeys } from '../features/cart/useHotkeys';
import { ProductPanel } from '../features/products/ProductPanel';

export function BillingPage() {
  const [cart, dispatch] = useReducer(cartReducer, undefined, loadCart);
  const [code, setCode] = useState('');
  const [qty, setQty] = useState('1');
  const [error, setError] = useState('');
  const [selected, setSelected] = useState('');
  const [dialog, setDialog] = useState<'review' | 'clear' | null>(null);
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
  useHotkeys((event) => {
    if (dialog) return;
    const keys: Record<string, () => void> = {
      F2: () => codeInput.current?.focus(),
      F3: () => document.querySelector<HTMLInputElement>('[aria-label="Search products"]')?.focus(),
      F4: () => nameInput.current?.focus(),
      F8: () => dispatch({ type: 'TOGGLE_DISCOUNT' }),
      F9: () => {
        if (ready) setDialog('review');
      },
      Escape: () => {
        if (cart.items.length) setDialog('clear');
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
    <div className="grid min-h-[calc(100vh-57px)] grid-cols-1 md:grid-cols-[320px_1fr]">
      <ProductPanel
        onPick={(product: PosProduct) => {
          void add(product.code, 1);
        }}
      />
      <section className="flex min-w-0 flex-col gap-5 p-5">
        <h1 className="text-2xl font-bold">New bill</h1>
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
          <label className="grid flex-1 gap-1 text-sm font-medium">
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
            <table className="w-full text-left text-sm">
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
                  const problem = line && line.status !== 'ok';
                  return (
                    <tr
                      key={item.code}
                      className={`border-b border-border ${problem ? 'bg-danger/10' : selected === item.code ? 'bg-primary/5' : ''}`}
                    >
                      <td className="p-3">
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
                            {line.status === 'insufficient_stock'
                              ? `Only ${line.available} left`
                              : line.status === 'inactive'
                                ? 'No longer sold'
                                : 'Product not found'}
                          </span>
                        )}
                      </td>
                      <td>
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
                      <td className="tabular-nums">{line ? formatINR(line.unit_price) : '…'}</td>
                      <td className="font-semibold tabular-nums">
                        {line ? formatINR(line.line_total) : '…'}
                      </td>
                      <td>
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
        <label className="flex items-center gap-3 font-semibold">
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
        <div className="flex justify-between border-t border-border pt-4">
          <Button variant="danger" disabled={!cart.items.length} onClick={() => setDialog('clear')}>
            Clear bill <kbd>Esc</kbd>
          </Button>
          <Button disabled={!ready} onClick={() => setDialog('review')}>
            Review bill <kbd>F9</kbd>
          </Button>
        </div>
        <p className="text-xs text-text-muted">
          F3 Search products · Arrow keys select a line · Delete removes the selected line
        </p>
      </section>
      <Modal
        open={dialog === 'clear'}
        title="Clear this bill?"
        onClose={() => setDialog(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setDialog(null)}>
              Keep bill
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                dispatch({ type: 'RESET' });
                setDialog(null);
                setError('');
              }}
            >
              Clear bill
            </Button>
          </>
        }
      >
        <p>The items and customer details in this draft will be cleared.</p>
      </Modal>
      <Modal
        open={dialog === 'review'}
        title="Review bill"
        onClose={() => setDialog(null)}
        footer={<Button onClick={() => setDialog(null)}>Return to bill</Button>}
      >
        <p>
          {cart.name} · {latest ? formatINR(latest.total) : 'Updating…'}
        </p>
        <p className="mt-3 text-text-muted">
          This is a draft. Order saving and payment confirmation are not available yet.
        </p>
      </Modal>
    </div>
  );
}
