export type CartItem = { code: string; qty: number; name: string; available: number };
export type Cart = { items: CartItem[]; discount: boolean; name: string; phone: string };
export type Action =
  | { type: 'ADD'; item: CartItem }
  | { type: 'SET_QTY'; code: string; qty: number }
  | { type: 'REMOVE'; code: string }
  | { type: 'TOGGLE_DISCOUNT' }
  | { type: 'SET_CUSTOMER'; name: string; phone: string }
  | { type: 'RESET' };
export const emptyCart: Cart = { items: [], discount: false, name: '', phone: '' };
export const storageKey = 'sd_pos_cart';

export function cartReducer(state: Cart, action: Action): Cart {
  switch (action.type) {
    case 'ADD': {
      const existing = state.items.find((item) => item.code === action.item.code);
      const qty = (existing?.qty ?? 0) + action.item.qty;
      if (!Number.isInteger(qty) || qty < 1 || qty > Math.min(action.item.available, 10000))
        return state;
      if (!existing && state.items.length >= 100) return state;
      return {
        ...state,
        items: existing
          ? state.items.map((item) =>
              item.code === action.item.code ? { ...action.item, qty } : item,
            )
          : [...state.items, action.item],
      };
    }
    case 'SET_QTY':
      return {
        ...state,
        items: state.items.map((item) =>
          item.code === action.code &&
          Number.isInteger(action.qty) &&
          action.qty >= 1 &&
          action.qty <= Math.min(item.available, 10000)
            ? { ...item, qty: action.qty }
            : item,
        ),
      };
    case 'REMOVE':
      return { ...state, items: state.items.filter((item) => item.code !== action.code) };
    case 'TOGGLE_DISCOUNT':
      return { ...state, discount: !state.discount };
    case 'SET_CUSTOMER':
      return { ...state, name: action.name, phone: action.phone };
    case 'RESET':
      return { ...emptyCart, items: [] };
  }
}

export function loadCart(): Cart {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(storageKey) ?? 'null');
    if (!value || typeof value !== 'object') return emptyCart;
    const data = value as Partial<Cart>;
    if (
      typeof data.name !== 'string' ||
      typeof data.phone !== 'string' ||
      typeof data.discount !== 'boolean' ||
      !Array.isArray(data.items) ||
      data.items.length > 100
    )
      return emptyCart;
    if (
      !data.items.every(
        (item) =>
          item &&
          typeof item.code === 'string' &&
          item.code.length <= 20 &&
          typeof item.name === 'string' &&
          Number.isInteger(item.qty) &&
          item.qty >= 1 &&
          item.qty <= 10000 &&
          Number.isInteger(item.available) &&
          item.available >= 0,
      )
    )
      return emptyCart;
    // Prices and quotes are never persisted or trusted on restore.
    return {
      name: data.name.slice(0, 120),
      phone: data.phone.slice(0, 10),
      discount: data.discount,
      items: data.items.map(({ code, qty, name, available }) => ({ code, qty, name, available })),
    };
  } catch {
    return emptyCart;
  }
}

export function isScan(times: number[], enteredAt = times.at(-1) ?? 0): boolean {
  return (
    times.length >= 3 &&
    enteredAt - (times.at(-1) ?? 0) < 50 &&
    times.slice(1).every((time, i) => time - (times[i] ?? time) < 50)
  );
}

export function validCustomer(name: string, phone: string): boolean {
  return (
    name.trim().length >= 2 && name.trim().length <= 120 && (!phone || /^[6-9]\d{9}$/.test(phone))
  );
}
