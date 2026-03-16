// ─────────────────────────────────────────────
// Search Session
// ─────────────────────────────────────────────

export interface SearchSession {
  session_id: string;
  status: 'pending' | 'processing' | 'complete' | 'failed';
  websocket_url: string;
  estimated_duration_seconds: number;
}

export interface SearchRequest {
  query: string;
  max_sources?: number;
  include_used?: boolean;
  price_min?: number;
  price_max?: number;
}

// ─────────────────────────────────────────────
// Results
// ─────────────────────────────────────────────

export interface PriceEntry {
  rank: number;
  source: string;
  product_title: string;
  price: number;
  shipping: string | null;
  availability: string;
  seller_rating: number | null;
  condition: string;
  deal_score: number | null;
  url: string;
  image_url: string | null;
}

export interface KeyDifference {
  attribute: string;
  target: string;
  alternative: string;
}

export interface Alternative {
  product_name: string;
  model_relationship: string;
  comparison_summary: string;
  key_differences: KeyDifference[];
  price_range: { min: number; max: number } | null;
  recommendation_strength: 'strong' | 'moderate' | 'weak';
}

export interface SearchSummary {
  top_pick_summary: string;
  alternatives_brief: string | null;
  caveats: string | null;
}

export interface SearchResults {
  session_id: string;
  query: string;
  status: string;
  completed_at: string | null;
  summary: SearchSummary | null;
  comparison: PriceEntry[];
  alternatives: Alternative[];
}

// ─────────────────────────────────────────────
// History
// ─────────────────────────────────────────────

export interface HistoryItem {
  session_id: string;
  query_text: string;
  status: string;
  created_at: string;
  completed_at: string | null;
  result_count: number | null;
  best_price: number | null;
  best_source: string | null;
}

export interface HistoryListResponse {
  items: HistoryItem[];
  total: number;
  page: number;
  limit: number;
}

// ─────────────────────────────────────────────
// WebSocket Events
// ─────────────────────────────────────────────

export interface WSEvent {
  event: string;
  search_id: string;
  timestamp: string;
  sequence: number;
  data: Record<string, unknown>;
}

export interface WSStartedData {
  query: string;
  normalized_query: string;
  sources_total: number;
  sources: string[];
  estimated_duration_ms: number;
}

export interface WSSourceCheckingData {
  source_id: string;
  source_display_name: string;
  source_logo_url: string | null;
  worker_id: string;
  attempt: number;
}

export interface WSSourceCompleteData {
  source_id: string;
  source_display_name: string;
  status: 'success' | 'no_results' | 'error' | 'timeout' | 'rate_limited';
  duration_ms: number;
  results_count: number;
}

export interface WSProgressData {
  percent_complete: number;
  sources_complete: number;
  sources_total: number;
  sources_in_progress: string[];
  sources_pending: string[];
  sources_done: Array<{ source_id: string; status: string }>;
  elapsed_ms: number;
  estimated_remaining_ms: number;
}

export interface WSCompleteData {
  total_duration_ms: number;
  sources_queried: number;
  sources_succeeded: number;
  total_listings_found: number;
  result_url: string;
  cache_ttl_seconds: number;
  next_refresh_available_at: string;
}

export interface WSErrorData {
  source_id?: string;
  source_display_name?: string;
  error_code: string;
  error_message: string;
  retryable: boolean;
  fatal: boolean;
}

// ─────────────────────────────────────────────
// Source step state (for UI)
// ─────────────────────────────────────────────

export type SourceStepStatus = 'pending' | 'active' | 'complete' | 'error' | 'timeout';

export interface SourceStep {
  source_id: string;
  display_name: string;
  status: SourceStepStatus;
  results_count?: number;
}

// ─────────────────────────────────────────────
// Sort / Filter options
// ─────────────────────────────────────────────

export type SortOption = 'price_asc' | 'price_desc' | 'rating_desc' | 'deal_score_desc';
export type HistorySortOption = 'date_desc' | 'date_asc' | 'price_asc' | 'price_desc';
