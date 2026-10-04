/**
 * Money display helpers. The API sends money as strings ("300.00"); the UI only formats them.
 * Never do money arithmetic in the browser — totals come from the server (BR-5).
 */

const inr = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const DECIMAL_STRING = /^-?\d+(\.\d+)?$/;

/** "1234.5" → "₹1,234.50". Accepts the decimal strings the API returns. */
export function formatINR(value: string): string {
  const trimmed = value.trim();
  if (!DECIMAL_STRING.test(trimmed)) {
    throw new Error(`formatINR expects a decimal string, got ${JSON.stringify(value)}`);
  }
  // Intl formats decimal strings exactly (no float conversion).
  return inr.format(trimmed as Intl.StringNumericLiteral);
}
