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
        'bg-white/60 border border-white/80',
        'backdrop-blur-sm',
      )}
    >
      <span className={clsx('flex-shrink-0', color)}>{icon}</span>
      <div className="min-w-0">
        <div className="text-xs text-neutral-500 leading-none mb-0.5">{label}</div>
        <div className="text-sm font-semibold text-neutral-800 truncate">{value}</div>
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
  const lowestPriceEntry = comparison.reduce<typeof comparison[0] | null>(
    (best, entry) => (best === null || entry.price < best.price ? entry : best),
    null,
  );

  const inStockEntry = comparison.find(
    (e) => e.availability.toLowerCase().includes('in stock') || e.availability.toLowerCase().includes('available'),
  );

  const highestRatedEntry = comparison.reduce<typeof comparison[0] | null>(
    (best, entry) =>
      entry.seller_rating !== null && (best === null || (best.seller_rating ?? 0) < entry.seller_rating)
        ? entry
        : best,
    null,
  );

  return (
    <section
      aria-label="AI Summary"
      className={clsx(
        'relative overflow-hidden rounded-card border border-primary-100 shadow-card',
        'bg-gradient-to-br from-primary-50 via-white to-primary-50/30',
      )}
    >
      {/* Decorative gradient blob */}
      <div
        className="absolute -top-10 -right-10 h-40 w-40 rounded-full bg-primary-600/8 blur-3xl pointer-events-none"
        aria-hidden="true"
      />

      <div className="relative p-5 space-y-4">
        {/* Header */}
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold text-white badge-ai shadow-sm">
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
            AI Summary
          </span>
          <span className="text-xs text-neutral-400">Powered by comparative analysis</span>
        </div>

        {/* Summary text */}
        <p className="text-sm text-neutral-700 leading-relaxed">
          {summary.top_pick_summary}
        </p>

        {/* Caveats */}
        {summary.caveats && (
          <p className="text-xs text-neutral-500 italic border-l-2 border-neutral-200 pl-3">
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
              color="text-success-600"
            />
          )}
          {inStockEntry && (
            <HighlightChip
              icon={<Package className="h-4 w-4" />}
              label="Best Availability"
              value={inStockEntry.source}
              color="text-primary-600"
            />
          )}
          {highestRatedEntry && highestRatedEntry.seller_rating !== null && (
            <HighlightChip
              icon={<ShieldCheck className="h-4 w-4" />}
              label="Top-Rated Seller"
              value={`${highestRatedEntry.source} (${highestRatedEntry.seller_rating.toFixed(1)}/5)`}
              color="text-warning-600"
            />
          )}
        </div>
      </div>
    </section>
  );
}
