import { apiErrorMessage, Badge, Button, formatINR, Spinner } from '@shopdesk/shared';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router';

import { useCategories, useProducts, type ProductQuery } from '../features/products/api';
import { useDebounced } from '../lib/useDebounced';

const PAGE_SIZE = 25;

export function ProductsPage() {
  const navigate = useNavigate();
  const categories = useCategories();
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState<ProductQuery>({ sort: 'name', page: 1, page_size: PAGE_SIZE });
  const debouncedSearch = useDebounced(search, 250);
  const products = useProducts({ ...query, search: debouncedSearch.trim() || undefined });

  const set = (patch: Partial<ProductQuery>) => setQuery((q) => ({ ...q, page: 1, ...patch }));
  const total = products.data?.total ?? 0;
  const page = query.page ?? 1;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Products</h1>
          <p className="text-sm text-text-muted">
            {total} product{total === 1 ? '' : 's'}
          </p>
        </div>
        <Button onClick={() => navigate('/admin/products/new')}>+ Add product</Button>
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-surface p-3">
        <input
          type="search"
          aria-label="Search products"
          placeholder="Search name, code or barcode…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="h-10 min-w-56 flex-1 rounded-lg border border-border bg-surface px-3 text-sm"
        />
        <select
          aria-label="Category"
          value={query.category_id ?? ''}
          onChange={(e) => set({ category_id: e.target.value || undefined })}
          className="h-10 rounded-lg border border-border bg-surface px-2 text-sm"
        >
          <option value="">All categories</option>
          {(categories.data ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={Boolean(query.low_stock)}
            onChange={(e) => set({ low_stock: e.target.checked })}
          />
          Low stock only
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={Boolean(query.include_inactive)}
            onChange={(e) => set({ include_inactive: e.target.checked })}
          />
          Show inactive
        </label>
        <select
          aria-label="Sort"
          value={query.sort}
          onChange={(e) => set({ sort: e.target.value })}
          className="h-10 rounded-lg border border-border bg-surface px-2 text-sm"
        >
          <option value="name">Name A–Z</option>
          <option value="-updated_at">Recently changed</option>
          <option value="code">Code</option>
          <option value="quantity">Stock: low → high</option>
          <option value="-quantity">Stock: high → low</option>
        </select>
      </div>

      <div className="overflow-x-auto rounded-xl border border-border bg-surface">
        {products.isPending ? (
          <div className="flex justify-center p-12">
            <Spinner label="Loading products" />
          </div>
        ) : products.isError ? (
          <p className="p-8 text-center text-danger">{apiErrorMessage(products.error)}</p>
        ) : products.data.items.length === 0 ? (
          <div className="p-12 text-center">
            <p className="font-medium">No products found</p>
            <p className="text-sm text-text-muted">
              Try another search, or add your first product.
            </p>
          </div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-text-muted uppercase">
              <tr>
                <th className="w-14 px-3 py-3" aria-label="Photo" />
                <th className="px-3 py-3">Code</th>
                <th className="px-3 py-3">Name</th>
                <th className="px-3 py-3">Category</th>
                <th className="px-3 py-3 text-right">Qty</th>
                <th className="px-3 py-3 text-right">Cost</th>
                <th className="px-3 py-3 text-right">MP</th>
                <th className="px-3 py-3 text-right">SP</th>
                <th className="px-3 py-3 text-right">Margin (SP)</th>
              </tr>
            </thead>
            <tbody>
              {products.data.items.map((p) => (
                <tr
                  key={p.id}
                  onClick={() => navigate(`/admin/products/${p.id}`)}
                  className={`cursor-pointer border-b border-border last:border-0 hover:bg-bg ${
                    p.is_active ? '' : 'opacity-60'
                  }`}
                >
                  <td className="px-3 py-2">
                    {p.thumb_url ? (
                      <img src={p.thumb_url} alt="" className="h-10 w-10 rounded-md object-cover" />
                    ) : (
                      <div className="h-10 w-10 rounded-md bg-bg" />
                    )}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">{p.code}</td>
                  <td className="px-3 py-2">
                    <Link
                      to={`/admin/products/${p.id}`}
                      className="font-medium hover:text-primary"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {p.name}
                    </Link>
                    {!p.is_active && (
                      <span className="ml-2">
                        <Badge tone="danger">inactive</Badge>
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-text-muted">{p.category?.name ?? '—'}</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {p.quantity === 0 ? (
                      <Badge tone="danger">0 · out</Badge>
                    ) : p.low_stock ? (
                      <Badge tone="warning">{p.quantity}</Badge>
                    ) : (
                      p.quantity
                    )}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatINR(p.cost_price)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {formatINR(p.market_price)}
                    {p.mp_is_manual && <span title="Manual price"> ✎</span>}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {formatINR(p.selling_price)}
                    {p.sp_is_manual && <span title="Manual price"> ✎</span>}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-text-muted">
                    {p.sp_margin_pct ? `${p.sp_margin_pct}%` : '—'}
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
            onClick={() => setQuery((q) => ({ ...q, page: page - 1 }))}
          >
            ← Prev
          </Button>
          <span className="tabular-nums">
            Page {page} of {pages}
          </span>
          <Button
            size="sm"
            variant="secondary"
            disabled={page >= pages}
            onClick={() => setQuery((q) => ({ ...q, page: page + 1 }))}
          >
            Next →
          </Button>
        </div>
      )}
    </section>
  );
}
