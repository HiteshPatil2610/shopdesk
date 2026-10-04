import { Badge, compareMoney, formatINR, isMoneyInput, Spinner } from '@shopdesk/shared';
import { useEffect } from 'react';
import { useFormContext } from 'react-hook-form';

import { useDebounced } from '../../lib/useDebounced';
import { usePricingPreview } from './api';
import type { ProductFormValues } from './schema';

const inputCls =
  'h-11 w-full rounded-lg border border-border bg-surface pr-3 pl-7 text-base tabular-nums focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none aria-[invalid=true]:border-danger';

function MoneyInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className="relative">
      <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-text-muted">
        ₹
      </span>
      <input inputMode="decimal" autoComplete="off" className={inputCls} {...props} />
    </div>
  );
}

/** Cost → live MP/SP preview from the server, MP rounding choice, manual overrides (spec 04 §8). */
export function PriceSection() {
  const {
    register,
    watch,
    setValue,
    formState: { errors },
  } = useFormContext<ProductFormValues>();
  const [cost, mode, mp, sp, mpManual, spManual] = watch([
    'cost_price',
    'mp_round_mode',
    'market_price',
    'selling_price',
    'mp_manual',
    'sp_manual',
  ]);

  const debouncedCost = useDebounced(isMoneyInput(cost) ? cost.trim() : null);
  const debouncedManualMp = useDebounced(mpManual && isMoneyInput(mp) ? mp.trim() : null);
  const preview = usePricingPreview({
    cost: debouncedCost,
    mode,
    manualMp: debouncedManualMp,
  });

  // Fill auto prices from the server preview; never overwrite a hand-typed price.
  useEffect(() => {
    const data = preview.data;
    if (!data || debouncedCost === null) return;
    if (!mpManual) setValue('market_price', data.market_price, { shouldValidate: true });
    if (!spManual && data.selling_price) {
      setValue('selling_price', data.selling_price, { shouldValidate: true });
    }
  }, [preview.data, mpManual, spManual, setValue, debouncedCost]);

  const mpField = register('market_price');
  const spField = register('selling_price');

  const warning =
    isMoneyInput(cost) && isMoneyInput(sp) && compareMoney(sp, cost) < 0
      ? `Selling price is below cost (${formatINR(cost)})`
      : isMoneyInput(sp) && isMoneyInput(mp) && compareMoney(sp, mp) > 0
        ? 'Selling price is above market price'
        : null;

  return (
    <fieldset className="flex flex-col gap-4 rounded-xl border border-border p-4">
      <legend className="px-1 text-sm font-semibold tracking-wide text-text-muted uppercase">
        Pricing
      </legend>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="flex flex-col gap-1">
          <label htmlFor="cost_price" className="text-sm font-medium">
            Cost price *
          </label>
          <MoneyInput
            id="cost_price"
            placeholder="0.00"
            aria-invalid={Boolean(errors.cost_price)}
            {...register('cost_price')}
          />
          {errors.cost_price && <p className="text-xs text-danger">{errors.cost_price.message}</p>}
        </div>

        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <label htmlFor="market_price" className="text-sm font-medium">
              Market price (MP)
            </label>
            {mpManual ? (
              <button
                type="button"
                className="text-xs"
                onClick={() => setValue('mp_manual', false)}
                title="Go back to the automatic price"
              >
                <Badge tone="warning">manual ✕</Badge>
              </button>
            ) : (
              <Badge>auto</Badge>
            )}
          </div>
          <MoneyInput
            id="market_price"
            aria-invalid={Boolean(errors.market_price)}
            {...mpField}
            onChange={(e) => {
              setValue('mp_manual', true);
              void mpField.onChange(e);
            }}
          />
          {errors.market_price && (
            <p className="text-xs text-danger">{errors.market_price.message}</p>
          )}
        </div>

        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <label htmlFor="selling_price" className="text-sm font-medium">
              Selling price (SP)
            </label>
            {spManual ? (
              <button
                type="button"
                className="text-xs"
                onClick={() => setValue('sp_manual', false)}
                title="Go back to the automatic price"
              >
                <Badge tone="warning">manual ✕</Badge>
              </button>
            ) : (
              <Badge>auto</Badge>
            )}
          </div>
          <MoneyInput
            id="selling_price"
            aria-invalid={Boolean(errors.selling_price)}
            {...spField}
            onChange={(e) => {
              setValue('sp_manual', true);
              void spField.onChange(e);
            }}
          />
          {errors.selling_price && (
            <p className="text-xs text-danger">{errors.selling_price.message}</p>
          )}
        </div>
      </div>

      {preview.data && debouncedCost !== null && (
        <div className="flex flex-col gap-3">
          <div
            role="radiogroup"
            aria-label="Market price rounding"
            className="flex flex-wrap gap-2"
          >
            <span className="self-center text-sm text-text-muted">Round MP to:</span>
            {preview.data.mp_options.map((option) => {
              const selected = !mpManual && mode === option.mode;
              return (
                <button
                  key={option.mode}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => {
                    setValue('mp_round_mode', option.mode);
                    setValue('mp_manual', false);
                  }}
                  className={`rounded-lg border px-3 py-1.5 text-sm tabular-nums ${
                    selected
                      ? 'border-primary bg-primary/10 font-semibold text-primary'
                      : 'border-border hover:bg-bg'
                  }`}
                >
                  {formatINR(option.value)}
                  <span className="ml-1 text-xs text-text-muted">
                    (next ₹{Number(option.step).toString()})
                  </span>
                </button>
              );
            })}
            {preview.isFetching && <Spinner label="Updating prices" className="text-text-muted" />}
          </div>
          <p className="text-xs text-text-muted">
            {preview.data.explanation}
            {preview.data.mp_margin_pct && <> · Margin at MP {preview.data.mp_margin_pct}%</>}
            {!spManual && preview.data.sp_margin_pct && <> · at SP {preview.data.sp_margin_pct}%</>}
          </p>
        </div>
      )}

      {warning && (
        <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
          ⚠ {warning}. Rule: cost ≤ SP ≤ MP.
        </p>
      )}
    </fieldset>
  );
}
