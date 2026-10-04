/**
 * Money display helpers. The API sends money as strings ("300.00"); the UI only formats and
 * compares them. Never do money arithmetic in the browser — totals come from the server (BR-5).
 */

const inr = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const DECIMAL_STRING = /^-?\d+(\.\d+)?$/;
const MONEY_INPUT = /^\d{1,7}(\.\d{1,2})?$/;

/** "1234.5" → "₹1,234.50". Accepts the decimal strings the API returns. */
export function formatINR(value: string): string {
  const trimmed = value.trim();
  if (!DECIMAL_STRING.test(trimmed)) {
    throw new Error(`formatINR expects a decimal string, got ${JSON.stringify(value)}`);
  }
  // Intl formats decimal strings exactly (no float conversion).
  return inr.format(trimmed as Intl.StringNumericLiteral);
}

/** True for what a user may type into a money field: up to 7 digits and 2 decimals. */
export function isMoneyInput(value: string): boolean {
  return MONEY_INPUT.test(value.trim());
}

/** Exact comparison of non-negative decimal strings (no floats): -1, 0 or 1. */
export function compareMoney(a: string, b: string): -1 | 0 | 1 {
  const [ai = '0', af = ''] = a.trim().split('.');
  const [bi = '0', bf = ''] = b.trim().split('.');
  const intA = ai.replace(/^0+(?=\d)/, '');
  const intB = bi.replace(/^0+(?=\d)/, '');
  if (intA.length !== intB.length) return intA.length < intB.length ? -1 : 1;
  if (intA !== intB) return intA < intB ? -1 : 1;
  const fracA = af.padEnd(2, '0');
  const fracB = bf.padEnd(2, '0');
  if (fracA === fracB) return 0;
  return fracA < fracB ? -1 : 1;
}
