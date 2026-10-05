import { isMoneyInput, UNITS } from '@shopdesk/shared';
import { z } from 'zod';

const money = z.string().trim().refine(isMoneyInput, 'Enter an amount like 212 or 212.50');

const wholeNumber = z
  .string()
  .trim()
  .regex(/^\d{1,7}$/, 'Whole number');

// Mirrors backend core/schemas/products.py (ProductCreate / ProductUpdate).
export const productFormSchema = z
  .object({
    name: z.string().trim().min(2, 'At least 2 characters').max(150),
    category_id: z.string(),
    unit: z.enum(UNITS),
    barcode: z
      .string()
      .trim()
      .max(64)
      .regex(/^[A-Za-z0-9-]*$/, 'Letters, numbers and dashes only'),
    description: z.string().trim().max(2000),
    quantity: wholeNumber,
    reorder_level: wholeNumber,
    cost_price: money,
    mp_round_mode: z.enum(['primary', 'alternate']),
    market_price: z.string().trim(),
    selling_price: z.string().trim(),
    mp_manual: z.boolean(),
    sp_manual: z.boolean(),
  })
  .superRefine((v, ctx) => {
    if (v.mp_manual && !isMoneyInput(v.market_price)) {
      ctx.addIssue({ code: 'custom', path: ['market_price'], message: 'Enter a market price' });
    }
    if (v.sp_manual && !isMoneyInput(v.selling_price)) {
      ctx.addIssue({ code: 'custom', path: ['selling_price'], message: 'Enter a selling price' });
    }
  });

export type ProductFormValues = z.infer<typeof productFormSchema>;

export const emptyProductForm: ProductFormValues = {
  name: '',
  category_id: '',
  unit: 'pcs',
  barcode: '',
  description: '',
  quantity: '0',
  reorder_level: '5',
  cost_price: '',
  mp_round_mode: 'primary',
  market_price: '',
  selling_price: '',
  mp_manual: false,
  sp_manual: false,
};
