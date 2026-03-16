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
        'bg-white border border-neutral-200 rounded-card',
        elevated ? 'shadow-card-elevated' : 'shadow-card',
        hoverable && 'transition-shadow duration-200 hover:shadow-card-hover cursor-pointer',
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
      className={clsx('border-b border-neutral-100 px-4 py-3', className)}
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
