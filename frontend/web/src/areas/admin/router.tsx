import { Layout } from './components/Layout';
import { RequireRole } from './components/RequireRole';
import { NotFoundPage } from './pages/NotFoundPage';

import { lazy, Suspense } from 'react';
import { Route, Routes } from 'react-router';
import { Spinner } from '@shopdesk/shared';

const Dashboard = lazy(() =>
  import('./pages/DashboardPage').then((m) => ({ default: m.DashboardPage })),
);
const Products = lazy(() =>
  import('./pages/ProductsPage').then((m) => ({ default: m.ProductsPage })),
);
const ProductNew = lazy(() =>
  import('./pages/ProductNewPage').then((m) => ({ default: m.ProductNewPage })),
);
const ProductEdit = lazy(() =>
  import('./pages/ProductEditPage').then((m) => ({ default: m.ProductEditPage })),
);
const Orders = lazy(() => import('./pages/OrdersPage').then((m) => ({ default: m.OrdersPage })));
const OrderDetail = lazy(() =>
  import('./pages/OrderDetailPage').then((m) => ({ default: m.OrderDetailPage })),
);
const Stock = lazy(() => import('./pages/StockPage').then((m) => ({ default: m.StockPage })));
const Reports = lazy(() => import('./pages/ReportsPage').then((m) => ({ default: m.ReportsPage })));
const Audit = lazy(() => import('./pages/AuditPage').then((m) => ({ default: m.AuditPage })));
const Pricing = lazy(() =>
  import('./pages/PricingSettingsPage').then((m) => ({ default: m.PricingSettingsPage })),
);
const Users = lazy(() => import('./pages/UsersPage').then((m) => ({ default: m.UsersPage })));

export default function AdminArea() {
  return (
    <Suspense fallback={<Spinner label="Loading Admin Console" />}>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="products" element={<Products />} />
          <Route path="products/new" element={<ProductNew />} />
          <Route path="products/:id" element={<ProductEdit />} />
          <Route path="stock" element={<Stock />} />
          <Route path="orders" element={<Orders />} />
          <Route path="orders/:id" element={<OrderDetail />} />
          <Route path="reports" element={<Reports />} />
          <Route path="audit" element={<Audit />} />
          <Route
            path="settings/pricing"
            element={
              <RequireRole roles={['admin']}>
                <Pricing />
              </RequireRole>
            }
          />
          <Route
            path="users"
            element={
              <RequireRole roles={['admin']}>
                <Users />
              </RequireRole>
            }
          />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
