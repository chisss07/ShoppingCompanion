import { create } from 'zustand';
import { searchApi, historyApi } from '../services/api';
import type {
  SearchResults,
  HistoryItem,
  WSEvent,
  WSStartedData,
  WSProgressData,
  WSSourceCheckingData,
  WSSourceCompleteData,
  SourceStep,
  SourceStepStatus,
} from '../types';

// ─────────────────────────────────────────────
// State interface
// ─────────────────────────────────────────────

export interface SearchState {
  // Current search
  currentSessionId: string | null;
  currentQuery: string;
  searchStatus: 'idle' | 'searching' | 'complete' | 'error';
  results: SearchResults | null;
  searchError: string | null;

  // Progress tracking (driven by WebSocket events)
  sourcesTotal: number;
  sourcesDone: Array<{ source_id: string; status: string }>;
  sourcesInProgress: string[];
  sourceSteps: SourceStep[];
  progressPercent: number;
  statusText: string;

  // History
  history: HistoryItem[];
  historyTotal: number;
  historyLoading: boolean;
  historyError: string | null;

  // Actions
  startSearch: (query: string) => Promise<void>;
  setWSEvent: (event: WSEvent) => void;
  setResults: (results: SearchResults) => void;
  setSearchError: (error: string) => void;
  loadHistory: (page?: number, limit?: number, q?: string) => Promise<void>;
  deleteHistory: (sessionId?: string) => Promise<void>;
  clearResults: () => void;
}

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────

const sourceIdToDisplayName = (sourceId: string): string => {
  const map: Record<string, string> = {
    amazon: 'Amazon',
    bestbuy: 'Best Buy',
    walmart: 'Walmart',
    target: 'Target',
    bhphotovideo: 'B&H Photo',
    adorama: 'Adorama',
    costco: 'Costco',
    ebay: 'eBay',
    newegg: 'Newegg',
    samsclub: "Sam's Club",
  };
  return map[sourceId] ?? sourceId.charAt(0).toUpperCase() + sourceId.slice(1);
};

const wsSourceStatusToStepStatus = (status: string): SourceStepStatus => {
  switch (status) {
    case 'success':
    case 'no_results':
      return 'complete';
    case 'error':
    case 'rate_limited':
      return 'error';
    case 'timeout':
      return 'timeout';
    default:
      return 'complete';
  }
};

// ─────────────────────────────────────────────
// Store
// ─────────────────────────────────────────────

export const useSearchStore = create<SearchState>((set, get) => ({
  // ─── Initial state ────────────────────────
  currentSessionId: null,
  currentQuery: '',
  searchStatus: 'idle',
  results: null,
  searchError: null,

  sourcesTotal: 0,
  sourcesDone: [],
  sourcesInProgress: [],
  sourceSteps: [],
  progressPercent: 0,
  statusText: '',

  history: [],
  historyTotal: 0,
  historyLoading: false,
  historyError: null,

  // ─── Actions ──────────────────────────────

  startSearch: async (query: string) => {
    set({
      currentQuery: query,
      searchStatus: 'searching',
      results: null,
      searchError: null,
      sourcesTotal: 0,
      sourcesDone: [],
      sourcesInProgress: [],
      sourceSteps: [],
      progressPercent: 0,
      statusText: 'Starting search...',
    });

    try {
      const session = await searchApi.create(query);
      set({ currentSessionId: session.session_id });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to start search.';
      set({ searchStatus: 'error', searchError: message, statusText: '' });
    }
  },

  setWSEvent: (event: WSEvent) => {
    switch (event.event) {
      case 'search:started': {
        const data = event.data as unknown as WSStartedData;
        const steps: SourceStep[] = data.sources.map((id) => ({
          source_id: id,
          display_name: sourceIdToDisplayName(id),
          status: 'pending' as SourceStepStatus,
        }));
        set({
          sourcesTotal: data.sources_total,
          sourceSteps: steps,
          statusText: `Searching ${data.sources_total} stores...`,
          progressPercent: 0,
        });
        break;
      }

      case 'search:source_checking': {
        const data = event.data as unknown as WSSourceCheckingData;
        set((s) => ({
          sourcesInProgress: [...new Set([...s.sourcesInProgress, data.source_id])],
          sourceSteps: s.sourceSteps.map((step) =>
            step.source_id === data.source_id ? { ...step, status: 'active' } : step,
          ),
          statusText: `Checking ${data.source_display_name}...`,
        }));
        break;
      }

      case 'search:source_complete': {
        const data = event.data as unknown as WSSourceCompleteData;
        const stepStatus = wsSourceStatusToStepStatus(data.status);
        const countText =
          data.results_count > 0 ? `Got ${data.results_count} result${data.results_count !== 1 ? 's' : ''} from ${data.source_display_name}` : `No results from ${data.source_display_name}`;

        set((s) => ({
          sourcesInProgress: s.sourcesInProgress.filter((id) => id !== data.source_id),
          sourcesDone: [...s.sourcesDone, { source_id: data.source_id, status: data.status }],
          sourceSteps: s.sourceSteps.map((step) =>
            step.source_id === data.source_id
              ? { ...step, status: stepStatus, results_count: data.results_count }
              : step,
          ),
          statusText: countText,
        }));
        break;
      }

      case 'search:progress': {
        const data = event.data as unknown as WSProgressData;
        set({
          progressPercent: data.percent_complete,
          sourcesDone: data.sources_done,
          sourcesInProgress: data.sources_in_progress,
          statusText: `${data.sources_complete} of ${data.sources_total} sources done...`,
        });
        break;
      }

      case 'search:comparison_ready': {
        set({ statusText: 'Ranking results...', progressPercent: 90 });
        break;
      }

      case 'search:alternatives_found': {
        set({ statusText: 'Finding alternatives...' });
        break;
      }

      case 'search:complete': {
        set({
          searchStatus: 'complete',
          progressPercent: 100,
          statusText: 'Done!',
        });
        // Refresh history in background
        void get().loadHistory();
        break;
      }

      case 'search:error': {
        const data = event.data as { fatal?: boolean; error_message?: string; source_display_name?: string };
        if (data.fatal) {
          set({
            searchStatus: 'error',
            searchError: data.error_message ?? 'Search failed.',
            statusText: '',
          });
        } else {
          // Non-fatal source error — mark step as error
          const sourceId = (event.data as { source_id?: string })['source_id'];
          if (sourceId) {
            set((s) => ({
              sourceSteps: s.sourceSteps.map((step) =>
                step.source_id === sourceId ? { ...step, status: 'error' } : step,
              ),
              statusText: `${data.source_display_name ?? sourceId} failed, continuing...`,
            }));
          }
        }
        break;
      }

      default:
        break;
    }
  },

  setResults: (results: SearchResults) => {
    set({ results, searchStatus: 'complete' });
  },

  setSearchError: (error: string) => {
    set({ searchStatus: 'error', searchError: error });
  },

  loadHistory: async (page = 1, limit = 50, q?: string) => {
    set({ historyLoading: true, historyError: null });
    try {
      const response = await historyApi.list(page, limit, q);
      set({
        history: Array.isArray(response.items) ? response.items : [],
        historyTotal: typeof response.total === 'number' ? response.total : 0,
        historyLoading: false,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load history.';
      set({ historyLoading: false, historyError: message });
    }
  },

  deleteHistory: async (sessionId?: string) => {
    try {
      if (sessionId) {
        await historyApi.delete(sessionId);
        set((s) => ({
          history: s.history.filter((h) => h.session_id !== sessionId),
          historyTotal: Math.max(0, s.historyTotal - 1),
        }));
      } else {
        await historyApi.deleteAll();
        set({ history: [], historyTotal: 0 });
      }
    } catch (err) {
      console.error('Failed to delete history:', err);
    }
  },

  clearResults: () => {
    set({
      currentSessionId: null,
      currentQuery: '',
      searchStatus: 'idle',
      results: null,
      searchError: null,
      sourcesTotal: 0,
      sourcesDone: [],
      sourcesInProgress: [],
      sourceSteps: [],
      progressPercent: 0,
      statusText: '',
    });
  },
}));
