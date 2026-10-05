import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { lazy, Suspense, useEffect, type ReactNode } from 'react';
import { Link, MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';

import { useHotkeys } from '../areas/pos/features/cart/useHotkeys';
import { AreaGuard, AreaSwitcher, Landing } from './AreaGuard';

const mocks = vi.hoisted(() => ({ areas: ['admin', 'pos'] as ('admin' | 'pos')[] }));
vi.mock('@shopdesk/shared', async (original) => ({
  ...(await original<typeof import('@shopdesk/shared')>()),
  useMe: () => ({ areas: mocks.areas }),
  ApiProvider: ({ children }: { children: ReactNode }) => children,
}));
afterEach(cleanup);
beforeEach(() => {
  localStorage.clear();
  mocks.areas = ['admin', 'pos'];
});

it('refuses cashier admin access before invoking the admin chunk import', () => {
  mocks.areas = ['pos'];
  const load = vi.fn(async () => ({ default: () => <p>Admin secret screen</p> }));
  const Admin = lazy(load);
  render(
    <MemoryRouter>
      <AreaGuard area="admin">
        <Suspense>
          <Admin />
        </Suspense>
      </AreaGuard>
    </MemoryRouter>,
  );
  expect(screen.getByText('No access to the Admin Console')).toBeTruthy();
  expect(screen.getByRole('link').getAttribute('href')).toBe('/pos');
  expect(load).not.toHaveBeenCalled();
});

it.each([
  { areas: ['admin', 'pos'] as ('admin' | 'pos')[], last: '', destination: 'admin' },
  { areas: ['admin', 'pos'] as ('admin' | 'pos')[], last: 'pos', destination: 'pos' },
  { areas: ['admin', 'pos'] as ('admin' | 'pos')[], last: 'admin', destination: 'admin' },
  { areas: ['pos'] as ('admin' | 'pos')[], last: 'admin', destination: 'pos' },
  { areas: ['pos'] as ('admin' | 'pos')[], last: '', destination: 'pos' },
])('lands on the permitted last area: $last → $destination', ({ areas, last, destination }) => {
  mocks.areas = areas;
  localStorage.setItem('shopdesk.lastArea', last);
  render(
    <MemoryRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/admin" element={<p>Admin destination</p>} />
        <Route path="/pos" element={<p>POS destination</p>} />
      </Routes>
    </MemoryRouter>,
  );
  expect(
    screen.getByText(destination === 'admin' ? 'Admin destination' : 'POS destination'),
  ).toBeTruthy();
});

it('hides the area switcher from cashiers', () => {
  mocks.areas = ['pos'];
  render(
    <MemoryRouter>
      <AreaSwitcher area="pos" />
    </MemoryRouter>,
  );
  expect(screen.queryByRole('link')).toBeNull();
});

it('offers the other area to admins and managers', () => {
  render(
    <MemoryRouter>
      <AreaSwitcher area="admin" />
    </MemoryRouter>,
  );
  expect(screen.getByRole('link', { name: 'Billing Counter' }).getAttribute('href')).toBe('/pos');
});

it('removes POS hotkeys and printing when switching to admin', () => {
  const key = vi.fn();
  const unmounted = vi.fn();
  function PosProbe() {
    useHotkeys(key);
    useEffect(() => unmounted, []);
    return (
      <>
        <style media="print">{'.receipt-print { width: 80mm; }'}</style>
        <Link to="/admin">Admin Console</Link>
      </>
    );
  }
  render(
    <MemoryRouter initialEntries={['/pos']}>
      <Routes>
        <Route
          path="/pos"
          element={
            <AreaGuard area="pos">
              <PosProbe />
            </AreaGuard>
          }
        />
        <Route
          path="/admin"
          element={
            <AreaGuard area="admin">
              <p>Admin screen</p>
            </AreaGuard>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
  fireEvent.keyDown(document, { key: 'F8' });
  expect(key).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('link', { name: 'Admin Console' }));
  fireEvent.keyDown(document, { key: 'F8' });
  expect(key).toHaveBeenCalledTimes(1);
  expect(unmounted).toHaveBeenCalledTimes(1);
  expect(document.querySelector('style[media="print"]')).toBeNull();
  expect(localStorage.getItem('shopdesk.lastArea')).toBe('admin');
});
