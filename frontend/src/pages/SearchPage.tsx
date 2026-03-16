import { SearchBar } from '../components/search/SearchBar';
import { useSearch } from '../hooks/useSearch';

// ─────────────────────────────────────────────
// SearchPage
// Home page — hero layout with centred search bar.
// ─────────────────────────────────────────────

export default function SearchPage() {
  const { startSearch, isSearching } = useSearch();

  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-4 py-16">
      {/* Hero */}
      <div className="mb-10 text-center max-w-xl">
        <h1 className="text-3xl font-bold text-neutral-900 mb-3 tracking-tight">
          Find the best price, instantly.
        </h1>
        <p className="text-neutral-500 text-base leading-relaxed">
          Search any product and we'll compare prices across major retailers — powered by AI.
        </p>
      </div>

      {/* Search bar */}
      <div className="w-full max-w-2xl">
        <SearchBar
          onSearch={(q) => void startSearch(q)}
          isSearching={isSearching}
        />
      </div>

      {/* Hint */}
      <p className="mt-4 text-xs text-neutral-400">
        Try{' '}
        <button
          className="underline underline-offset-2 hover:text-neutral-600 transition-colors"
          onClick={() => void startSearch('Sony WH-1000XM5 headphones')}
        >
          Sony WH-1000XM5 headphones
        </button>
        {' '}or{' '}
        <button
          className="underline underline-offset-2 hover:text-neutral-600 transition-colors"
          onClick={() => void startSearch('iPad Pro 13 inch M4')}
        >
          iPad Pro 13 M4
        </button>
      </p>
    </div>
  );
}
