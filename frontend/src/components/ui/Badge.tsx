import { clsx } from 'clsx';
import type { ReactNode } from 'react';

// ─────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────

type BadgeVariant = 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'primary';
type BadgeSize = 'sm' | 'md';

interface BadgeProps {
  variant?: BadgeVariant;
  size?: BadgeSize;
  children: ReactNode;
  className?: string;
  dot?: boolean;
}

// ─────────────────────────────────────────────
// Variant styles
// ─────────────────────────────────────────────

const variantClasses: Record<BadgeVariant, string> = {
  success:
    'bg-success-100 text-success-700 border-success-500/20 dark:bg-success-500/15 dark:text-green-400 dark:border-success-500/20',
  warning:
    'bg-warning-100 text-warning-700 border-warning-500/20 dark:bg-warning-500/15 dark:text-yellow-400 dark:border-warning-500/20',
  danger:
    'bg-danger-100 text-danger-700 border-danger-500/20 dark:bg-danger-500/15 dark:text-red-400 dark:border-danger-500/20',
  info:
    'bg-primary-100 text-primary-700 border-primary-500/20 dark:bg-primary-500/15 dark:text-primary-300 dark:border-primary-500/20',
  neutral:
    'bg-neutral-100 text-neutral-600 border-neutral-200 dark:bg-neutral-800 dark:text-neutral-400 dark:border-neutral-700',
  primary:
    'bg-primary-600 text-white border-transparent dark:bg-primary-500 dark:border-transparent',
};

const dotClasses: Record<BadgeVariant, string> = {
  success: 'bg-success-500',
  warning: 'bg-warning-500',
  danger: 'bg-danger-500',
  info: 'bg-primary-500',
  neutral: 'bg-neutral-400',
  primary: 'bg-white',
};

const sizeClasses: Record<BadgeSize, string> = {
  sm: 'px-1.5 py-0.5 text-xs',
  md: 'px-2 py-0.5 text-xs',
};

// ─────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────

export function Badge({
  variant = 'neutral',
  size = 'md',
  children,
  className,
  dot = false,
}: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded border font-medium leading-none',
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
    >
      {dot && (
        <span
          className={clsx('h-1.5 w-1.5 rounded-full flex-shrink-0', dotClasses[variant])}
          aria-hidden="true"
        />
      )}
      {children}
    </span>
  );
}
