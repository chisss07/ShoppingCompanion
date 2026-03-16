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
  primary:
    'bg-primary-600 text-white border border-primary-700 hover:bg-primary-700 active:bg-primary-800 focus-visible:ring-2 focus-visible:ring-primary-600 focus-visible:ring-offset-2 disabled:bg-primary-300 disabled:border-primary-300',
  secondary:
    'bg-white text-neutral-700 border border-neutral-200 hover:bg-neutral-50 hover:border-neutral-300 active:bg-neutral-100 focus-visible:ring-2 focus-visible:ring-primary-600 focus-visible:ring-offset-2 disabled:text-neutral-400 disabled:bg-neutral-50',
  ghost:
    'bg-transparent text-neutral-600 border border-transparent hover:bg-neutral-100 hover:text-neutral-900 active:bg-neutral-200 focus-visible:ring-2 focus-visible:ring-primary-600 focus-visible:ring-offset-2 disabled:text-neutral-400',
  destructive:
    'bg-danger-500 text-white border border-danger-700 hover:bg-danger-700 active:bg-danger-700 focus-visible:ring-2 focus-visible:ring-danger-500 focus-visible:ring-offset-2 disabled:bg-danger-300 disabled:border-danger-300',
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-sm gap-1.5',
  md: 'h-9 px-4 text-sm gap-2',
  lg: 'h-11 px-5 text-base gap-2',
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
        'inline-flex items-center justify-center rounded-lg font-medium',
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
