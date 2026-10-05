import { AuthGate, SignInPage } from '@shopdesk/shared';
import { createBrowserRouter, Link, Outlet, type RouteObject } from 'react-router';

import { ChooseArea, Landing } from './landing/AreaGuard';

import { AdminScreen, PosScreen } from './AreaScreens';

export const routes: RouteObject[] = [
  { path: '/sign-in/*', element: <SignInPage appName="ShopDesk" /> },
  {
    element: (
      <AuthGate appName="ShopDesk">
        <Outlet />
      </AuthGate>
    ),
    children: [
      { path: '/', element: <Landing /> },
      { path: '/choose-area', element: <ChooseArea /> },
      { path: '/admin/*', element: <AdminScreen /> },
      { path: '/pos/*', element: <PosScreen /> },
    ],
  },
  {
    path: '*',
    element: (
      <main className="p-8">
        Page not found. <Link to="/">Home</Link>
      </main>
    ),
  },
];

export const router = createBrowserRouter(routes);
