import { clsx } from 'clsx';

// ─────────────────────────────────────────────
// Logo
// PanCor logo image + "ShopCompare" wordmark.
// ─────────────────────────────────────────────

interface LogoProps {
  /** Show just the icon without the text wordmark */
  iconOnly?: boolean;
  /** Height of the logo image in pixels (default 32) */
  size?: number;
  className?: string;
  /** Override text size class */
  textClassName?: string;
}

const LOGO_URL =
  'https://assets.zyrosite.com/cdn-cgi/image/format=auto,w=432,fit=crop,q=95/ALpeKGnb8qhM5WZx/high-res-d951855loVcyzJb0.png';

export function Logo({
  iconOnly = false,
  size = 32,
  className,
  textClassName,
}: LogoProps) {
  return (
    <span className={clsx('inline-flex items-center gap-2.5 select-none', className)}>
      <img
        src={LOGO_URL}
        alt="ShopCompare"
        height={size}
        style={{ height: size, width: 'auto' }}
        className="flex-shrink-0 object-contain drop-shadow-sm"
      />

      {!iconOnly && (
        <span
          className={clsx(
            'font-bold tracking-tight leading-none',
            textClassName ?? 'text-base',
          )}
        >
          <span className="text-gray-900 dark:text-white">Shop</span>
          <span className="text-blue-600 dark:text-blue-300">Compare</span>
        </span>
      )}
    </span>
  );
}
