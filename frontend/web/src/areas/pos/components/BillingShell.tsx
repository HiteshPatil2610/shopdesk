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
    <div className="flex min-h-dvh flex-col text-base">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-surface px-3 py-3 sm:px-5">
        <p className="font-bold">
          ShopDesk <span className="font-semibold text-text-muted">· BILLING</span>
        </p>
        <div className="flex min-w-0 items-center gap-3">
          <span className="hidden text-sm lg:block">
            Cashier: <strong>{user.full_name}</strong>
          </span>
          <span className="hidden xl:block">
            <Clock />
          </span>
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
