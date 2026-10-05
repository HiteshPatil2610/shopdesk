import { apiErrorMessage, Badge, Button, Modal, Spinner, useMe } from '@shopdesk/shared';
import { useState } from 'react';
import { useSearchParams } from 'react-router';

import { useAudit, useExportAudit, type AuditEntry } from '../features/audit/api';

const formatDate = (iso: string) =>
  new Date(iso).toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    dateStyle: 'medium',
    timeStyle: 'short',
  });
const show = (value: unknown) => (value === undefined ? '—' : JSON.stringify(value));
const dateInputIST = (iso: string | undefined) => {
  if (!iso || Number.isNaN(Date.parse(iso))) return '';
  return new Date(Date.parse(iso) + 330 * 60_000).toISOString().slice(0, 16);
};

export function AuditPage({ productId }: { productId?: number }) {
  const [search, setSearch] = useSearchParams();
  const params = Object.fromEntries(search);
  if (productId !== undefined) {
    params.entity_type = 'product';
    params.entity_id = String(productId);
  }
  const logs = useAudit(params);
  const download = useExportAudit();
  const { user } = useMe();
  const [selected, setSelected] = useState<AuditEntry | null>(null);
  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(search);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== 'page') next.delete('page');
    setSearch(next);
  };
  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Audit log</h1>
          <p className="text-sm text-text-muted">
            Read-only history across both apps. Times shown in IST.
            {user.role === 'admin' &&
              ' CSV exports include up to the newest 100,000 matching entries.'}
          </p>
        </div>
        {user.role === 'admin' && (
          <Button
            variant="secondary"
            disabled={download.isPending}
            onClick={() => download.mutate(params)}
          >
            {download.isPending ? 'Exporting…' : 'Export CSV'}
          </Button>
        )}
      </div>
      <div className="grid gap-3 rounded-xl border border-border bg-surface p-4 sm:grid-cols-3 lg:grid-cols-4">
        {(['from', 'to'] as const).map((key) => (
          <label key={key} className="text-sm">
            {key === 'from' ? 'From (IST)' : 'To (IST)'}
            <input
              type="datetime-local"
              value={dateInputIST(params[key])}
              onChange={(e) =>
                setFilter(
                  key,
                  e.target.value ? new Date(`${e.target.value}+05:30`).toISOString() : '',
                )
              }
              className="mt-1 block w-full rounded-md border border-border p-2"
            />
          </label>
        ))}
        <label className="text-sm">
          Source
          <select
            value={params.source ?? ''}
            onChange={(e) => setFilter('source', e.target.value)}
            className="mt-1 block w-full rounded-md border border-border p-2"
          >
            <option value="">All sources</option>
            <option value="admin">Admin</option>
            <option value="pos">Billing Counter</option>
            <option value="system">System</option>
          </select>
        </label>
        {(
          [
            ['user_id', 'User ID', 'number'],
            ['action', 'Action or prefix', 'text'],
            ['entity_type', 'Entity type', 'text'],
            ['entity_id', 'Entity ID', 'text'],
            ['q', 'Search summary', 'search'],
          ] as const
        ).map(([key, label, type]) => (
          <label key={key} className="text-sm">
            {label}
            <input
              type={type}
              min={type === 'number' ? 1 : undefined}
              value={params[key] ?? ''}
              onChange={(e) => setFilter(key, e.target.value)}
              className="mt-1 block w-full rounded-md border border-border p-2"
            />
          </label>
        ))}
        <Button variant="secondary" onClick={() => setSearch({})}>
          Clear filters
        </Button>
      </div>
      {download.isError && (
        <p role="alert" className="text-danger">
          {apiErrorMessage(download.error)}
        </p>
      )}
      {logs.isPending ? (
        <Spinner label="Loading audit history" />
      ) : logs.isError ? (
        <p role="alert" className="text-danger">
          {apiErrorMessage(logs.error)}
        </p>
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-border bg-surface">
            <table className="w-full text-left text-sm">
              <thead>
                <tr>
                  {['When (IST)', 'User', 'Source', 'Action', 'Summary', 'Details'].map((h) => (
                    <th key={h} className="px-4 py-3">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {logs.data.items.map((row) => (
                  <tr key={row.id} className="border-t border-border">
                    <td className="whitespace-nowrap px-4 py-3">{formatDate(row.occurred_at)}</td>
                    <td className="px-4 py-3">
                      {row.actor_username}
                      <span className="block text-xs text-text-muted">
                        ID {row.actor_user_id ?? 'system'}
                      </span>
                    </td>
                    <td className="px-4 py-3">{row.source}</td>
                    <td className="px-4 py-3">
                      <Badge
                        tone={
                          row.action.includes('deactivate')
                            ? 'danger'
                            : row.action.endsWith('create')
                              ? 'success'
                              : 'neutral'
                        }
                      >
                        {row.action}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">{row.summary}</td>
                    <td className="px-4 py-3">
                      <Button size="sm" variant="secondary" onClick={() => setSelected(row)}>
                        View details
                      </Button>
                    </td>
                  </tr>
                ))}
                {!logs.data.items.length && (
                  <tr>
                    <td colSpan={6} className="p-10 text-center text-text-muted">
                      No audit entries match these filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span>
              {logs.data.total} entries · Page {logs.data.page}
            </span>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                disabled={logs.data.page <= 1 || logs.isFetching}
                onClick={() => setFilter('page', String(logs.data.page - 1))}
              >
                Previous
              </Button>
              <Button
                variant="secondary"
                disabled={
                  logs.data.page * logs.data.page_size >= logs.data.total || logs.isFetching
                }
                onClick={() => setFilter('page', String(logs.data.page + 1))}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      )}
      <Modal
        open={selected !== null}
        title="Audit entry details"
        size="lg"
        onClose={() => setSelected(null)}
      >
        {selected && (
          <div className="flex flex-col gap-4 text-sm">
            <p className="font-medium">{selected.summary}</p>
            <p>
              {formatDate(selected.occurred_at)} · {selected.actor_username} · {selected.source} ·{' '}
              {selected.action}
            </p>
            <p>
              Entity: {selected.entity_type} / {selected.entity_id ?? '—'} · Entry #{selected.id}
            </p>
            {selected.changes && (
              <table className="w-full text-left">
                <thead>
                  <tr>
                    <th>Field</th>
                    <th>Before</th>
                    <th>After</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(selected.changes).map(([field, values]) => (
                    <tr key={field} className="border-t border-border">
                      <td className="py-2">{field}</td>
                      <td className="break-all p-2 text-danger">{show(values[0])}</td>
                      <td className="break-all p-2 text-success">{show(values[1])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {!selected.changes && <p className="text-text-muted">No field changes recorded.</p>}
            <p>IP: {selected.ip_address ?? '—'}</p>
            <p className="break-all">User agent: {selected.user_agent ?? '—'}</p>
            <h3 className="font-semibold">Metadata</h3>
            <pre className="overflow-auto rounded-lg bg-bg p-3">
              {JSON.stringify(selected.metadata, null, 2) ?? 'None'}
            </pre>
          </div>
        )}
      </Modal>
    </section>
  );
}
