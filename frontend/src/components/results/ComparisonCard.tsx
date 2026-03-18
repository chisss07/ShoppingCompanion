import { ExternalLink, Star, Truck, Award } from 'lucide-react';
import { clsx } from 'clsx';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { formatPrice } from '../../services/api';
import type { PriceEntry } from '../../types';

// ─────────────────────────────────────────────
// Star rating display
// ─────────────────────────────────────────────

function StarRating({ rating }: { rating: number }) {
  return (
    <span className="flex items-center gap-0.5" aria-label={`Rating: ${rating} out of 5`}>
      {Array.from({ length: 5 }, (_, i) => {
        const filled = i + 1 <= Math.round(rating);
        return (
          <Star
            key={i}
            className={clsx(
              'h-3 w-3',
              filled
                ? 'fill-warning-500 text-warning-500'
                : 'text-neutral-300 dark:text-slate-600',
            )}
            aria-hidden="true"
          />
        );
      })}
      <span className="ml-1 text-xs text-neutral-500 dark:text-slate-400 font-medium">
        {rating.toFixed(1)}
      </span>
    </span>
  );
}

// ─────────────────────────────────────────────
// Deal score bar
// ─────────────────────────────────────────────

function DealScoreBar({ score }: { score: number }) {
  const percent = Math.round(score * 100);
  const color =
    percent >= 80
      ? 'bg-success-500'
      : percent >= 60
        ? 'bg-warning-500'
        : 'bg-neutral-300 dark:bg-slate-600';

  return (
    <div className="space-y-0.5">
      <div className="flex items-center justify-between text-xs text-neutral-400 dark:text-slate-500">
        <span>Deal score</span>
        <span className="font-mono font-medium text-neutral-600 dark:text-slate-300">
          {percent}/100
        </span>
      </div>
      <div className="h-1 w-full overflow-hidden rounded-full bg-primary-100 dark:bg-primary-900/40">
        <div
          role="progressbar"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Deal score: ${percent} out of 100`}
          className={clsx('h-full rounded-full transition-all duration-500', color)}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// Availability badge
// ─────────────────────────────────────────────

function AvailabilityBadge({ availability }: { availability: string }) {
  const lower = availability.toLowerCase();
  if (lower.includes('out of stock') || lower.includes('unavailable')) {
    return <Badge variant="danger" dot>{availability}</Badge>;
  }
  if (lower.includes('limited') || lower.includes('low stock')) {
    return <Badge variant="warning" dot>{availability}</Badge>;
  }
  return <Badge variant="success" dot>{availability}</Badge>;
}

// ─────────────────────────────────────────────
// ComparisonCard
// ─────────────────────────────────────────────

interface ComparisonCardProps {
  entry: PriceEntry;
  isBestDeal?: boolean;
}

export function ComparisonCard({ entry, isBestDeal = false }: ComparisonCardProps) {
  const isFreeShipping =
    entry.shipping === null ||
    entry.shipping.toLowerCase().includes('free') ||
    entry.shipping === '0';

  return (
    <article
      className={clsx(
        'flex flex-col overflow-hidden rounded-card',
        'bg-white dark:bg-dark-surface',
        'transition-shadow duration-200',
        isBestDeal
          ? [
              'border-2 border-primary-600 dark:border-primary-500',
              'shadow-[0_0_0_1px_rgb(37_99_235_/_0.15),0_4px_16px_rgb(37_99_235_/_0.12)]',
              'dark:shadow-[0_0_0_1px_rgb(59_130_246_/_0.2),0_4px_16px_rgb(0_0_0_/_0.4)]',
            ]
          : [
              'border border-primary-100 dark:border-dark-border',
              'shadow-card dark:shadow-card-dark',
              'hover:shadow-card-hover dark:hover:shadow-card-dark-hover',
            ],
      )}
      aria-label={`${entry.source} — ${formatPrice(entry.price)}`}
    >
      {/* Best deal banner */}
      {isBestDeal && (
        <div className="bg-primary-600 dark:bg-primary-500 px-4 py-1.5 flex items-center gap-1.5">
          <Award className="h-3.5 w-3.5 text-white flex-shrink-0" aria-hidden="true" />
          <span className="text-xs font-semibold text-white uppercase tracking-wide">
            Best Deal
          </span>
        </div>
      )}

      <div className="p-4 flex flex-col gap-3 flex-1">
        {/* Header row: source + availability */}
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="font-semibold text-neutral-900 dark:text-slate-100 text-sm leading-tight">
              {entry.source}
            </h3>
            {entry.condition !== 'new' && (
              <span className="text-xs text-neutral-500 dark:text-slate-400 capitalize">
                {entry.condition}
              </span>
            )}
          </div>
          <AvailabilityBadge availability={entry.availability} />
        </div>

        {/* Product image + title */}
        {entry.image_url && (
          <div className="flex items-center gap-3">
            <div className="h-14 w-14 flex-shrink-0 rounded-lg overflow-hidden bg-neutral-50 dark:bg-[#0a1628] border border-primary-100 dark:border-dark-border flex items-center justify-center">
              <img
                src={entry.image_url}
                alt={entry.product_title}
                className="h-12 w-12 object-contain"
                loading="lazy"
              />
            </div>
            <p className="text-xs text-neutral-500 dark:text-slate-400 line-clamp-2 leading-relaxed">
              {entry.product_title}
            </p>
          </div>
        )}

        {!entry.image_url && (
          <p className="text-xs text-neutral-500 dark:text-slate-400 line-clamp-2 leading-relaxed">
            {entry.product_title}
          </p>
        )}

        {/* Price */}
        <div className="flex items-baseline gap-1">
          <span
            className={clsx(
              'font-mono font-bold tabular-nums',
              isBestDeal
                ? 'text-3xl text-primary-600 dark:text-primary-400'
                : 'text-2xl text-neutral-900 dark:text-slate-100',
            )}
            aria-label={`Price: ${formatPrice(entry.price)}`}
          >
            {formatPrice(entry.price)}
          </span>
        </div>

        {/* Shipping */}
        <div className="flex items-center gap-1.5">
          <Truck
            className={clsx(
              'h-3.5 w-3.5 flex-shrink-0',
              isFreeShipping
                ? 'text-success-500'
                : 'text-neutral-400 dark:text-slate-500',
            )}
            aria-hidden="true"
          />
          <span
            className={clsx(
              'text-xs font-medium',
              isFreeShipping
                ? 'text-success-700 dark:text-green-400'
                : 'text-neutral-500 dark:text-slate-400',
            )}
          >
            {isFreeShipping ? 'Free shipping' : entry.shipping}
          </span>
        </div>

        {/* Rating */}
        {entry.seller_rating !== null && entry.seller_rating > 0 && (
          <StarRating rating={entry.seller_rating} />
        )}

        {/* Deal score */}
        {entry.deal_score !== null && <DealScoreBar score={entry.deal_score} />}

        {/* CTA */}
        <div className="mt-auto pt-1">
          <Button
            variant={isBestDeal ? 'primary' : 'secondary'}
            size="sm"
            fullWidth
            rightIcon={<ExternalLink className="h-3.5 w-3.5" />}
            onClick={() => window.open(entry.url, '_blank', 'noopener,noreferrer')}
          >
            View Deal
          </Button>
        </div>
      </div>
    </article>
  );
}
