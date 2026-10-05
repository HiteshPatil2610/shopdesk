import type { Product } from '@shopdesk/shared';

import type { ProductCreateInput, ProductPatch } from './api';
import type { ProductFormValues } from './schema';

/** Form values for editing an existing product. */
export function productToForm(p: Product): ProductFormValues {
  return {
    name: p.name,
    category_id: p.category ? String(p.category.id) : '',
    unit: 'pcs',
    barcode: p.barcode ?? '',
    description: p.description ?? '',
    quantity: String(p.quantity),
    reorder_level: String(p.reorder_level),
    cost_price: p.cost_price,
    mp_round_mode: p.mp_round_mode,
    market_price: p.market_price,
    selling_price: p.selling_price,
    mp_manual: p.mp_is_manual,
    sp_manual: p.sp_is_manual,
  };
}

/** Create payload: auto prices are NOT sent (the server calculates them). */
export function formToCreate(v: ProductFormValues, image: Blob | null): ProductCreateInput {
  return {
    name: v.name,
    category_id: v.category_id,
    unit: v.unit,
    barcode: v.barcode,
    description: v.description,
    quantity: v.quantity,
    reorder_level: v.reorder_level,
    cost_price: v.cost_price,
    mp_round_mode: v.mp_round_mode,
    market_price: v.mp_manual ? v.market_price : undefined,
    selling_price: v.sp_manual ? v.selling_price : undefined,
    image,
  };
}

/** PATCH payload: a typed price marks it manual; otherwise ask the server to keep it auto. */
export function formToPatch(v: ProductFormValues, version: number): ProductPatch {
  const patch: ProductPatch = {
    version,
    name: v.name,
    unit: v.unit,
    description: v.description,
    reorder_level: Number(v.reorder_level),
    cost_price: v.cost_price,
    mp_round_mode: v.mp_round_mode,
  };
  if (v.category_id) patch.category_id = Number(v.category_id);
  else patch.clear_category = true;
  if (v.barcode) patch.barcode = v.barcode;
  else patch.clear_barcode = true;
  if (v.mp_manual) patch.market_price = v.market_price;
  else patch.mp_is_manual = false;
  if (v.sp_manual) patch.selling_price = v.selling_price;
  else patch.sp_is_manual = false;
  return patch;
}
