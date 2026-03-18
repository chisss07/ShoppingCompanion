import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, AlertCircle, LayoutGrid, List } from 'lucide-react';
import { clsx } from 'clsx';
import { useSearchStore } from '../store/searchStore';
import { useSearch } from '../hooks/useSearch';
import { useResultsPageWebSocket } from '../hooks/useSearch';
import { searchApi } from '../services/api';
import { SearchBar } from '../components/search/SearchBar';
import { ProgressTracker } from '../components/search/ProgressTracker';
import { ComparisonCard } from '../components/results/ComparisonCard';
import { AISummaryCard } from '../components/results/AISummaryCard';
import { AlternativeCard } from '../components/results/AlternativeCard';
import type { SortOption } from '../types';

// ─────────────────────────────────────────────
// Sort selector
// ─────────────────────────────────────────────

const SORT_OPTIONS: { value: SortOption; label: string }[] = [
  { value: 'price_asc', label: 'Price: Low → High' },
  { value: 'price_desc', label: 'Price: High → Low' },
  { value: 'rating_desc', label: 'Highest Rated' },
  { value: 'deal_score_desc', label: 'Best Deal' },
];

// ─────────────────────────────────────────────
// ResultsPage
// ─────────────────────────────────────────────

export default function ResultsPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const {
    searchStatus,
    results,
    searchError,
    currentQuery,
    setResults,
    setSearchError,
  } = useSearchStore();

  const { startSearch, isSearching } = useSearch();

  const [sort, setSort] = useState<SortOption>('price_asc');
  const [gridView, setGridView] = useState(true);

  // Connect WS for this session (handles direct-URL navigation)
  useResultsPageWebSocket({ sessionId: sessionId ?? '' });

  // If navigating directly to a results URL and results aren't loaded, fetch them
  useEffect(() => {
    if (!sessionId) return;
    if (results?.session_id === sessionId) return;
    if (searchStatus === 'searching') return;

    searchApi
      .getResults(sessionId)
      .then((r) => setResults(r))
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : 'Failed to load results.';
        setSearchError(message);
      });
  }, [sessionId, results, searchStatus, setResults, setSearchError]);

  // ─── Sorted comparison ───────────────────────

  const sortedComparison = results
    ? [...results.comparison].sort((a, b) => {
        switch (sort) {
          case 'price_asc':
            return a.price - b.price;
          case 'price_desc':
            return b.price - a.price;
          case 'rating_desc':
            return (b.seller_rating ?? 0) - (a.seller_rating ?? 0);
          case 'deal_score_desc':
            return (b.deal_score ?? 0) - (a.deal_score ?? 0);
          default:
            return 0;
        }
      })
    : [];

  const isLoading = searchStatus === 'searching';
  const hasResults = searchStatus === 'complete' && results !== null;
  const hasError = searchStatus === 'error';

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
      {/* Top bar: back + search bar */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/')}
          aria-label="Back to search"
          className={clsx(
            'flex-shrink-0 p-2 rounded-lg',
            'text-neutral-500 dark:text-slate-400',
            'hover:bg-primary-50 dark:hover:bg-primary-900/30',
            'hover:text-primary-700 dark:hover:text-primary-300',
            'transition-colors',
          )}
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        </button>
        <SearchBar
          onSearch={(q) => void startSearch(q)}
          isSearching={isSearching}
          initialValue={currentQuery}
          compact
        />
      </div>

      {/* Progress tracker (visible while searching) */}
      <ProgressTracker visible={isLoading} />

      {/* Error state */}
      {hasError && (
        <div
          role="alert"
          className={clsx(
            'flex items-start gap-3 rounded-card p-4',
            'bg-danger-50 dark:bg-danger-500/10',
            'border border-danger-200 dark:border-danger-500/20',
          )}
        >
          <AlertCircle
            className="h-5 w-5 text-danger-500 flex-shrink-0 mt-0.5"
            aria-hidden="true"
          />
          <div>
            <p className="text-sm font-semibold text-danger-800 dark:text-red-400">
              Search failed
            </p>
            <p className="text-sm text-danger-700 dark:text-red-400/80 mt-0.5">
              {searchError}
            </p>
          </div>
        </div>
      )}

      {/* Results */}
      {hasResults && results && (
        <div className="space-y-6">
          {/* AI Summary */}
          <AISummaryCard results={results} />

          {/* Comparison section header */}
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-sm font-semibold text-neutral-700 dark:text-slate-300">
              Price comparison
              <span className="ml-2 text-neutral-400 dark:text-slate-500 font-normal">
                ({results.comparison.length} source
                {results.comparison.length !== 1 ? 's' : ''})
              </span>
            </h2>

            <div className="flex items-center gap-2">
              {/* Sort */}
              <select
                value={sort}
                onChange={(e) => setSort(e.target.value as SortOption)}
                aria-label="Sort results"
                className={clsx(
                  'text-xs text-neutral-600 dark:text-slate-300',
                  'bg-white dark:bg-dark-surface',
                  'border border-primary-200 dark:border-dark-border',
                  'rounded-lg px-2.5 py-1.5',
                  'focus:outline-none focus:ring-2 focus:ring-primary-600 dark:focus:ring-primary-400 focus:border-primary-600',
                  'transition-colors duration-150',
                )}
              >
                {SORT_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>

              {/* Grid/List toggle */}
              <div className="flex border border-primary-200 dark:border-dark-border rounded-lg overflow-hidden">
                <button
                  onClick={() => setGridView(true)}
                  aria-label="Grid view"
                  aria-pressed={gridView}
                  className={clsx(
                    'p-1.5 transition-colors duration-150',
                    gridView
                      ? 'bg-primary-600 dark:bg-primary-500 text-white'
                      : 'bg-white dark:bg-dark-surface text-neutral-500 dark:text-slate-400 hover:bg-primary-50 dark:hover:bg-primary-900/30',
                  )}
                >
                  <LayoutGrid className="h-3.5 w-3.5" aria-hidden="true" />
                </button>
                <button
                  onClick={() => setGridView(false)}
                  aria-label="List view"
                  aria-pressed={!gridView}
                  className={clsx(
                    'p-1.5 transition-colors duration-150',
                    !gridView
                      ? 'bg-primary-600 dark:bg-primary-500 text-white'
                      : 'bg-white dark:bg-dark-surface text-neutral-500 dark:text-slate-400 hover:bg-primary-50 dark:hover:bg-primary-900/30',
                  )}
                >
                  <List className="h-3.5 w-3.5" aria-hidden="true" />
                </button>
              </div>
            </div>
          </div>

          {/* Comparison cards */}
          <div
            className={clsx(
              gridView
                ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4'
                : 'flex flex-col gap-3',
            )}
            role="list"
            aria-label="Price comparison results"
          >
            {sortedComparison.map((entry, i) => (
              <div key={`${entry.source}-${i}`} role="listitem">
                <ComparisonCard entry={entry} isBestDeal={i === 0 && sort === 'price_asc'} />
              </div>
            ))}
          </div>

          {/* Alternatives section */}
          {results.alternatives.length > 0 && (
            <section aria-label="Alternative products">
              <h2 className="text-sm font-semibold text-neutral-700 dark:text-slate-300 mb-3">
                Alternatives & related models
                <span className="ml-2 text-neutral-400 dark:text-slate-500 font-normal">
                  ({results.alternatives.length})
                </span>
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {results.alternatives.map((alt) => (
                  <AlternativeCard
                    key={alt.product_name}
                    alternative={alt}
                    onSearch={(q) => void startSearch(q)}
                  />
                ))}
              </div>
            </section>
          )}
        </div>
      )}

      {/* Empty state while not yet searching and no results */}
      {!isLoading && !hasResults && !hasError && (
        <div className="text-center py-16 text-neutral-400 dark:text-slate-500 text-sm">
          Loading results...
        </div>
      )}
    </div>
  );
}
