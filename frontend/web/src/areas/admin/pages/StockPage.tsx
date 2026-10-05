import { apiErrorMessage, Badge, Button, Spinner, type Product } from '@shopdesk/shared';
import { useState } from 'react';
import { Link } from 'react-router';

import { StockAdjustModal } from '../features/orders/StockAdjustModal';
import { useProducts } from '../features/products/api';
import { useDebounced } from '../lib/useDebounced';

/** Stock overview: lowest stock first, with quick restock / damage / correction. */
export function StockPage() {
  const [search, setSearch] = useState('');
  const [lowOnly, setLowOnly] = useState(false);
  const [adjusting, setAdjusting] = useState<Product | null>(null);
  const products = useProducts({
    sort: 'quantity',
    page_size: 100,
    low_stock: lowOnly,
    search: useDebounced(search.trim(), 250) || undefined,
  });

  return (
    <section className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold">Stock</h1>
        <p className="text-sm text-text-muted">
          Lowest stock first. Every change is recorded in the product's stock history.
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-surface p-3">
        <input
          type="search"
          aria-label="Search products"
          placeholder="Search name or code…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="h-10 min-w-0 w-full flex-1 sm:min-w-56 rounded-lg border border-border bg-surface px-3 text-sm"
        />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={lowOnly} onChange={(e) => setLowOnly(e.target.checked)} />
          Low stock only
        </label>
      </div>
      <div className="overflow-x-auto rounded-xl border border-border bg-surface">
        {products.isPending ? (
          <div className="flex justify-center p-12">
            <Spinner label="Loading stock" />
          </div>
        ) : products.isError ? (
          <p className="p-8 text-center text-danger">{apiErrorMessage(products.error)}</p>
        ) : products.data.items.length === 0 ? (
          <p className="p-12 text-center text-text-muted">No products.</p>
        ) : (
          <table className="mobile-records w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-text-muted uppercase">
              <tr>
                <th className="px-3 py-3">Code</th>
                <th className="px-3 py-3">Product</th>
                <th className="px-3 py-3 text-right">In stock</th>
                <th className="px-3 py-3 text-right">Alert at</th>
                <th className="px-3 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {products.data.items.map((p) => (
                <tr key={p.id} className="border-b border-border last:border-0">
                  <td data-label="Code" className="px-3 py-2 font-mono text-xs">
                    {p.code}
                  </td>
                  <td data-label="Product" className="px-3 py-2">
                    <Link to={`/admin/products/${p.id}`} className="hover:text-primary">
                      {p.name}
                    </Link>
                  </td>
                  <td data-label="In stock" className="px-3 py-2 text-right tabular-nums">
                    {p.quantity === 0 ? (
                      <Badge tone="danger">0 · out</Badge>
                    ) : p.low_stock ? (
                      <Badge tone="warning">{p.quantity}</Badge>
                    ) : (
                      p.quantity
                    )}{' '}
                    <span className="text-text-muted">{p.unit}</span>
                  </td>
                  <td
                    data-label="Alert at"
                    className="px-3 py-2 text-right text-text-muted tabular-nums"
                  >
                    {p.reorder_level}
                  </td>
                  <td data-label="Action" className="px-3 py-2 text-right">
                    <Button size="sm" variant="secondary" onClick={() => setAdjusting(p)}>
                      Adjust
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <StockAdjustModal product={adjusting} onClose={() => setAdjusting(null)} />
    </section>
  );
}
