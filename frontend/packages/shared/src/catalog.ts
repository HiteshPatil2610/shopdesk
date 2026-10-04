/** Catalogue + pricing types shared by both apps (shapes match backend core/serializers.py). */

export type Page<T> = { items: T[]; page: number; page_size: number; total: number };

export type Category = { id: number; name: string; is_active: boolean };

export type MpMode = 'primary' | 'alternate';

/** Admin view — includes cost and margins. */
export type Product = {
  id: number;
  code: string;
  barcode: string | null;
  name: string;
  description: string | null;
  category: Category | null;
  unit: string;
  image_url: string | null;
  thumb_url: string | null;
  cost_price: string;
  market_price: string;
  selling_price: string;
  mp_is_manual: boolean;
  sp_is_manual: boolean;
  mp_round_mode: MpMode;
  mp_margin_pct: string | null;
  sp_margin_pct: string | null;
  quantity: number;
  reorder_level: number;
  low_stock: boolean;
  is_active: boolean;
  version: number;
  updated_by: string | null;
  created_at: string | null;
  updated_at: string | null;
};

/** Billing Counter view — no cost, no margins (BR-12). */
export type PosProduct = {
  id: number;
  code: string;
  barcode: string | null;
  name: string;
  unit: string;
  image_url: string | null;
  thumb_url: string | null;
  market_price: string;
  selling_price: string;
  quantity: number;
  low_stock: boolean;
};

export type MpOption = { mode: MpMode; value: string; step: string };

export type PricingPreview = {
  cost_price: string;
  raw_market_price: string;
  markup_pct: string;
  market_price: string;
  selling_price: string | null;
  mp_round_mode: MpMode;
  mp_options: MpOption[];
  mp_margin_pct: string | null;
  sp_margin_pct: string | null;
  explanation: string;
  manual_market_price?: boolean;
};

export type PricingSettings = {
  markup_low_pct: string;
  markup_high_pct: string;
  markup_threshold: string;
  small_mp_limit: string;
  small_mp_step: string;
  small_mp_alt_step: string;
  mp_step: string;
  mp_alt_step: string;
  sp_discount_pct: string;
  sp_step: string;
  sp_avoid_ten: boolean;
};

export const UNITS = [
  'pcs',
  'kg',
  'g',
  'l',
  'ml',
  'm',
  'box',
  'pack',
  'pair',
  'set',
  'dozen',
] as const;
