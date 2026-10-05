import { Spinner } from '@shopdesk/shared';
import { lazy, Suspense } from 'react';
import { AreaGuard } from './landing/AreaGuard';

const AdminArea = lazy(() => import('./areas/admin/router'));
const PosArea = lazy(() => import('./areas/pos/router'));

export function AdminScreen() {
  return (
    <AreaGuard area="admin">
      <Suspense fallback={<Spinner label="Loading Admin Console" />}>
        <AdminArea />
      </Suspense>
    </AreaGuard>
  );
}

export function PosScreen() {
  return (
    <AreaGuard area="pos">
      <Suspense fallback={<Spinner label="Loading Billing Counter" />}>
        <PosArea />
      </Suspense>
    </AreaGuard>
  );
}
