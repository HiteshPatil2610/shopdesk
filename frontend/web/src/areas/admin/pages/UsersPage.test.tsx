import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { UsersPage } from './UsersPage';
const mocks = vi.hoisted(() => ({ revoke: vi.fn(), refresh: vi.fn() }));
vi.mock('@shopdesk/shared', async (original) => ({
  ...(await original<typeof import('@shopdesk/shared')>()),
  useMe: () => ({ user: { id: 1, role: 'admin' } }),
}));
vi.mock('../features/users/AddUserModal', () => ({ AddUserModal: () => null }));
vi.mock('../features/users/ResetPasswordModal', () => ({ ResetPasswordModal: () => null }));
vi.mock('../features/users/api', () => ({
  useUsers: () => ({
    refetch: mocks.refresh,
    data: [
      {
        id: 2,
        full_name: '<img src=x onerror=alert(1)>',
        username: 'staff',
        email: null,
        role: 'cashier',
        is_active: true,
        last_seen_at: null,
      },
      {
        id: 3,
        full_name: 'Deleted staff',
        username: 'deleted',
        email: null,
        role: 'cashier',
        is_active: false,
        deleted_in_clerk: true,
        last_seen_at: null,
      },
    ],
  }),
  useUpdateUser: () => ({}),
  useSetActive: () => ({}),
  useRevokeSessions: () => ({ mutate: mocks.revoke, reset: vi.fn(), isPending: false }),
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
it('hides deleted staff by default and exposes their historical record without account actions', () => {
  render(<UsersPage />);
  expect(screen.queryByText('Deleted staff')).toBeNull();
  fireEvent.click(screen.getByRole('checkbox', { name: 'Show inactive and deleted accounts' }));
  expect(screen.getByText('Deleted staff')).toBeTruthy();
  expect(screen.getByText('Deleted in Clerk')).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Reactivate' })).toBeNull();
});
it('lets the admin refresh Clerk changes explicitly', () => {
  render(<UsersPage />);
  fireEvent.click(screen.getByRole('button', { name: 'Refresh from Clerk' }));
  expect(mocks.refresh).toHaveBeenCalledOnce();
});
it('renders hostile names as text and revokes only after confirmation', () => {
  const { container } = render(<UsersPage />);
  expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeTruthy();
  expect(container.querySelector('img')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Sign out all devices' }));
  expect(mocks.revoke).not.toHaveBeenCalled();
  const dialog = screen.getByRole('dialog');
  fireEvent.click(dialog.querySelector('button:not([data-close])') as HTMLButtonElement);
  expect(mocks.revoke).toHaveBeenCalledWith(
    2,
    expect.objectContaining({ onSuccess: expect.any(Function) }),
  );
});
