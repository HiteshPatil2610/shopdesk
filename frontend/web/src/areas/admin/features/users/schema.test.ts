import { describe, expect, it } from 'vitest';

import { newUserSchema } from './schema';

const valid = {
  username: 'priya',
  full_name: 'Priya Shah',
  role: 'cashier',
  password: 'counter-pass-01',
};

describe('newUserSchema (mirrors backend UserCreate)', () => {
  it('accepts a valid cashier', () => {
    expect(newUserSchema.safeParse(valid).success).toBe(true);
  });

  it.each([
    [{ username: 'ab' }, 'username'],
    [{ username: 'bad name!' }, 'username'],
    [{ password: 'short' }, 'password'],
    [{ role: 'boss' }, 'role'],
    [{ username: 'priya1234', password: 'PRIYA1234' }, 'password'],
  ])('rejects %o', (patch, field) => {
    const result = newUserSchema.safeParse({ ...valid, ...patch });
    expect(result.success).toBe(false);
    expect(result.error?.issues.map((i) => i.path[0])).toContain(field);
  });
});
