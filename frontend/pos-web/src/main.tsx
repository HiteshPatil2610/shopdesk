import './index.css';

import { ClerkProvider } from '@clerk/react';
import { ApiProvider, ClerkConfigError } from '@shopdesk/shared';
import { QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router';

import { prewarm } from './lib/prewarm';
import { queryClient } from './lib/queryClient';
import { router } from './router';

const rootEl = document.getElementById('root');
if (!rootEl) throw new Error('Missing #root element');

const publishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;
const apiBase = import.meta.env.VITE_API_BASE_URL ?? '';

// Wake the serverless POS API (and Neon) while the cashier is still signing in.
prewarm(apiBase);

createRoot(rootEl).render(
  <StrictMode>
    {publishableKey ? (
      <ClerkProvider
        publishableKey={publishableKey}
        telemetry={false}
        routerPush={(to) => void router.navigate(to)}
        routerReplace={(to) => void router.navigate(to, { replace: true })}
      >
        <QueryClientProvider client={queryClient}>
          <ApiProvider baseURL={apiBase}>
            <RouterProvider router={router} />
          </ApiProvider>
        </QueryClientProvider>
      </ClerkProvider>
    ) : (
      <ClerkConfigError appDir="pos-web" />
    )}
  </StrictMode>,
);
