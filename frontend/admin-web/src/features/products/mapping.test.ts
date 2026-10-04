import { describe, expect, it } from 'vitest';

import { formToCreate, formToPatch } from './mapping';
import { emptyProductForm, productFormSchema } from './schema';

const base = { ...emptyProductForm, name: 'Steel bottle', cost_price: '212', quantity: '14' };

describe('formToCreate', () => {
  it('omits auto prices so the server calculates them', () => {
    const out = formToCreate({ ...base, market_price: '420.00', selling_price: '370.00' }, null);
    expect(out.market_price).toBeUndefined();
    expect(out.selling_price).toBeUndefined();
  });

  it('sends manual prices', () => {
    const out = formToCreate({ ...base, market_price: '450', mp_manual: true }, null);
    expect(out.market_price).toBe('450');
    expect(out.selling_price).toBeUndefined();
  });
});

describe('formToPatch', () => {
  it('keeps auto prices auto and clears empty category/barcode', () => {
    const patch = formToPatch(base, 3);
    expect(patch).toMatchObject({
      version: 3,
      mp_is_manual: false,
      sp_is_manual: false,
      clear_category: true,
      clear_barcode: true,
    });
    expect(patch).not.toHaveProperty('market_price');
  });

  it('sends typed prices as manual', () => {
    const patch = formToPatch({ ...base, sp_manual: true, selling_price: '399' }, 1);
    expect(patch.selling_price).toBe('399');
    expect(patch).not.toHaveProperty('sp_is_manual');
  });
});

describe('productFormSchema', () => {
  it('requires a manual price value when the field is manual', () => {
    const result = productFormSchema.safeParse({ ...base, mp_manual: true, market_price: '' });
    expect(result.success).toBe(false);
  });

  it('rejects a bad cost', () => {
    expect(productFormSchema.safeParse({ ...base, cost_price: '12.345' }).success).toBe(false);
  });
});
