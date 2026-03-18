import { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  History,
  Trash2,
  ChevronRight,
  Search,
  Clock,
  Settings,
  Sun,
  Moon,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useSearchStore } from '../../store/searchStore';
import { formatPrice } from '../../services/api';
import { Logo } from '../ui/Logo';
import { useDarkMode } from '../../hooks/useDarkMode';

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

function HistoryRow({
  sessionId,
  queryText,
  createdAt,
  bestPrice,
  bestSource,
  onDelete,
}: HistoryRowProps) {
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
          'hover:bg-gray-100 dark:hover:bg-primary-900/60',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400',
        )}
      >
        <div className="flex items-start gap-2 pr-6">
          <Clock
            className="h-3.5 w-3.5 text-gray-400 dark:text-primary-400/60 flex-shrink-0 mt-0.5"
            aria-hidden="true"
          />
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium text-gray-800 dark:text-primary-200 line-clamp-2 leading-snug">
              {queryText}
            </p>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <span className="text-xs text-gray-400 dark:text-primary-400/70">
                {formatRelativeTime(createdAt)}
              </span>
              {bestPrice !== null && bestSource && (
                <>
                  <span className="text-gray-300 dark:text-primary-300/50 text-xs">·</span>
                  <span className="text-xs text-green-600 dark:text-green-400 font-medium font-mono tabular-nums">
                    {formatPrice(bestPrice)}
                  </span>
                  <span className="text-xs text-gray-400 dark:text-primary-300/60 truncate">{bestSource}</span>
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
          'p-1 rounded text-primary-300/60 hover:text-red-400 hover:bg-red-500/10',
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
  const { isDark, toggle: toggleDark } = useDarkMode();

  useEffect(() => {
    void loadHistory(1, 20);
  }, [loadHistory]);

  const recentHistory = history.slice(0, 10);

  // Nav link style factory
  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    clsx(
      'flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-150',
      isActive
        ? 'bg-blue-600 text-white shadow-sm'
        : 'text-gray-600 dark:text-primary-300 hover:bg-gray-100 dark:hover:bg-primary-900/60 hover:text-gray-900 dark:hover:text-white',
    );

  return (
    <aside
      className={clsx(
        'flex flex-col h-full',
        'bg-white dark:bg-slate-800 border-r border-gray-200 dark:border-slate-700',
        'w-[280px] flex-shrink-0',
        className,
      )}
      aria-label="Sidebar navigation"
    >
      {/* Brand */}
      <div className="px-4 py-4 border-b border-gray-200 dark:border-slate-700">
        <div className="flex items-center justify-between">
          <NavLink
            to="/"
            aria-label="ShopCompare home"
          >
            <Logo
              size={28}
              textClassName="text-sm"
            />
          </NavLink>

          {/* Dark mode toggle */}
          <button
            onClick={toggleDark}
            aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            className={clsx(
              'p-1.5 rounded-lg transition-colors duration-150',
              'text-gray-500 dark:text-primary-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800',
            )}
          >
            {isDark ? (
              <Sun className="h-4 w-4" aria-hidden="true" />
            ) : (
              <Moon className="h-4 w-4" aria-hidden="true" />
            )}
          </button>
        </div>
      </div>

      {/* Navigation */}
      <nav className="px-3 pt-3 pb-1" aria-label="Main navigation">
        <ul className="space-y-0.5" role="list">
          <li>
            <NavLink to="/" end className={navLinkClass}>
              <Search className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
              Search
            </NavLink>
          </li>
          <li>
            <NavLink to="/history" className={navLinkClass}>
              <History className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
              History
            </NavLink>
          </li>
        </ul>
      </nav>

      {/* Recent searches */}
      <div className="flex-1 overflow-hidden flex flex-col px-3 pt-4">
        <div className="flex items-center justify-between mb-2 px-1">
          <span className="text-xs font-semibold text-gray-400 dark:text-primary-400/80 uppercase tracking-wider">
            Recent
          </span>
          {history.length > 0 && (
            <button
              onClick={() => void deleteHistory()}
              className="text-xs text-gray-400 dark:text-primary-400/70 hover:text-red-400 transition-colors duration-150"
              aria-label="Clear all history"
            >
              Clear all
            </button>
          )}
        </div>

        {historyLoading && (
          <div className="flex items-center justify-center py-6">
            <span
              className="h-4 w-4 animate-spin rounded-full border-2 border-primary-400 border-t-transparent"
              aria-label="Loading history"
            />
          </div>
        )}

        {!historyLoading && recentHistory.length === 0 && (
          <p className="text-xs text-primary-400/60 px-1 py-2 italic">
            No searches yet. Try searching for a product!
          </p>
        )}

        {!historyLoading && recentHistory.length > 0 && (
          <ul
            className="overflow-y-auto flex-1 space-y-0.5 -mx-1 px-1 scrollbar-hide"
            role="list"
          >
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

      {/* Footer: view all + settings */}
      <div className="border-t border-gray-200 dark:border-slate-700">
        {history.length > 10 && (
          <div className="px-4 py-2 border-b border-gray-200/50 dark:border-gray-800/50">
            <NavLink
              to="/history"
              className="flex items-center justify-center gap-1 text-xs text-gray-500 dark:text-primary-300 hover:text-gray-900 dark:hover:text-white font-medium transition-colors duration-150"
            >
              View all history
              <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
            </NavLink>
          </div>
        )}

        {/* Settings link */}
        <div className="px-3 py-3">
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-150',
                isActive
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-gray-600 dark:text-primary-300 hover:bg-gray-100 dark:hover:bg-primary-900/60 hover:text-gray-900 dark:hover:text-white',
              )
            }
          >
            <Settings className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
            Settings
          </NavLink>
        </div>
      </div>
    </aside>
  );
}
