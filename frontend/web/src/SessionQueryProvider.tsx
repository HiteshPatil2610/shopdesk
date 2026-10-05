import { useAuth } from '@clerk/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { useState, type ReactNode } from 'react';
import { createQueryClient } from './lib/queryClient';

function QueryScope({ children }: { children: ReactNode }) {
  const [client] = useState(createQueryClient);
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

/** A shared device must not reuse another staff member's identity or order cache. */
export function SessionQueryProvider({ children }: { children: ReactNode }) {
  const { userId, sessionId } = useAuth();
  return <QueryScope key={`${userId ?? 'signed-out'}:${sessionId ?? ''}`}>{children}</QueryScope>;
}
