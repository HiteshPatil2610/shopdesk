import { AreaSwitcher } from '../../../landing/AreaGuard';
import { UserButton } from '@clerk/react';
import { RoleBadge, useMe, type Role } from '@shopdesk/shared';
import { NavLink, Outlet } from 'react-router';

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

  return (
    <div className="flex min-h-screen">
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
        <header className="flex items-center justify-between border-b border-border bg-surface px-6 py-3">
          <nav aria-label="Main (mobile)" className="flex gap-3 md:hidden">
            {items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/admin'}
                className="text-sm font-medium"
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <span className="hidden md:block" />
          <div className="flex items-center gap-3">
            <span className="text-sm text-text-muted">{user.full_name}</span>
            <RoleBadge role={user.role} />
            <AreaSwitcher area="admin" />
            <UserButton />
          </div>
        </header>
        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
