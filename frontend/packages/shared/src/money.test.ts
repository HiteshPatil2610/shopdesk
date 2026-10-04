import { describe, expect, it } from 'vitest';

import { compareMoney, formatINR, isMoneyInput } from './money';

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

describe('isMoneyInput', () => {
  it.each(['0', '212', '212.5', '212.50', '9999999.99'])('accepts %s', (v) => {
    expect(isMoneyInput(v)).toBe(true);
  });
  it.each(['', '-1', '1.234', 'abc', '12345678', '1,000'])('rejects %s', (v) => {
    expect(isMoneyInput(v)).toBe(false);
  });
});

describe('compareMoney', () => {
  it.each([
    ['100', '99.99', 1],
    ['99.99', '100', -1],
    ['370.00', '370', 0],
    ['0.1', '0.10', 0],
    ['1450', '1500', -1],
    ['007', '7.00', 0],
  ] as const)('compareMoney(%s, %s) = %s', (a, b, expected) => {
    expect(compareMoney(a, b)).toBe(expected);
  });
});
