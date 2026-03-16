import { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { History, Trash2, ChevronRight, ShoppingBag, X, Clock } from 'lucide-react';
import { clsx } from 'clsx';
import { useSearchStore } from '../../store/searchStore';
import { formatPrice } from '../../services/api';

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// ─────────────────────────────────────────────
// HistoryItem row
// ─────────────────────────────────────────────

interface HistoryRowProps {
  sessionId: string;
  queryText: string;
  createdAt: string;
  bestPrice: number | null;
  bestSource: string | null;
  onDelete: (id: string) => void;
}

function HistoryRow({ sessionId, queryText, createdAt, bestPrice, bestSource, onDelete }: HistoryRowProps) {
  const navigate = useNavigate();
  const [showDelete, setShowDelete] = useState(false);

  return (
    <li
      className="group relative"
      onMouseEnter={() => setShowDelete(true)}
      onMouseLeave={() => setShowDelete(false)}
    >
      <button
        onClick={() => navigate(`/results/${sessionId}`)}
        className={clsx(
          'w-full text-left px-3 py-2.5 rounded-lg transition-colors duration-150',
          'hover:bg-neutral-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-600',
        )}
      >
        <div className="flex items-start gap-2 pr-6">
          <Clock className="h-3.5 w-3.5 text-neutral-400 flex-shrink-0 mt-0.5" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium text-neutral-800 line-clamp-2 leading-snug">
              {queryText}
            </p>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <span className="text-xs text-neutral-400">{formatRelativeTime(createdAt)}</span>
              {bestPrice !== null && bestSource && (
                <>
                  <span className="text-neutral-300 text-xs">·</span>
                  <span className="text-xs text-success-700 font-medium font-mono tabular-nums">
                    {formatPrice(bestPrice)}
                  </span>
                  <span className="text-xs text-neutral-400 truncate">{bestSource}</span>
                </>
              )}
            </div>
          </div>
        </div>
      </button>

      {/* Delete button (appears on hover) */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onDelete(sessionId);
        }}
        aria-label={`Delete search: ${queryText}`}
        className={clsx(
          'absolute right-2 top-1/2 -translate-y-1/2',
          'p-1 rounded text-neutral-400 hover:text-danger-600 hover:bg-danger-50',
          'transition-all duration-150',
          showDelete ? 'opacity-100' : 'opacity-0 pointer-events-none',
        )}
      >
        <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    </li>
  );
}

// ─────────────────────────────────────────────
// Sidebar
// ─────────────────────────────────────────────

interface SidebarProps {
  className?: string;
}

export function Sidebar({ className }: SidebarProps) {
  const { history, historyLoading, loadHistory, deleteHistory } = useSearchStore();

  useEffect(() => {
    void loadHistory(1, 20);
  }, [loadHistory]);

  const recentHistory = history.slice(0, 10);

  return (
    <aside
      className={clsx(
        'flex flex-col h-full bg-neutral-50 border-r border-neutral-200',
        'w-[280px] flex-shrink-0',
        className,
      )}
      aria-label="Sidebar navigation"
    >
      {/* Brand */}
      <div className="px-4 py-4 border-b border-neutral-200">
        <NavLink
          to="/"
          className="flex items-center gap-2.5 group"
          aria-label="Shopping Companion home"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-600 shadow-sm">
            <ShoppingBag className="h-4.5 w-4.5 text-white" aria-hidden="true" />
          </span>
          <div>
            <span className="text-sm font-bold text-neutral-900 block leading-tight">
              Shopping
            </span>
            <span className="text-xs text-neutral-500 leading-tight">Companion</span>
          </div>
        </NavLink>
      </div>

      {/* Navigation */}
      <nav className="px-3 pt-3 pb-1" aria-label="Main navigation">
        <ul className="space-y-0.5" role="list">
          <li>
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-150',
                  isActive
                    ? 'bg-primary-100 text-primary-800'
                    : 'text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900',
                )
              }
            >
              <ShoppingBag className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
              Search
            </NavLink>
          </li>
          <li>
            <NavLink
              to="/history"
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-150',
                  isActive
                    ? 'bg-primary-100 text-primary-800'
                    : 'text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900',
                )
              }
            >
              <History className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
              History
            </NavLink>
          </li>
        </ul>
      </nav>

      {/* Recent searches */}
      <div className="flex-1 overflow-hidden flex flex-col px-3 pt-4">
        <div className="flex items-center justify-between mb-2 px-1">
          <span className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">
            Recent
          </span>
          {history.length > 0 && (
            <button
              onClick={() => void deleteHistory()}
              className="text-xs text-neutral-400 hover:text-danger-600 transition-colors duration-150"
              aria-label="Clear all history"
            >
              Clear all
            </button>
          )}
        </div>

        {historyLoading && (
          <div className="flex items-center justify-center py-6">
            <span
              className="h-4 w-4 animate-spin rounded-full border-2 border-primary-600 border-t-transparent"
              aria-label="Loading history"
            />
          </div>
        )}

        {!historyLoading && recentHistory.length === 0 && (
          <p className="text-xs text-neutral-400 px-1 py-2 italic">
            No searches yet. Try searching for a product!
          </p>
        )}

        {!historyLoading && recentHistory.length > 0 && (
          <ul className="overflow-y-auto flex-1 space-y-0.5 -mx-1 px-1" role="list">
            {recentHistory.map((item) => (
              <HistoryRow
                key={item.session_id}
                sessionId={item.session_id}
                queryText={item.query_text}
                createdAt={item.created_at}
                bestPrice={item.best_price}
                bestSource={item.best_source}
                onDelete={(id) => void deleteHistory(id)}
              />
            ))}
          </ul>
        )}
      </div>

      {/* Footer: view all */}
      {history.length > 10 && (
        <div className="px-4 py-3 border-t border-neutral-200">
          <NavLink
            to="/history"
            className="flex items-center justify-center gap-1 text-xs text-primary-600 hover:text-primary-800 font-medium transition-colors duration-150"
          >
            View all history
            <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
          </NavLink>
        </div>
      )}
    </aside>
  );
}
