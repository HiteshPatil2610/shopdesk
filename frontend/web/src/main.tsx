import './index.css';

import { ClerkProvider } from '@clerk/react';
import { ApiProvider, ClerkConfigError } from '@shopdesk/shared';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router';

import { SessionQueryProvider } from './SessionQueryProvider';
import { router } from './router';

const rootEl = document.getElementById('root');
if (!rootEl) throw new Error('Missing #root element');

const publishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

createRoot(rootEl).render(
  <StrictMode>
    {publishableKey ? (
      <ClerkProvider
        publishableKey={publishableKey}
        telemetry={false}
        routerPush={(to) => void router.navigate(to)}
        routerReplace={(to) => void router.navigate(to, { replace: true })}
      >
        <SessionQueryProvider>
          <ApiProvider baseURL="/api/auth">
            <RouterProvider router={router} />
          </ApiProvider>
        </SessionQueryProvider>
      </ClerkProvider>
    ) : (
      <ClerkConfigError appDir="web" />
    )}
  </StrictMode>,
);
