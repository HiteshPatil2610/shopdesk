import { describe, expect, it } from 'vitest';

import { formatINR } from './money';

describe('formatINR', () => {
  it.each([
    ['1234.5', '₹1,234.50'],
    ['300.00', '₹300.00'],
    ['0', '₹0.00'],
    ['1499', '₹1,499.00'],
    ['12345678.9', '₹1,23,45,678.90'],
    ['0.005', '₹0.01'],
  ])('formats %s as %s', (input, expected) => {
    expect(formatINR(input)).toBe(expected);
  });

  it('rejects non-decimal input', () => {
    expect(() => formatINR('abc')).toThrow();
    expect(() => formatINR('1,000')).toThrow();
  });
});
