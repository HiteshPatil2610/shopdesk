import { apiErrorMessage, Badge, formatINR, Spinner, type PosProduct } from '@shopdesk/shared';
import { useEffect, useState } from 'react';

import { usePosProducts } from './api';

type Props = {
  /** Called when a product is clicked (spec 06 adds it to the cart). */
  onPick?: (product: PosProduct) => void;
};

function useDebounced<T>(value: T, delay = 250): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

/** Searchable list of active products: photo, code, MP, stock. No cost price (BR-12). */
export function ProductPanel({ onPick }: Props) {
  const [search, setSearch] = useState('');
  const products = usePosProducts(useDebounced(search.trim()));

  return (
    <aside className="flex min-w-0 flex-col border-b border-border bg-surface lg:border-r lg:border-b-0">
      <div className="flex items-center gap-2 border-b border-border p-3">
        <h2 className="text-sm font-semibold tracking-wide text-text-muted uppercase">Products</h2>
        <input
          type="search"
          aria-label="Search products"
          placeholder="Search name or code…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="h-11 min-w-0 flex-1 rounded-lg border border-border bg-surface px-3"
        />
      </div>

      <div className="max-h-48 flex-1 overflow-y-auto overscroll-contain lg:max-h-[calc(100dvh-140px)]">
        {products.isPending ? (
          <div className="flex justify-center p-8">
            <Spinner label="Loading products" />
          </div>
        ) : products.isError ? (
          <p className="p-4 text-sm text-danger">{apiErrorMessage(products.error)}</p>
        ) : products.data.items.length === 0 ? (
          <p className="p-6 text-center text-sm text-text-muted">No products found</p>
        ) : (
          <ul>
            {products.data.items.map((p) => {
              const out = p.quantity === 0;
              return (
                <li key={p.id} className="border-b border-border last:border-0">
                  <button
                    type="button"
                    disabled={out || !onPick}
                    onClick={() => onPick?.(p)}
                    className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-bg disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {p.thumb_url ? (
                      <img src={p.thumb_url} alt="" className="h-12 w-12 rounded-md object-cover" />
                    ) : (
                      <div className="h-12 w-12 shrink-0 rounded-md bg-bg" />
                    )}
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">{p.name}</span>
                      <span className="font-mono text-xs text-text-muted">{p.code}</span>
                    </span>
                    <span className="text-right">
                      <span className="block font-semibold tabular-nums">
                        {formatINR(p.market_price)}
                      </span>
                      {out ? (
                        <Badge tone="danger">OUT</Badge>
                      ) : p.low_stock ? (
                        <Badge tone="warning">{p.quantity} left</Badge>
                      ) : (
                        <span className="text-xs text-text-muted">{p.quantity} in stock</span>
                      )}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </aside>
  );
}
