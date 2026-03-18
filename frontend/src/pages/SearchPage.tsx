import { SearchBar } from '../components/search/SearchBar';
import { Logo } from '../components/ui/Logo';
import { useSearch } from '../hooks/useSearch';

// ─────────────────────────────────────────────
// Suggestion chip
// ─────────────────────────────────────────────

interface SuggestionChipProps {
  label: string;
  onClick: () => void;
}

function SuggestionChip({ label, onClick }: SuggestionChipProps) {
  return (
    <button
      onClick={onClick}
      className={[
        'inline-flex items-center px-3 py-1.5 rounded-full text-xs font-medium',
        'bg-white dark:bg-dark-surface',
        'border border-primary-200 dark:border-dark-border',
        'text-primary-700 dark:text-primary-300',
        'hover:bg-primary-50 dark:hover:bg-primary-900/40 hover:border-primary-400 dark:hover:border-primary-700',
        'transition-colors duration-150 shadow-sm',
      ].join(' ')}
    >
      {label}
    </button>
  );
}

// ─────────────────────────────────────────────
// Suggestions
// ─────────────────────────────────────────────

const SUGGESTIONS = [
  'Sony WH-1000XM5 headphones',
  'iPad Pro 13 inch M4',
  'Samsung 65" 4K OLED TV',
  'MacBook Air M3',
  'Dyson V15 vacuum',
];

// ─────────────────────────────────────────────
// SearchPage
// ─────────────────────────────────────────────

export default function SearchPage() {
  const { startSearch, isSearching } = useSearch();

  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-4 py-16">
      {/* Decorative background blobs */}
      <div
        className="pointer-events-none fixed inset-0 overflow-hidden"
        aria-hidden="true"
      >
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 h-[600px] w-[600px] rounded-full bg-primary-600/8 dark:bg-primary-500/5 blur-3xl" />
        <div className="absolute bottom-1/3 right-1/4 h-[400px] w-[400px] rounded-full bg-primary-400/6 dark:bg-primary-800/10 blur-3xl" />
      </div>

      {/* Hero */}
      <div className="relative mb-10 text-center max-w-xl space-y-4">
        {/* Logo mark */}
        <div className="flex justify-center mb-6">
          <Logo size={52} textClassName="text-2xl" />
        </div>

        <h1 className="text-3xl font-bold text-neutral-900 dark:text-slate-100 tracking-tight text-balance">
          Find the best price, <span className="text-primary-600 dark:text-primary-400">instantly.</span>
        </h1>
        <p className="text-neutral-500 dark:text-slate-400 text-base leading-relaxed">
          Compare prices across major retailers in seconds — powered by AI.
        </p>
      </div>

      {/* Search bar */}
      <div className="relative w-full max-w-2xl">
        <SearchBar
          onSearch={(q) => void startSearch(q)}
          isSearching={isSearching}
        />
      </div>

      {/* Suggestion chips */}
      <div className="relative mt-6 flex flex-wrap items-center justify-center gap-2 max-w-xl">
        <span className="text-xs text-neutral-400 dark:text-slate-500 mr-1">Try:</span>
        {SUGGESTIONS.map((s) => (
          <SuggestionChip
            key={s}
            label={s}
            onClick={() => void startSearch(s)}
          />
        ))}
      </div>

      {/* Feature highlights */}
      <div className="relative mt-14 grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-2xl w-full">
        {[
          {
            title: 'Real-time prices',
            desc: 'Live data from Amazon, Best Buy, Walmart, and more.',
          },
          {
            title: 'AI-powered analysis',
            desc: 'Smart summaries tell you the best deal in plain English.',
          },
          {
            title: 'Alternatives surfaced',
            desc: 'Discover related models you might not have considered.',
          },
        ].map((f) => (
          <div
            key={f.title}
            className={[
              'rounded-card p-4 text-center',
              'bg-white/70 dark:bg-dark-surface/60',
              'border border-primary-100 dark:border-dark-border',
              'backdrop-blur-sm shadow-sm',
            ].join(' ')}
          >
            <p className="text-sm font-semibold text-neutral-800 dark:text-slate-200 mb-1">
              {f.title}
            </p>
            <p className="text-xs text-neutral-500 dark:text-slate-400 leading-relaxed">
              {f.desc}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
