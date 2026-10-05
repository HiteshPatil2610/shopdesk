import { Button, SelectField, TextField, apiErrorMessage } from '@shopdesk/shared';
import { useState } from 'react';
import { useFormContext } from 'react-hook-form';

import { useCategories, useCreateCategory } from './api';
import type { ProductFormValues } from './schema';

type Props = { mode: 'create' | 'edit' };

/** Name, category, unit, barcode, quantity, reorder level, description. */
export function ProductFields({ mode }: Props) {
  const {
    register,
    setValue,
    formState: { errors },
  } = useFormContext<ProductFormValues>();
  const categories = useCategories();
  const createCategory = useCreateCategory();
  const [newCategory, setNewCategory] = useState<string | null>(null);

  const categoryOptions = [
    { value: '', label: 'No category' },
    ...(categories.data ?? []).map((c) => ({ value: String(c.id), label: c.name })),
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="sm:col-span-2">
        <TextField label="Name *" error={errors.name?.message} {...register('name')} />
      </div>

      <div className="flex flex-col gap-1">
        <SelectField
          label="Category"
          options={categoryOptions}
          error={errors.category_id?.message}
          {...register('category_id')}
        />
        {newCategory === null ? (
          <button
            type="button"
            className="self-start text-xs text-primary"
            onClick={() => setNewCategory('')}
          >
            + New category
          </button>
        ) : (
          <div className="flex gap-2">
            <input
              aria-label="New category name"
              value={newCategory}
              onChange={(e) => setNewCategory(e.target.value)}
              className="h-8 flex-1 rounded-md border border-border bg-surface px-2 text-sm"
              placeholder="e.g. Kitchen"
            />
            <Button
              size="sm"
              disabled={newCategory.trim().length < 2 || createCategory.isPending}
              onClick={async () => {
                const created = await createCategory.mutateAsync(newCategory.trim());
                setValue('category_id', String(created.id));
                setNewCategory(null);
              }}
            >
              Add
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setNewCategory(null)}>
              Cancel
            </Button>
          </div>
        )}
        {createCategory.isError && (
          <p className="text-xs text-danger">{apiErrorMessage(createCategory.error)}</p>
        )}
      </div>

      <TextField
        label="Unit"
        readOnly
        hint="All products are counted in pieces (pcs)."
        {...register('unit')}
      />

      <TextField
        label="Barcode"
        hint="Optional. Scan it to fill"
        error={errors.barcode?.message}
        {...register('barcode')}
      />

      {mode === 'create' ? (
        <TextField
          label="Starting stock (pcs) *"
          hint="Pieces already in stock when you add this product. For example, enter 20 if you have 20 pieces; enter 0 if none."
          inputMode="numeric"
          error={errors.quantity?.message}
          {...register('quantity')}
        />
      ) : (
        <span className="hidden sm:block" />
      )}

      <TextField
        label="Low-stock alert at"
        inputMode="numeric"
        hint="Warn when stock is at or below this"
        error={errors.reorder_level?.message}
        {...register('reorder_level')}
      />

      <div className="flex flex-col gap-1 sm:col-span-2">
        <label htmlFor="description" className="text-sm font-medium">
          Description
        </label>
        <textarea
          id="description"
          rows={2}
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          {...register('description')}
        />
      </div>
    </div>
  );
}
