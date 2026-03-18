import { clsx } from 'clsx';

// ─────────────────────────────────────────────
// Logo
// Price-tag shape with sparkle, plus "ShopCompare" wordmark.
// ─────────────────────────────────────────────

interface LogoProps {
  /** Show just the icon without the text wordmark */
  iconOnly?: boolean;
  /** Size of the icon in pixels (default 32) */
  size?: number;
  className?: string;
  /** Override text size class */
  textClassName?: string;
}

export function Logo({
  iconOnly = false,
  size = 32,
  className,
  textClassName,
}: LogoProps) {
  return (
    <span className={clsx('inline-flex items-center gap-2.5 select-none', className)}>
      {/* SVG price-tag icon */}
      <svg
        width={size}
        height={size}
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
        className="flex-shrink-0"
      >
        {/* Price tag body — rounded rectangle with notched top-left */}
        <path
          d="M6 4C4.89543 4 4 4.89543 4 6V20C4 21.1046 4.89543 22 6 22H20C21.1046 22 22 21.1046 22 20V10L16 4H6Z"
          className="fill-primary-600 dark:fill-primary-400"
        />
        {/* Tag hole */}
        <circle
          cx="9"
          cy="9"
          r="2"
          className="fill-white dark:fill-dark-surface"
          fillOpacity="0.9"
        />
        {/* Folded corner triangle */}
        <path
          d="M16 4L22 10H17C16.4477 10 16 9.55228 16 9V4Z"
          className="fill-primary-700 dark:fill-primary-500"
        />
        {/* Sparkle / star — bottom-right corner area */}
        {/* Main sparkle cross */}
        <line
          x1="25"
          y1="20"
          x2="25"
          y2="28"
          stroke="white"
          strokeWidth="2"
          strokeLinecap="round"
          className="stroke-primary-400 dark:stroke-primary-300"
        />
        <line
          x1="21"
          y1="24"
          x2="29"
          y2="24"
          stroke="white"
          strokeWidth="2"
          strokeLinecap="round"
          className="stroke-primary-400 dark:stroke-primary-300"
        />
        {/* Diagonal sparkle arms */}
        <line
          x1="22.5"
          y1="21.5"
          x2="27.5"
          y2="26.5"
          stroke="white"
          strokeWidth="1.2"
          strokeLinecap="round"
          className="stroke-primary-300 dark:stroke-primary-400"
          strokeOpacity="0.7"
        />
        <line
          x1="27.5"
          y1="21.5"
          x2="22.5"
          y2="26.5"
          stroke="white"
          strokeWidth="1.2"
          strokeLinecap="round"
          className="stroke-primary-300 dark:stroke-primary-400"
          strokeOpacity="0.7"
        />
        {/* Price lines on tag body */}
        <rect
          x="8"
          y="13"
          width="10"
          height="1.5"
          rx="0.75"
          className="fill-white"
          fillOpacity="0.6"
        />
        <rect
          x="8"
          y="16.5"
          width="7"
          height="1.5"
          rx="0.75"
          className="fill-white"
          fillOpacity="0.4"
        />
      </svg>

      {/* Wordmark */}
      {!iconOnly && (
        <span
          className={clsx(
            'font-bold tracking-tight leading-none',
            textClassName ?? 'text-base',
          )}
        >
          <span className="text-primary-600 dark:text-primary-400">Shop</span>
          <span className="text-neutral-900 dark:text-slate-200">Compare</span>
        </span>
      )}
    </span>
  );
}
