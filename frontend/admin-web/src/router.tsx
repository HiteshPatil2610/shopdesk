import { AuthGate, SignInPage } from '@shopdesk/shared';
import { createBrowserRouter } from 'react-router';

import { Layout } from './components/Layout';
import { RequireRole } from './components/RequireRole';
import { DashboardPage } from './pages/DashboardPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { UsersPage } from './pages/UsersPage';

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
      { index: true, element: <DashboardPage /> },
      {
        path: 'users',
        element: (
          <RequireRole roles={['admin']}>
            <UsersPage />
          </RequireRole>
        ),
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
