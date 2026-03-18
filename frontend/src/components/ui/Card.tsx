import { clsx } from 'clsx';
import type { HTMLAttributes, ReactNode } from 'react';

// ─────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  hoverable?: boolean;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  elevated?: boolean;
}

interface CardHeaderProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

interface CardBodyProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  padding?: 'sm' | 'md' | 'lg';
}

// ─────────────────────────────────────────────
// Padding map
// ─────────────────────────────────────────────

const paddingClasses = {
  none: '',
  sm: 'p-3',
  md: 'p-4',
  lg: 'p-6',
} as const;

// ─────────────────────────────────────────────
// Card
// ─────────────────────────────────────────────

export function Card({
  children,
  hoverable = false,
  padding = 'md',
  elevated = false,
  className,
  ...props
}: CardProps) {
  return (
    <div
      className={clsx(
        'bg-white dark:bg-dark-surface',
        'border border-primary-100 dark:border-dark-border',
        'rounded-card',
        elevated
          ? 'shadow-card-elevated dark:shadow-card-dark'
          : 'shadow-card dark:shadow-card-dark',
        hoverable && [
          'transition-shadow duration-200 cursor-pointer',
          'hover:shadow-card-hover dark:hover:shadow-card-dark-hover',
        ],
        paddingClasses[padding],
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

// ─────────────────────────────────────────────
// Card.Header
// ─────────────────────────────────────────────

export function CardHeader({ children, className, ...props }: CardHeaderProps) {
  return (
    <div
      className={clsx(
        'border-b border-primary-100 dark:border-dark-border px-4 py-3',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

// ─────────────────────────────────────────────
// Card.Body
// ─────────────────────────────────────────────

export function CardBody({
  children,
  padding = 'md',
  className,
  ...props
}: CardBodyProps) {
  return (
    <div className={clsx(paddingClasses[padding], className)} {...props}>
      {children}
    </div>
  );
}
