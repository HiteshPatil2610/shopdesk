import { AuthGate, SignInPage, type Role } from '@shopdesk/shared';
import type { ComponentType } from 'react';
import { createBrowserRouter, type RouteObject } from 'react-router';

import { Layout } from './components/Layout';
import { RequireRole } from './components/RequireRole';
import { NotFoundPage } from './pages/NotFoundPage';

/**
 * Pages load on demand (code-splitting): the dashboard's chart library, the product form,
 * the audit viewer etc. only download when that page is opened.
 */
function page(
  load: () => Promise<Record<string, unknown>>,
  name: string,
  roles?: Role[],
): Pick<RouteObject, 'lazy'> {
  return {
    lazy: async () => {
      const Component = (await load())[name] as ComponentType;
      return {
        element: roles ? (
          <RequireRole roles={roles}>
            <Component />
          </RequireRole>
        ) : (
          <Component />
        ),
      };
    },
  };
}

export const router = createBrowserRouter([
  { path: '/sign-in/*', element: <SignInPage appName="Admin Console" /> },
  {
    path: '/',
    element: (
      <AuthGate appName="the Admin Console">
        <Layout />
      </AuthGate>
    ),
    children: [
      { index: true, ...page(() => import('./pages/DashboardPage'), 'DashboardPage') },
      { path: 'products', ...page(() => import('./pages/ProductsPage'), 'ProductsPage') },
      { path: 'products/new', ...page(() => import('./pages/ProductNewPage'), 'ProductNewPage') },
      {
        path: 'products/:id',
        ...page(() => import('./pages/ProductEditPage'), 'ProductEditPage'),
      },
      { path: 'stock', ...page(() => import('./pages/StockPage'), 'StockPage') },
      { path: 'orders', ...page(() => import('./pages/OrdersPage'), 'OrdersPage') },
      {
        path: 'orders/:id',
        ...page(() => import('./pages/OrderDetailPage'), 'OrderDetailPage'),
      },
      { path: 'reports', ...page(() => import('./pages/ReportsPage'), 'ReportsPage') },
      {
        path: 'audit',
        ...page(() => import('./pages/AuditPage'), 'AuditPage', ['admin', 'manager']),
      },
      {
        path: 'settings/pricing',
        ...page(() => import('./pages/PricingSettingsPage'), 'PricingSettingsPage', ['admin']),
      },
      { path: 'users', ...page(() => import('./pages/UsersPage'), 'UsersPage', ['admin']) },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
