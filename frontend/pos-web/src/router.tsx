import { AuthGate, SignInPage } from '@shopdesk/shared';
import { createBrowserRouter } from 'react-router';

import { BillingShell } from './components/BillingShell';
import { BillingPage } from './pages/BillingPage';

export const router = createBrowserRouter([
  { path: '/sign-in/*', element: <SignInPage appName="Billing Counter" /> },
  {
    path: '/',
    element: (
      <AuthGate appName="the Billing Counter">
        <BillingShell />
      </AuthGate>
    ),
    children: [{ index: true, element: <BillingPage /> }],
  },
]);
