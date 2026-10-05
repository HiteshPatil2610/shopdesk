import {
  apiErrorMessage,
  Button,
  formatINR,
  isMoneyInput,
  Modal,
  Spinner,
  type PricingSettings,
} from '@shopdesk/shared';
import { useState } from 'react';

import {
  useApplyPricing,
  useExamples,
  usePricingSettings,
  useSavePricingSettings,
  type ApplyResult,
} from '../features/pricing/api';
import { useDebounced } from '../lib/useDebounced';

const EXAMPLE_COSTS = ['20', '99', '212', '499', '500', '650', '700', '743', '1499'];

type FieldDef = {
  key: Exclude<keyof PricingSettings, 'sp_avoid_ten'>;
  label: string;
  suffix: string;
};

const GROUPS: { title: string; fields: FieldDef[] }[] = [
  {
    title: 'Market price markup',
    fields: [
      { key: 'markup_low_pct', label: 'Markup when cost is below the threshold', suffix: '%' },
      { key: 'markup_high_pct', label: 'Markup when cost is at/above the threshold', suffix: '%' },
      { key: 'markup_threshold', label: 'Cost threshold', suffix: '₹' },
    ],
  },
  {
    title: 'Market price rounding (always up)',
    fields: [
      { key: 'mp_step', label: 'Default: round up to the next', suffix: '₹' },
      { key: 'mp_alt_step', label: 'Bigger option: round up to the next', suffix: '₹' },
      {
        key: 'small_mp_limit',
        label: 'Small prices: below this MP use smaller steps',
        suffix: '₹',
      },
      { key: 'small_mp_step', label: 'Small prices: default step', suffix: '₹' },
      { key: 'small_mp_alt_step', label: 'Small prices: bigger option', suffix: '₹' },
    ],
  },
  {
    title: 'Selling price (discount)',
    fields: [
      { key: 'sp_discount_pct', label: 'SP = MP minus', suffix: '%' },
      { key: 'sp_step', label: 'Then round down to the nearest', suffix: '₹' },
    ],
  },
];

export function PricingSettingsPage() {
  const settings = usePricingSettings();
  if (settings.isPending) {
    return (
      <div className="flex justify-center p-16">
        <Spinner label="Loading pricing rules" />
      </div>
    );
  }
  if (settings.isError) {
    return <p className="p-8 text-center text-danger">{apiErrorMessage(settings.error)}</p>;
  }
  return <PricingRulesEditor saved={settings.data} />;
}

function PricingRulesEditor({ saved }: { saved: PricingSettings }) {
  const save = useSavePricingSettings();
  const apply = useApplyPricing();
  const [draft, setDraft] = useState<PricingSettings>(saved);
  const [dryRun, setDryRun] = useState<ApplyResult | null>(null);

  const valid = Object.values(draft).every((v) => typeof v === 'boolean' || isMoneyInput(v));
  const debouncedDraft = useDebounced(valid ? draft : null, 400);
  const examples = useExamples(EXAMPLE_COSTS, debouncedDraft);
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved);

  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Pricing rules</h1>
          <p className="text-sm text-text-muted">
            How new prices are worked out from the cost. Saving doesn't change existing products
            until you click “Apply to products”.
          </p>
        </div>
        <Button
          variant="secondary"
          disabled={dirty || apply.isPending}
          title={dirty ? 'Save your changes first' : undefined}
          onClick={async () => setDryRun(await apply.mutateAsync(true))}
        >
          Apply to products…
        </Button>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_1fr]">
        <form
          className="flex flex-col gap-5 min-w-0 rounded-xl border border-border bg-surface p-5"
          onSubmit={(e) => {
            e.preventDefault();
            if (valid) save.mutate(draft);
          }}
        >
          {GROUPS.map((group) => (
            <fieldset key={group.title} className="flex flex-col gap-3">
              <legend className="mb-1 text-sm font-semibold tracking-wide text-text-muted uppercase">
                {group.title}
              </legend>
              {group.title === 'Market price markup' && (
                <p className="text-xs text-text-muted">
                  Prices are smoothed at the threshold so the lower markup never causes a price
                  drop. With the default rules, cost ₹500 gives MP ₹1,000.
                </p>
              )}
              {group.fields.map((f) => (
                <label key={f.key} className="flex items-center justify-between gap-3 text-sm">
                  <span>{f.label}</span>
                  <span className="flex items-center gap-1">
                    {f.suffix === '₹' && <span className="text-text-muted">₹</span>}
                    <input
                      inputMode="decimal"
                      value={draft[f.key]}
                      aria-invalid={!isMoneyInput(draft[f.key])}
                      onChange={(e) => setDraft({ ...draft, [f.key]: e.target.value })}
                      className="h-9 w-24 rounded-md border border-border bg-surface px-2 text-right tabular-nums aria-[invalid=true]:border-danger"
                    />
                    {f.suffix === '%' && <span className="text-text-muted">%</span>}
                  </span>
                </label>
              ))}
              {group.title === 'Selling price (discount)' && (
                <label className="flex items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={draft.sp_avoid_ten}
                    onChange={(e) => setDraft({ ...draft, sp_avoid_ten: e.target.checked })}
                    className="mt-1"
                  />
                  <span>
                    If the rounded SP ends in 10, drop it to 00
                    <span className="block text-xs text-text-muted">
                      ₹1,212 → ₹1,200; ₹1,293 → ₹1,290. Applies from ₹100 upward; SP stays at or
                      above cost.
                    </span>
                  </span>
                </label>
              )}
            </fieldset>
          ))}
          {save.isError && (
            <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
              {apiErrorMessage(save.error)}
            </p>
          )}
          {save.isSuccess && !dirty && (
            <p role="status" className="text-sm text-success">
              ✓ Saved
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" disabled={!dirty} onClick={() => setDraft(saved)}>
              Reset
            </Button>
            <Button type="submit" disabled={!dirty || !valid || save.isPending}>
              {save.isPending ? 'Saving…' : 'Save rules'}
            </Button>
          </div>
        </form>

        <div className="min-w-0 rounded-xl border border-border bg-surface p-5">
          <h2 className="mb-3 flex items-center gap-2 font-semibold">
            Examples {dirty && <span className="text-xs font-normal text-warning">(unsaved)</span>}
            {examples.isFetching && <Spinner label="Updating" className="text-text-muted" />}
          </h2>
          {examples.isError ? (
            <p className="text-sm text-danger">{apiErrorMessage(examples.error)}</p>
          ) : (
            <div className="min-w-0 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs text-text-muted uppercase">
                  <tr>
                    <th className="py-2 text-left">Cost</th>
                    <th className="py-2 text-right">MP</th>
                    <th className="py-2 text-right">Bigger MP</th>
                    <th className="py-2 text-right">SP</th>
                  </tr>
                </thead>
                <tbody>
                  {(examples.data ?? []).map((ex) => (
                    <tr key={ex.cost_price} className="border-t border-border tabular-nums">
                      <td className="py-2">{formatINR(ex.cost_price)}</td>
                      <td className="py-2 text-right font-medium">{formatINR(ex.market_price)}</td>
                      <td className="py-2 text-right text-text-muted">
                        {ex.mp_options[1] ? formatINR(ex.mp_options[1].value) : '—'}
                      </td>
                      <td className="py-2 text-right">
                        {ex.selling_price ? formatINR(ex.selling_price) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <Modal
        open={dryRun !== null}
        title="Apply pricing rules to products?"
        onClose={() => setDryRun(null)}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setDryRun(null)}>
              Cancel
            </Button>
            <Button
              disabled={!dryRun?.affected || apply.isPending}
              onClick={async () => {
                await apply.mutateAsync(false);
                setDryRun(null);
              }}
            >
              {apply.isPending ? 'Applying…' : `Reprice ${dryRun?.affected ?? 0} product(s)`}
            </Button>
          </>
        }
      >
        {dryRun && dryRun.affected === 0 ? (
          <p className="text-sm">All products already match the current rules.</p>
        ) : (
          <div className="flex flex-col gap-3 text-sm">
            <p>
              <strong>{dryRun?.affected}</strong> active product(s) will get new automatic prices.
              Hand-set (manual) prices are kept.
            </p>
            <div className="min-w-0 overflow-x-auto">
              <table className="w-full">
                <thead className="text-xs text-text-muted uppercase">
                  <tr>
                    <th className="py-1 text-left">Product</th>
                    <th className="py-1 text-right">MP</th>
                    <th className="py-1 text-right">SP</th>
                  </tr>
                </thead>
                <tbody>
                  {dryRun?.sample.map((s) => (
                    <tr key={s.id} className="border-t border-border tabular-nums">
                      <td className="py-1">
                        <span className="font-mono text-xs">{s.code}</span> {s.name}
                      </td>
                      <td className="py-1 text-right">
                        {s.changes.market_price
                          ? `${s.changes.market_price[0]} → ${s.changes.market_price[1]}`
                          : '—'}
                      </td>
                      <td className="py-1 text-right">
                        {s.changes.selling_price
                          ? `${s.changes.selling_price[0]} → ${s.changes.selling_price[1]}`
                          : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {(dryRun?.affected ?? 0) > (dryRun?.sample.length ?? 0) && (
              <p className="text-xs text-text-muted">Showing the first {dryRun?.sample.length}.</p>
            )}
          </div>
        )}
      </Modal>
    </section>
  );
}
