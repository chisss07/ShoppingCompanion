import { clsx } from 'clsx';
import type { ButtonHTMLAttributes, ReactNode } from 'react';

// ─────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'destructive';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  children: ReactNode;
  loading?: boolean;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
  fullWidth?: boolean;
}

// ─────────────────────────────────────────────
// Styles
// ─────────────────────────────────────────────

const variantClasses: Record<ButtonVariant, string> = {
  primary: [
    'bg-primary-600 text-white border border-primary-700',
    'hover:bg-primary-700 active:bg-primary-800',
    'dark:bg-primary-500 dark:border-primary-600 dark:hover:bg-primary-600',
    'focus-visible:ring-2 focus-visible:ring-primary-600 dark:focus-visible:ring-primary-400 focus-visible:ring-offset-2',
    'disabled:bg-primary-300 disabled:border-primary-300 dark:disabled:bg-primary-800 dark:disabled:border-primary-800',
  ].join(' '),

  secondary: [
    'bg-white dark:bg-dark-surface text-neutral-700 dark:text-slate-300',
    'border border-primary-200 dark:border-dark-border',
    'hover:bg-primary-50 dark:hover:bg-primary-900/40 hover:border-primary-300 dark:hover:border-primary-700',
    'active:bg-primary-100 dark:active:bg-primary-900/60',
    'focus-visible:ring-2 focus-visible:ring-primary-600 dark:focus-visible:ring-primary-400 focus-visible:ring-offset-2',
    'disabled:text-neutral-400 dark:disabled:text-slate-600 disabled:bg-neutral-50 dark:disabled:bg-dark-surface',
  ].join(' '),

  ghost: [
    'bg-transparent text-neutral-600 dark:text-slate-400 border border-transparent',
    'hover:bg-primary-50 dark:hover:bg-primary-900/30 hover:text-primary-700 dark:hover:text-primary-300',
    'active:bg-primary-100 dark:active:bg-primary-900/50',
    'focus-visible:ring-2 focus-visible:ring-primary-600 dark:focus-visible:ring-primary-400 focus-visible:ring-offset-2',
    'disabled:text-neutral-400 dark:disabled:text-slate-600',
  ].join(' '),

  destructive: [
    'bg-danger-500 text-white border border-danger-700',
    'hover:bg-danger-700 active:bg-danger-700',
    'focus-visible:ring-2 focus-visible:ring-danger-500 focus-visible:ring-offset-2',
    'disabled:bg-danger-300 disabled:border-danger-300',
  ].join(' '),
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-sm gap-1.5 rounded-button',
  md: 'h-9 px-4 text-sm gap-2 rounded-button',
  lg: 'h-11 px-5 text-base gap-2 rounded-button',
};

// ─────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────

export function Button({
  variant = 'primary',
  size = 'md',
  children,
  loading = false,
  leftIcon,
  rightIcon,
  fullWidth = false,
  className,
  disabled,
  ...props
}: ButtonProps) {
  const isDisabled = disabled ?? loading;

  return (
    <button
      className={clsx(
        'inline-flex items-center justify-center font-medium',
        'transition-colors duration-150 select-none cursor-pointer',
        'disabled:cursor-not-allowed disabled:opacity-70',
        variantClasses[variant],
        sizeClasses[size],
        fullWidth && 'w-full',
        className,
      )}
      disabled={isDisabled}
      aria-busy={loading}
      {...props}
    >
      {loading ? (
        <span
          className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
          aria-hidden="true"
        />
      ) : (
        leftIcon && <span className="flex-shrink-0">{leftIcon}</span>
      )}
      <span className={loading ? 'sr-only' : undefined}>{children}</span>
      {!loading && rightIcon && <span className="flex-shrink-0">{rightIcon}</span>}
    </button>
  );
}
