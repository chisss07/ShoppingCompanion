import { useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSearchStore } from '../store/searchStore';
import { SearchWebSocket } from '../services/websocket';
import { searchApi } from '../services/api';
import type { WSEvent } from '../types';

// ─────────────────────────────────────────────
// useSearch hook
// Manages search initiation and WebSocket lifecycle.
// ─────────────────────────────────────────────

export interface UseSearchReturn {
  startSearch: (query: string) => Promise<void>;
  isSearching: boolean;
}

export function useSearch(): UseSearchReturn {
  const navigate = useNavigate();
  const wsRef = useRef<SearchWebSocket | null>(null);
  const sessionIdRef = useRef<string | null>(null);

  const {
    startSearch: storeStartSearch,
    setWSEvent,
    setResults,
    setSearchError,
    currentSessionId,
    searchStatus,
  } = useSearchStore();

  // ─── WebSocket event handler ───────────────

  const handleWSEvent = useCallback(
    (event: WSEvent) => {
      setWSEvent(event);

      if (event.event === 'search:complete') {
        const sid = sessionIdRef.current;
        if (!sid) return;

        // Fetch full results from REST after terminal event
        searchApi
          .getResults(sid)
          .then((results) => {
            setResults(results);
          })
          .catch((err: unknown) => {
            const message = err instanceof Error ? err.message : 'Failed to fetch results.';
            setSearchError(message);
          });
      }
    },
    [setWSEvent, setResults, setSearchError],
  );

  // ─── Start search ──────────────────────────

  const startSearch = useCallback(
    async (query: string) => {
      // Disconnect any previous WS
      if (wsRef.current) {
        wsRef.current.disconnect();
        wsRef.current = null;
      }

      // Initiate search in store (creates session via API)
      await storeStartSearch(query);
    },
    [storeStartSearch],
  );

  // ─── Connect WebSocket when session ID is available ─

  useEffect(() => {
    if (!currentSessionId || searchStatus !== 'searching') return;
    if (sessionIdRef.current === currentSessionId) return; // already connected

    sessionIdRef.current = currentSessionId;

    // Navigate to results page
    void navigate(`/results/${currentSessionId}`);

    // Create and connect WebSocket
    const ws = new SearchWebSocket();
    wsRef.current = ws;

    ws.on('*', handleWSEvent);
    ws.connect(currentSessionId);

    return () => {
      // Cleanup is handled by the unmount effect below
    };
  }, [currentSessionId, searchStatus, navigate, handleWSEvent]);

  // ─── Cleanup on unmount ────────────────────

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.disconnect();
        wsRef.current = null;
      }
    };
  }, []);

  return {
    startSearch,
    isSearching: searchStatus === 'searching',
  };
}

// ─────────────────────────────────────────────
// useResultsPageWebSocket
// Used by ResultsPage to connect WS for a specific session,
// supporting direct navigation via URL.
// ─────────────────────────────────────────────

export interface UseResultsWSOptions {
  sessionId: string;
  onEvent?: (event: WSEvent) => void;
}

export function useResultsPageWebSocket({ sessionId, onEvent }: UseResultsWSOptions): void {
  const wsRef = useRef<SearchWebSocket | null>(null);
  const { setWSEvent, setResults, setSearchError, searchStatus } = useSearchStore();

  const handleEvent = useCallback(
    (event: WSEvent) => {
      setWSEvent(event);
      onEvent?.(event);

      if (event.event === 'search:complete') {
        searchApi
          .getResults(sessionId)
          .then((results) => {
            setResults(results);
          })
          .catch((err: unknown) => {
            const message = err instanceof Error ? err.message : 'Failed to fetch results.';
            setSearchError(message);
          });
      }
    },
    [sessionId, setWSEvent, setResults, setSearchError, onEvent],
  );

  useEffect(() => {
    // If search is already complete (navigating back), skip WS
    if (searchStatus === 'complete') return;

    const ws = new SearchWebSocket();
    wsRef.current = ws;
    ws.on('*', handleEvent);
    ws.connect(sessionId);

    return () => {
      ws.disconnect();
      wsRef.current = null;
    };
  }, [sessionId, searchStatus, handleEvent]);
}
