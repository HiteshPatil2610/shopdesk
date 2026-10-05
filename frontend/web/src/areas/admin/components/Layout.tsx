import { AreaSwitcher } from '../../../landing/AreaGuard';
import { UserButton } from '@clerk/react';
import { RoleBadge, useMe, type Role } from '@shopdesk/shared';
import { NavLink, Outlet } from 'react-router';
import { useEffect, useRef } from 'react';

type NavItem = { to: string; label: string; icon: string; roles: Role[] };

const NAV: NavItem[] = [
  { to: '/admin', label: 'Dashboard', icon: '▣', roles: ['admin', 'manager'] },
  { to: '/admin/products', label: 'Products', icon: '📦', roles: ['admin', 'manager'] },
  { to: '/admin/stock', label: 'Stock', icon: '▤', roles: ['admin', 'manager'] },
  { to: '/admin/orders', label: 'Orders', icon: '🧾', roles: ['admin', 'manager'] },
  { to: '/admin/reports', label: 'Reports', icon: '📈', roles: ['admin', 'manager'] },
  { to: '/admin/audit', label: 'Audit log', icon: '≡', roles: ['admin', 'manager'] },
  { to: '/admin/settings/pricing', label: 'Pricing rules', icon: '₹', roles: ['admin'] },
  { to: '/admin/users', label: 'Users', icon: '👥', roles: ['admin'] },
];

export function Layout() {
  const { user } = useMe();
  const items = NAV.filter((item) => item.roles.includes(user.role));
  const mobileMenu = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      const menu = mobileMenu.current;
      if (event.key === 'Escape' && menu?.open && menu.contains(event.target as Node)) {
        menu.open = false;
        menu.querySelector('summary')?.focus();
      }
    };
    document.addEventListener('keydown', closeOnEscape);
    return () => document.removeEventListener('keydown', closeOnEscape);
  }, []);

  return (
    <div className="flex min-h-dvh">
      <aside className="hidden w-56 shrink-0 flex-col border-r border-border bg-surface md:flex">
        <div className="px-5 py-5">
          <p className="text-lg font-bold">ShopDesk</p>
          <p className="text-xs font-semibold tracking-widest text-text-muted uppercase">Admin</p>
        </div>
        <nav aria-label="Main" className="flex flex-col gap-1 px-3">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/admin'}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium ${
                  isActive ? 'bg-primary/10 text-primary' : 'text-text hover:bg-bg'
                }`
              }
            >
              <span aria-hidden="true">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="relative flex flex-wrap items-center justify-between gap-2 border-b border-border bg-surface px-3 py-3 sm:px-6">
          <details ref={mobileMenu} className="group md:hidden">
            <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 rounded-lg border border-border px-3 text-sm font-semibold">
              <span aria-hidden="true">☰</span> Menu
            </summary>
            <nav
              aria-label="Main (mobile)"
              className="absolute inset-x-3 top-full z-30 mt-2 grid grid-cols-2 gap-1 rounded-xl border border-border bg-surface p-2 shadow-lg"
            >
              {items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/admin'}
                  onClick={() => {
                    if (mobileMenu.current) mobileMenu.current.open = false;
                  }}
                  className={({ isActive }) =>
                    `flex min-h-11 items-center gap-2 rounded-lg px-3 text-sm font-medium ${isActive ? 'bg-primary/10 text-primary' : 'hover:bg-bg'}`
                  }
                >
                  <span aria-hidden="true">{item.icon}</span>
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </details>
          <span className="hidden md:block" />
          <div className="flex min-w-0 items-center gap-2 sm:gap-3">
            <span className="hidden max-w-48 truncate text-sm text-text-muted lg:block">
              {user.full_name}
            </span>
            <span className="hidden sm:block">
              <RoleBadge role={user.role} />
            </span>
            <AreaSwitcher area="admin" />
            <UserButton />
          </div>
        </header>
        <main className="min-w-0 flex-1 p-3 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
