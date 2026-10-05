import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { AddUserModal } from './AddUserModal';

vi.mock('./api', () => ({ useCreateUser: () => ({ reset: vi.fn(), mutateAsync: vi.fn() }) }));
afterEach(cleanup);

it('shows and hides the typed password without changing it, and resets visibility on close', () => {
  const close = vi.fn();
  render(<AddUserModal open onClose={close} />);
  const password = screen.getByLabelText('Temporary password') as HTMLInputElement;
  fireEvent.change(password, { target: { value: 'example-password-01' } });
  expect(password.type).toBe('password');
  fireEvent.click(screen.getByRole('button', { name: 'Show password' }));
  expect(password.type).toBe('text');
  expect(password.value).toBe('example-password-01');
  fireEvent.click(screen.getByRole('button', { name: 'Hide password' }));
  expect(password.type).toBe('password');
  expect(screen.getByLabelText('Email (optional)')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  expect(close).toHaveBeenCalledOnce();
  expect(password.type).toBe('password');
});
