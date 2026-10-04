import {
  apiErrorMessage,
  Badge,
  Button,
  Modal,
  RoleBadge,
  Spinner,
  useMe,
  type Role,
  type UserPublic,
} from '@shopdesk/shared';
import { useState } from 'react';

import { useSetActive, useUpdateUser, useUsers, type AdminUser } from '../features/users/api';
import { AddUserModal } from '../features/users/AddUserModal';
import { ResetPasswordModal } from '../features/users/ResetPasswordModal';

const lastSeen = (iso: string | null) =>
  iso
    ? new Date(iso).toLocaleString('en-IN', {
        dateStyle: 'medium',
        timeStyle: 'short',
        timeZone: 'Asia/Kolkata',
      })
    : 'Never';

export function UsersPage() {
  const { user: me } = useMe();
  const users = useUsers();
  const updateUser = useUpdateUser();
  const setActive = useSetActive();
  const [adding, setAdding] = useState(false);
  const [details, setDetails] = useState<AdminUser | null>(null);
  const [resetting, setResetting] = useState<UserPublic | null>(null);
  const [confirming, setConfirming] = useState<UserPublic | null>(null);
  const actionError = updateUser.error ?? setActive.error;

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Users</h1>
          <p className="text-sm text-text-muted">
            Staff accounts for both apps. Cashiers can only use the Billing Counter.
          </p>
        </div>
        <Button onClick={() => setAdding(true)}>+ Add user</Button>
      </div>

      {actionError && (
        <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
          {apiErrorMessage(actionError)}
        </p>
      )}

      <div className="overflow-x-auto rounded-xl border border-border bg-surface">
        {users.isPending ? (
          <div className="flex justify-center p-10">
            <Spinner label="Loading users" />
          </div>
        ) : users.isError ? (
          <div className="p-8 text-center text-danger">{apiErrorMessage(users.error)}</div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-text-muted uppercase">
              <tr>
                <th className="px-4 py-3">User</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Last seen</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.data.map((u) => {
                const isMe = u.id === me.id;
                return (
                  <tr key={u.id} className="border-b border-border last:border-0">
                    <td className="px-4 py-3">
                      <p className="font-medium">
                        {u.full_name} {isMe && <span className="text-text-muted">(you)</span>}
                      </p>
                      <p className="font-mono text-xs text-text-muted">
                        Username: {u.username ?? 'Not provided'}
                      </p>
                      <p className="text-xs text-text-muted">Email: {u.email ?? 'Not provided'}</p>
                    </td>
                    <td className="px-4 py-3">
                      {isMe ? (
                        <RoleBadge role={u.role} />
                      ) : (
                        <select
                          aria-label={`Role for ${u.full_name}`}
                          value={u.role}
                          disabled={updateUser.isPending}
                          onChange={(e) =>
                            updateUser.mutate({ id: u.id, role: e.target.value as Role })
                          }
                          className="h-8 rounded-md border border-border bg-surface px-2 text-sm"
                        >
                          <option value="cashier">cashier</option>
                          <option value="manager">manager</option>
                          <option value="admin">admin</option>
                        </select>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {u.is_active ? (
                        <Badge tone="success">Active</Badge>
                      ) : (
                        <Badge tone="danger">Deactivated</Badge>
                      )}
                    </td>
                    <td className="px-4 py-3 text-text-muted">{lastSeen(u.last_seen_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-2">
                        <Button size="sm" variant="secondary" onClick={() => setDetails(u)}>
                          View details
                        </Button>
                        <Button size="sm" variant="secondary" onClick={() => setResetting(u)}>
                          Reset password
                        </Button>
                        {!isMe &&
                          (u.is_active ? (
                            <Button size="sm" variant="danger" onClick={() => setConfirming(u)}>
                              Deactivate
                            </Button>
                          ) : (
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() => setActive.mutate({ id: u.id, active: true })}
                            >
                              Reactivate
                            </Button>
                          ))}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <AddUserModal open={adding} onClose={() => setAdding(false)} />
      <Modal open={details !== null} title="User details" onClose={() => setDetails(null)}>
        {details && (
          <div className="flex flex-col gap-4 text-sm">
            <dl className="grid grid-cols-[auto_1fr] gap-x-5 gap-y-3">
              {[
                ['Full name', details.full_name],
                ['Username', details.username ?? 'Not provided'],
                ['Email', details.email ?? 'Not provided'],
                ['Role', details.role],
                ['Status', details.is_active ? 'Active' : 'Deactivated'],
                [
                  'App access',
                  details.role === 'cashier'
                    ? 'Billing Counter'
                    : 'Admin Console and Billing Counter',
                ],
                ['User ID', String(details.id)],
                ['Clerk account ID', details.clerk_user_id],
                [
                  'Added to ShopDesk (IST)',
                  details.created_at ? lastSeen(details.created_at) : 'Not available',
                ],
                [
                  'Updated in ShopDesk (IST)',
                  details.updated_at ? lastSeen(details.updated_at) : 'Not available',
                ],
                ['Last seen (IST)', lastSeen(details.last_seen_at)],
              ].map(([label, value]) => (
                <div key={label} className="contents">
                  <dt className="text-text-muted">{label}</dt>
                  <dd className="break-all font-medium">{value}</dd>
                </div>
              ))}
            </dl>
            <p className="rounded-lg bg-bg p-3 text-text-muted">
              Passwords are managed by Clerk and cannot be viewed. Use Reset password to set a new
              one. These are the current account details; email may be absent for accounts created
              with only a username.
            </p>
          </div>
        )}
      </Modal>
      <ResetPasswordModal user={resetting} onClose={() => setResetting(null)} />
      <Modal
        open={confirming !== null}
        title="Deactivate account?"
        size="sm"
        onClose={() => setConfirming(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirming(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                if (confirming) setActive.mutate({ id: confirming.id, active: false });
                setConfirming(null);
              }}
            >
              Deactivate
            </Button>
          </>
        }
      >
        <p className="text-sm">
          <strong>{confirming?.full_name}</strong> will be signed out everywhere and won't be able
          to sign in until reactivated. Their past orders stay in the records.
        </p>
      </Modal>
    </section>
  );
}
