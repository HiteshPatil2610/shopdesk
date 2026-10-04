import type { ReactNode } from 'react';

import type { Role } from '../api';

type Tone = 'neutral' | 'primary' | 'success' | 'warning' | 'danger' | 'discount';

const tones: Record<Tone, string> = {
  neutral: 'bg-bg text-text-muted border border-border',
  primary: 'bg-primary/10 text-primary',
  success: 'bg-success/10 text-success',
  warning: 'bg-warning/10 text-warning',
  danger: 'bg-danger/10 text-danger',
  discount: 'bg-discount/10 text-discount',
};

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

const roleTone: Record<Role, Tone> = { admin: 'discount', manager: 'primary', cashier: 'neutral' };

export function RoleBadge({ role }: { role: Role }) {
  return <Badge tone={roleTone[role]}>{role}</Badge>;
}
