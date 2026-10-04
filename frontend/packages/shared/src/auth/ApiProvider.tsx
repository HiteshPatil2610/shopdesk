import { useAuth } from '@clerk/react';
import type { AxiosInstance } from 'axios';
import { createContext, useContext, useMemo, type ReactNode } from 'react';

import { createApiClient } from '../api';

const ApiContext = createContext<AxiosInstance | null>(null);

type Props = { baseURL: string; children: ReactNode };

/** Provides an axios client that attaches the signed-in user's Clerk token to every request. */
export function ApiProvider({ baseURL, children }: Props) {
  const { getToken } = useAuth();
  const client = useMemo(() => createApiClient({ baseURL, getToken }), [baseURL, getToken]);
  return <ApiContext.Provider value={client}>{children}</ApiContext.Provider>;
}

export function useApi(): AxiosInstance {
  const client = useContext(ApiContext);
  if (!client) throw new Error('useApi must be used inside <ApiProvider>');
  return client;
}
