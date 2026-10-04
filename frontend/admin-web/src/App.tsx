import { HealthBadge } from '@shopdesk/shared';
import { useQuery } from '@tanstack/react-query';

import { fetchHealth } from './lib/api';

export function App() {
  const health = useQuery({ queryKey: ['health'], queryFn: fetchHealth });

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-center justify-center gap-6 p-8 text-center">
      <p className="text-sm font-semibold tracking-widest text-text-muted uppercase">
        Admin Console
      </p>
      <h1 className="text-4xl font-bold">ShopDesk Admin</h1>
      <HealthBadge isLoading={health.isLoading} isError={health.isError} data={health.data} />
      <p className="max-w-md text-text-muted">
        Products, pricing, stock and the audit log will live here. This page is the spec 01
        skeleton.
      </p>
    </main>
  );
}
