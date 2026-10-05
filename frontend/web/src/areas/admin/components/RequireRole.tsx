import { useMe, type Role } from '@shopdesk/shared';
import type { ReactNode } from 'react';

/** Hides a page from roles that can't use it. The API enforces this too — this is only UX. */
export function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { user } = useMe();
  if (!roles.includes(user.role)) {
    return (
      <div className="rounded-xl border border-border bg-surface p-8 text-center">
        <p className="text-lg font-semibold">Admins only</p>
        <p className="mt-1 text-text-muted">Ask the owner if you need access to this page.</p>
      </div>
    );
  }
  return <>{children}</>;
}
