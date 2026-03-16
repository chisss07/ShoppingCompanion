import { useState, useRef, type FormEvent, type KeyboardEvent } from 'react';
import { Search, X } from 'lucide-react';
import { clsx } from 'clsx';

// ─────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────

interface SearchBarProps {
  onSearch: (query: string) => void;
  isSearching?: boolean;
  initialValue?: string;
  placeholder?: string;
  compact?: boolean;
}

// ─────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────

export function SearchBar({
  onSearch,
  isSearching = false,
  initialValue = '',
  placeholder = 'Search for a product, e.g. "Sony WH-1000XM6 headphones"',
  compact = false,
}: SearchBarProps) {
  const [query, setQuery] = useState(initialValue);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || isSearching) return;
    onSearch(trimmed);
  };

  const handleClear = () => {
    setQuery('');
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') handleClear();
  };

  return (
    <form
      onSubmit={handleSubmit}
      role="search"
      aria-label="Product search"
      className={clsx('flex w-full', compact ? 'max-w-lg' : 'max-w-2xl')}
    >
      <div
        className={clsx(
          'relative flex flex-1 items-center',
          'bg-white border border-neutral-200 rounded-l-xl',
          'focus-within:border-primary-600 focus-within:ring-2 focus-within:ring-primary-600/20',
          'transition-colors duration-150',
          compact ? 'h-10' : 'h-14',
        )}
      >
        {/* Search icon */}
        <span className={clsx('pl-3 flex-shrink-0 text-neutral-400', compact ? 'pl-2.5' : 'pl-4')}>
          {isSearching ? (
            <span
              className={clsx(
                'inline-block animate-spin rounded-full border-2 border-primary-600 border-t-transparent',
                compact ? 'h-4 w-4' : 'h-5 w-5',
              )}
              aria-hidden="true"
            />
          ) : (
            <Search
              className={clsx('text-neutral-400', compact ? 'h-4 w-4' : 'h-5 w-5')}
              aria-hidden="true"
            />
          )}
        </span>

        {/* Input */}
        <input
          ref={inputRef}
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={compact ? 'Search products...' : placeholder}
          aria-label="Search products"
          autoComplete="off"
          spellCheck="false"
          className={clsx(
            'flex-1 bg-transparent text-neutral-900 placeholder:text-neutral-400',
            'focus:outline-none',
            compact ? 'px-2 text-sm' : 'px-3 text-base',
            '[appearance:textfield] [&::-webkit-search-cancel-button]:hidden',
          )}
          disabled={isSearching}
        />

        {/* Clear button */}
        {query.length > 0 && !isSearching && (
          <button
            type="button"
            onClick={handleClear}
            aria-label="Clear search"
            className={clsx(
              'flex-shrink-0 text-neutral-400 hover:text-neutral-600 transition-colors',
              compact ? 'pr-2' : 'pr-3',
            )}
          >
            <X className={compact ? 'h-3.5 w-3.5' : 'h-4 w-4'} aria-hidden="true" />
          </button>
        )}
      </div>

      {/* Submit button */}
      <button
        type="submit"
        disabled={!query.trim() || isSearching}
        aria-label="Start search"
        className={clsx(
          'flex-shrink-0 font-medium text-white',
          'bg-primary-600 hover:bg-primary-700 active:bg-primary-800',
          'border border-primary-700 rounded-r-xl',
          'transition-colors duration-150',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-600 focus-visible:ring-offset-2',
          compact ? 'px-4 h-10 text-sm' : 'px-6 h-14 text-base',
        )}
      >
        {isSearching ? (
          <span className="flex items-center gap-2">
            <span
              className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"
              aria-hidden="true"
            />
            <span className={compact ? 'hidden sm:inline' : undefined}>Searching</span>
          </span>
        ) : (
          'Search'
        )}
      </button>
    </form>
  );
}
