import { afterEach, expect, it } from 'vitest';
import { cartReducer, emptyCart, isScan, loadCart, storageKey, validCustomer } from './cart';
afterEach(() => sessionStorage.clear());
it('merges duplicate codes, bounds quantities and resets customer details', () => {
  const item = { code: 'P00042', name: 'Bottle', available: 14, qty: 2 };
  let cart = cartReducer(emptyCart, { type: 'ADD', item });
  cart = cartReducer(cart, { type: 'ADD', item: { ...item, qty: 3 } });
  expect(cart.items).toHaveLength(1);
  expect(cart.items[0]?.qty).toBe(5);
  expect(cartReducer(cart, { type: 'ADD', item: { ...item, qty: 20 } })).toBe(cart);
  expect(cartReducer(cart, { type: 'SET_QTY', code: item.code, qty: 20 }).items[0]?.qty).toBe(5);
  cart = cartReducer(cart, { type: 'SET_CUSTOMER', name: 'Test Buyer', phone: '9876543210' });
  cart = cartReducer(cart, { type: 'TOGGLE_DISCOUNT' });
  sessionStorage.setItem(storageKey, JSON.stringify({ ...cart, total: '1.00' }));
  expect(loadCart()).toEqual(cart);
  expect(cartReducer(cart, { type: 'REMOVE', code: item.code }).items).toEqual([]);
  expect(cartReducer(cart, { type: 'RESET' })).toEqual(emptyCart);
});
it('discards corrupt drafts and distinguishes scans and customer validity', () => {
  sessionStorage.setItem(storageKey, '{oops');
  expect(loadCart()).toEqual(emptyCart);
  expect(isScan([0, 10, 30])).toBe(true);
  expect(isScan([0, 60, 100])).toBe(false);
  expect(validCustomer('A', '')).toBe(false);
  expect(validCustomer('Test', '1234567890')).toBe(false);
  expect(validCustomer('Test', '9876543210')).toBe(true);
});

it('treats a slow Enter after fast typing as manual entry, not a scan', () => {
  expect(isScan([0, 10, 30], 40)).toBe(true);
  expect(isScan([0, 10, 30], 600)).toBe(false);
});
