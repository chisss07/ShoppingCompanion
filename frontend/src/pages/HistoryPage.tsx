import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { History, Search, Trash2, AlertCircle, Clock, TrendingDown } from 'lucide-react';
import { clsx } from 'clsx';
import { useSearchStore } from '../store/searchStore';
import { useSearch } from '../hooks/useSearch';
import { formatPrice } from '../services/api';

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case 'complete':
      return 'bg-success-100 text-success-700';
    case 'failed':
      return 'bg-danger-100 text-danger-700';
    case 'processing':
      return 'bg-primary-100 text-primary-700';
    default:
      return 'bg-neutral-100 text-neutral-500';
  }
}

// ─────────────────────────────────────────────
// HistoryPage
// ─────────────────────────────────────────────

export default function HistoryPage() {
  const navigate = useNavigate();
  const { startSearch } = useSearch();

  const {
    history,
    historyTotal,
    historyLoading,
    historyError,
    loadHistory,
    deleteHistory,
  } = useSearchStore();

  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const [confirmClearAll, setConfirmClearAll] = useState(false);
  const LIMIT = 20;

  const load = useCallback(
    (pageNum: number, query: string) => {
      void loadHistory(pageNum, LIMIT, query || undefined);
    },
    [loadHistory],
  );

  useEffect(() => {
    load(1, '');
  }, [load]);

  const handleSearch = () => {
    setPage(1);
    load(1, q);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') handleSearch();
  };

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
    load(newPage, q);
  };

  const handleClearAll = () => {
    if (!confirmClearAll) {
      setConfirmClearAll(true);
      setTimeout(() => setConfirmClearAll(false), 3000);
      return;
    }
    void deleteHistory();
    setConfirmClearAll(false);
  };

  const totalPages = Math.ceil(historyTotal / LIMIT);

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <History className="h-5 w-5 text-neutral-500" aria-hidden="true" />
          <div>
            <h1 className="text-xl font-bold text-neutral-900">Search history</h1>
            <p className="text-xs text-neutral-500 mt-0.5">
              {historyTotal} search{historyTotal !== 1 ? 'es' : ''}
            </p>
          </div>
        </div>

        {history.length > 0 && (
          <button
            onClick={handleClearAll}
            className={clsx(
              'flex items-center gap-1.5 text-sm font-medium px-3 py-1.5 rounded-lg transition-colors duration-200',
              confirmClearAll
                ? 'bg-danger-600 text-white hover:bg-danger-700'
                : 'text-neutral-500 hover:bg-neutral-100 hover:text-danger-600',
            )}
            aria-label="Clear all history"
          >
            <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
            {confirmClearAll ? 'Confirm clear' : 'Clear all'}
          </button>
        )}
      </div>

      {/* Search filter */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400 pointer-events-none"
            aria-hidden="true"
          />
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Filter by product name…"
            aria-label="Filter history"
            className={clsx(
              'w-full pl-9 pr-4 py-2 text-sm rounded-lg border border-neutral-200 bg-white',
              'focus:outline-none focus:ring-2 focus:ring-primary-600 focus:border-primary-600',
              'placeholder:text-neutral-400 text-neutral-900',
            )}
          />
        </div>
        <button
          onClick={handleSearch}
          className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors duration-150"
        >
          Filter
        </button>
      </div>

      {/* Error */}
      {historyError && (
        <div role="alert" className="flex items-start gap-3 bg-danger-50 border border-danger-200 rounded-lg p-4">
          <AlertCircle className="h-5 w-5 text-danger-500 flex-shrink-0 mt-0.5" aria-hidden="true" />
          <p className="text-sm text-danger-700">{historyError}</p>
        </div>
      )}

      {/* Loading skeleton */}
      {historyLoading && (
        <ul className="space-y-2" aria-label="Loading history" aria-busy="true">
          {Array.from({ length: 5 }, (_, i) => (
            <li key={i} className="bg-white border border-neutral-200 rounded-lg p-4 animate-pulse">
              <div className="h-3.5 bg-neutral-200 rounded w-3/4 mb-2" />
              <div className="h-3 bg-neutral-100 rounded w-1/3" />
            </li>
          ))}
        </ul>
      )}

      {/* History list */}
      {!historyLoading && history.length === 0 && (
        <div className="text-center py-20 text-neutral-400">
          <History className="h-12 w-12 mx-auto mb-3 opacity-30" aria-hidden="true" />
          <p className="text-sm font-medium">No searches yet</p>
          <p className="text-xs mt-1">Your search history will appear here.</p>
        </div>
      )}

      {!historyLoading && history.length > 0 && (
        <ul className="space-y-2" role="list" aria-label="Search history">
          {history.map((item) => (
            <li
              key={item.session_id}
              className={clsx(
                'group bg-white border border-neutral-200 rounded-lg p-4',
                'hover:border-neutral-300 hover:shadow-sm transition-all duration-150',
              )}
            >
              <div className="flex items-start gap-3">
                {/* Main content — clickable */}
                <button
                  onClick={() => navigate(`/results/${item.session_id}`)}
                  className="flex-1 text-left min-w-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-600 rounded"
                  aria-label={`View results for: ${item.query_text}`}
                >
                  <div className="flex items-start justify-between gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-neutral-900 leading-snug">
                      {item.query_text}
                    </span>
                    <span
                      className={clsx(
                        'text-xs font-medium px-2 py-0.5 rounded-full capitalize flex-shrink-0',
                        statusBadgeClass(item.status),
                      )}
                    >
                      {item.status}
                    </span>
                  </div>

                  <div className="flex items-center gap-3 mt-1.5 flex-wrap">
                    <span className="flex items-center gap-1 text-xs text-neutral-400">
                      <Clock className="h-3 w-3" aria-hidden="true" />
                      {formatDate(item.created_at)}
                    </span>

                    {item.result_count !== null && item.result_count > 0 && (
                      <span className="text-xs text-neutral-400">
                        {item.result_count} listing{item.result_count !== 1 ? 's' : ''}
                      </span>
                    )}

                    {item.best_price !== null && item.best_source && (
                      <span className="flex items-center gap-1 text-xs text-success-700 font-medium">
                        <TrendingDown className="h-3 w-3" aria-hidden="true" />
                        {formatPrice(item.best_price)} at {item.best_source}
                      </span>
                    )}
                  </div>
                </button>

                {/* Actions */}
                <div className="flex items-center gap-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
                  <button
                    onClick={() => void startSearch(item.query_text)}
                    aria-label={`Re-search: ${item.query_text}`}
                    className="p-1.5 rounded-lg text-neutral-400 hover:text-primary-600 hover:bg-primary-50 transition-colors duration-150"
                    title="Search again"
                  >
                    <Search className="h-3.5 w-3.5" aria-hidden="true" />
                  </button>
                  <button
                    onClick={() => void deleteHistory(item.session_id)}
                    aria-label={`Delete: ${item.query_text}`}
                    className="p-1.5 rounded-lg text-neutral-400 hover:text-danger-600 hover:bg-danger-50 transition-colors duration-150"
                    title="Delete"
                  >
                    <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <nav aria-label="History pagination" className="flex items-center justify-center gap-2">
          <button
            onClick={() => handlePageChange(page - 1)}
            disabled={page <= 1}
            className="px-3 py-1.5 text-sm rounded-lg border border-neutral-200 text-neutral-600 hover:bg-neutral-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Previous
          </button>
          <span className="text-xs text-neutral-500">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => handlePageChange(page + 1)}
            disabled={page >= totalPages}
            className="px-3 py-1.5 text-sm rounded-lg border border-neutral-200 text-neutral-600 hover:bg-neutral-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Next
          </button>
        </nav>
      )}
    </div>
  );
}
