import { ApiProvider, useMe } from '@shopdesk/shared';
import { useEffect, type ReactNode } from 'react';
import { Link, Navigate } from 'react-router';

export type Area = 'admin' | 'pos';

export function AreaGuard({ area, children }: { area: Area; children: ReactNode }) {
  const { areas } = useMe();
  const allowed = areas.includes(area);
  useEffect(() => {
    if (allowed) localStorage.setItem('shopdesk.lastArea', area);
  }, [allowed, area]);
  if (!allowed) {
    return (
      <main className="p-8 text-center">
        <h1>No access to the Admin Console</h1>
        <Link to="/pos" className="text-primary">
          Go to Billing Counter
        </Link>
      </main>
    );
  }
  return (
    <ApiProvider baseURL={`/api/${area}`}>
      <div data-shopdesk-area={area}>{children}</div>
    </ApiProvider>
  );
}

export function Landing() {
  const { areas } = useMe();
  const last = localStorage.getItem('shopdesk.lastArea');
  const destination =
    last && areas.includes(last as Area) ? last : areas.includes('admin') ? 'admin' : 'pos';
  return <Navigate to={`/${destination}`} replace />;
}

export function AreaSwitcher({ area }: { area: Area }) {
  const { areas } = useMe();
  if (!areas.includes('admin')) return null;
  return (
    <Link className="text-sm text-primary" to={area === 'admin' ? '/pos' : '/admin'}>
      {area === 'admin' ? 'Billing Counter' : 'Admin Console'}
    </Link>
  );
}

export function ChooseArea() {
  const { areas } = useMe();
  return (
    <main className="p-8">
      <h1 className="text-xl font-semibold">Choose an area</h1>
      <nav className="flex gap-4">
        {areas.map((area) => (
          <Link key={area} to={`/${area}`} className="text-primary">
            {area === 'admin' ? 'Admin Console' : 'Billing Counter'}
          </Link>
        ))}
      </nav>
    </main>
  );
}
