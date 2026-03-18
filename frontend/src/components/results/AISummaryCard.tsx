import { Sparkles, DollarSign, Package, ShieldCheck } from 'lucide-react';
import { clsx } from 'clsx';
import { formatPrice } from '../../services/api';
import type { SearchResults } from '../../types';

// ─────────────────────────────────────────────
// Highlight chip
// ─────────────────────────────────────────────

interface HighlightChipProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  color: string;
}

function HighlightChip({ icon, label, value, color }: HighlightChipProps) {
  return (
    <div
      className={clsx(
        'flex items-center gap-2 rounded-lg px-3 py-2',
        'bg-white/20 dark:bg-black/20 border border-white/30 dark:border-white/10',
        'backdrop-blur-sm',
      )}
    >
      <span className={clsx('flex-shrink-0', color)}>{icon}</span>
      <div className="min-w-0">
        <div className="text-xs text-blue-100/70 dark:text-blue-200/60 leading-none mb-0.5">
          {label}
        </div>
        <div className="text-sm font-semibold text-white truncate">{value}</div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// AISummaryCard
// ─────────────────────────────────────────────

interface AISummaryCardProps {
  results: SearchResults;
}

export function AISummaryCard({ results }: AISummaryCardProps) {
  const { summary, comparison } = results;

  if (!summary) return null;

  // Derive highlight values from comparison data
  const lowestPriceEntry = comparison.reduce<(typeof comparison)[0] | null>(
    (best, entry) => (best === null || entry.price < best.price ? entry : best),
    null,
  );

  const inStockEntry = comparison.find(
    (e) =>
      e.availability.toLowerCase().includes('in stock') ||
      e.availability.toLowerCase().includes('available'),
  );

  const highestRatedEntry = comparison.reduce<(typeof comparison)[0] | null>(
    (best, entry) =>
      entry.seller_rating !== null &&
      (best === null || (best.seller_rating ?? 0) < entry.seller_rating)
        ? entry
        : best,
    null,
  );

  return (
    <section
      aria-label="AI Summary"
      className={clsx(
        'relative overflow-hidden rounded-card',
        // Light: rich blue gradient
        'bg-gradient-to-br from-primary-900 via-primary-800 to-primary-700',
        // Dark: deeper navy
        'dark:bg-gradient-to-br dark:from-[#030c24] dark:via-[#0d1b3e] dark:to-[#0d1b3e]',
      )}
    >
      {/* Decorative blob */}
      <div
        className="absolute -top-12 -right-12 h-48 w-48 rounded-full bg-primary-500/20 blur-3xl pointer-events-none"
        aria-hidden="true"
      />
      <div
        className="absolute bottom-0 left-1/4 h-32 w-32 rounded-full bg-blue-400/10 blur-2xl pointer-events-none"
        aria-hidden="true"
      />

      <div className="relative p-5 space-y-4">
        {/* Header */}
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold text-white badge-ai shadow-sm">
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
            AI Summary
          </span>
          <span className="text-xs text-blue-200/60">Powered by comparative analysis</span>
        </div>

        {/* Summary text */}
        <p className="text-sm text-blue-50 leading-relaxed">{summary.top_pick_summary}</p>

        {/* Caveats */}
        {summary.caveats && (
          <p className="text-xs text-blue-200/70 italic border-l-2 border-blue-400/40 pl-3">
            {summary.caveats}
          </p>
        )}

        {/* Highlight chips */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {lowestPriceEntry && (
            <HighlightChip
              icon={<DollarSign className="h-4 w-4" />}
              label="Lowest Price"
              value={`${lowestPriceEntry.source} — ${formatPrice(lowestPriceEntry.price)}`}
              color="text-green-300"
            />
          )}
          {inStockEntry && (
            <HighlightChip
              icon={<Package className="h-4 w-4" />}
              label="Best Availability"
              value={inStockEntry.source}
              color="text-blue-300"
            />
          )}
          {highestRatedEntry && highestRatedEntry.seller_rating !== null && (
            <HighlightChip
              icon={<ShieldCheck className="h-4 w-4" />}
              label="Top-Rated Seller"
              value={`${highestRatedEntry.source} (${highestRatedEntry.seller_rating.toFixed(1)}/5)`}
              color="text-yellow-300"
            />
          )}
        </div>
      </div>
    </section>
  );
}
