import { useQueryClient, type QueryClient } from '@tanstack/react-query';
import { cleanup, render } from '@testing-library/react';
import { useEffect } from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { SessionQueryProvider } from './SessionQueryProvider';

const auth = vi.hoisted(() => ({ userId: 'admin', sessionId: 'admin-session' }));
vi.mock('@clerk/react', () => ({ useAuth: () => auth }));
afterEach(cleanup);

it('does not expose cached admin identity or orders to a new cashier session', () => {
  const observe = vi.fn<(client: QueryClient) => void>();
  function Probe() {
    const client = useQueryClient();
    useEffect(() => observe(client), [client]);
    return null;
  }
  const view = render(
    <SessionQueryProvider>
      <Probe />
    </SessionQueryProvider>,
  );
  const before = observe.mock.calls[0]?.[0];
  if (!before) throw new Error('Initial query client was not observed');
  before.setQueryData(['me'], { areas: ['admin', 'pos'] });
  before.setQueryData(['my-orders'], [{ customer_name: 'Other customer' }]);
  auth.userId = 'cashier';
  auth.sessionId = 'cashier-session';
  view.rerender(
    <SessionQueryProvider>
      <Probe />
    </SessionQueryProvider>,
  );
  const after = observe.mock.calls[1]?.[0];
  if (!after) throw new Error('New query client was not observed');
  expect(after).not.toBe(before);
  expect(after.getQueryData(['me'])).toBeUndefined();
  expect(after.getQueryData(['my-orders'])).toBeUndefined();
});
