import { apiErrorMessage, Button, Modal, type Product } from '@shopdesk/shared';
import { useState } from 'react';

import { useAdjustStock, type AdjustInput } from './api';

const TYPES: { value: AdjustInput['type']; label: string; hint: string }[] = [
  { value: 'restock', label: 'Restock (+)', hint: 'New stock arrived' },
  { value: 'damage', label: 'Damage / loss (−)', hint: 'Broken, expired or missing' },
  { value: 'correction', label: 'Correction (±)', hint: 'Fix the count after a recount' },
];

type Props = { product: Product | null; onClose: () => void };

/** Every quantity change goes through here so the ledger explains it (H5, OS-3). */
export function StockAdjustModal({ product, onClose }: Props) {
  return product ? <AdjustForm key={product.id} product={product} onClose={onClose} /> : null;
}

function AdjustForm({ product, onClose }: { product: Product; onClose: () => void }) {
  const adjust = useAdjustStock(product.id);
  const [type, setType] = useState<AdjustInput['type']>('restock');
  const [qtyText, setQtyText] = useState('');
  const [note, setNote] = useState('');

  const qty = /^-?\d{1,7}$/.test(qtyText.trim()) ? Number(qtyText.trim()) : null;
  const change =
    qty === null
      ? null
      : type === 'damage'
        ? -Math.abs(qty)
        : type === 'restock'
          ? Math.abs(qty)
          : qty;
  const after = change === null ? null : product.quantity + change;
  const needsNote = type !== 'restock';
  const valid =
    change !== null &&
    change !== 0 &&
    after !== null &&
    after >= 0 &&
    (!needsNote || note.trim().length > 0);

  return (
    <Modal
      open
      title={`Adjust stock · ${product.code} ${product.name}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="stock-adjust-form" disabled={!valid || adjust.isPending}>
            {adjust.isPending ? 'Saving…' : 'Save adjustment'}
          </Button>
        </>
      }
    >
      <form
        id="stock-adjust-form"
        className="flex flex-col gap-4"
        onSubmit={async (e) => {
          e.preventDefault();
          if (!valid || qty === null) return;
          await adjust.mutateAsync({
            type,
            qty: type === 'correction' ? qty : Math.abs(qty),
            note: note.trim() || undefined,
          });
          onClose();
        }}
      >
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-medium">Type</legend>
          {TYPES.map((t) => (
            <label key={t.value} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="adjust-type"
                checked={type === t.value}
                onChange={() => setType(t.value)}
              />
              <span className="font-medium">{t.label}</span>
              <span className="text-text-muted">· {t.hint}</span>
            </label>
          ))}
        </fieldset>
        <label className="flex flex-col gap-1 text-sm font-medium">
          {type === 'correction' ? 'Change (use − to reduce, e.g. -2)' : 'Quantity'}
          <input
            inputMode="numeric"
            value={qtyText}
            onChange={(e) => setQtyText(e.target.value)}
            className="h-10 rounded-lg border border-border bg-surface px-3 tabular-nums"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Note {needsNote ? '(required)' : '(optional)'}
          <input
            value={note}
            maxLength={255}
            onChange={(e) => setNote(e.target.value)}
            className="h-10 rounded-lg border border-border bg-surface px-3"
            placeholder={needsNote ? 'What happened?' : 'e.g. supplier invoice no.'}
          />
        </label>
        <p className="rounded-lg bg-bg px-3 py-2 text-sm tabular-nums">
          Stock: <strong>{product.quantity}</strong> →{' '}
          <strong className={after !== null && after < 0 ? 'text-danger' : ''}>
            {after ?? '?'}
          </strong>{' '}
          {product.unit}
          {after !== null && after < 0 && <span className="text-danger"> · can't go below 0</span>}
        </p>
        {adjust.isError && (
          <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
            {apiErrorMessage(adjust.error)}
          </p>
        )}
      </form>
    </Modal>
  );
}
