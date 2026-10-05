import type { ButtonHTMLAttributes } from 'react';

type Variant = 'primary' | 'secondary' | 'success' | 'danger' | 'ghost';
type Size = 'sm' | 'md' | 'lg' | 'xl';

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
};

const variants: Record<Variant, string> = {
  primary: 'bg-primary text-white hover:opacity-90',
  secondary: 'bg-surface text-text border border-border hover:bg-bg',
  success: 'bg-success text-white hover:opacity-90',
  danger: 'bg-danger text-white hover:opacity-90',
  ghost: 'bg-transparent text-text hover:bg-bg',
};

const sizes: Record<Size, string> = {
  sm: 'h-11 sm:h-8 px-3 text-sm',
  md: 'h-11 sm:h-10 px-4 text-sm',
  lg: 'h-12 px-5 text-base',
  xl: 'h-14 px-6 text-lg',
};

export function Button({ variant = 'primary', size = 'md', className = '', type, ...rest }: Props) {
  return (
    <button
      type={type ?? 'button'}
      className={`inline-flex items-center justify-center gap-2 rounded-lg font-medium transition focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${sizes[size]} ${className}`}
      {...rest}
    />
  );
}
