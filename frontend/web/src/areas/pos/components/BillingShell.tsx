import { AreaSwitcher } from '../../../landing/AreaGuard';
import { UserButton } from '@clerk/react';
import { useMe } from '@shopdesk/shared';
import { useEffect, useState } from 'react';
import { Outlet } from 'react-router';

function Clock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 30_000);
    return () => window.clearInterval(id);
  }, []);
  return (
    <time dateTime={now.toISOString()} className="text-sm text-text-muted tabular-nums">
      {now.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
    </time>
  );
}

export function BillingShell() {
  const { user } = useMe();
  return (
    <div className="flex min-h-screen flex-col text-base">
      <header className="flex items-center justify-between border-b border-border bg-surface px-5 py-3">
        <p className="font-bold">
          ShopDesk <span className="font-semibold text-text-muted">· BILLING</span>
        </p>
        <div className="flex items-center gap-4">
          <span className="text-sm">
            Cashier: <strong>{user.full_name}</strong>
          </span>
          <Clock />
          <AreaSwitcher area="pos" />
          <UserButton />
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
