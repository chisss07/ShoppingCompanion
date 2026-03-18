import axios from 'axios';
import type {
  SearchSession,
  SearchRequest,
  SearchResults,
  HistoryItem,
  HistoryListResponse,
} from '../types';

// ─────────────────────────────────────────────
// Axios instance
// ─────────────────────────────────────────────

const baseURL = import.meta.env['VITE_API_BASE_URL'] ?? '/api/v1';

export const apiClient = axios.create({
  baseURL,
  timeout: 30_000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

// Request interceptor — attach Bearer token from authStore when present
apiClient.interceptors.request.use((config) => {
  // Import lazily to avoid circular dependency at module init time
  const token = localStorage.getItem('shopcompare_token');
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor — normalise error shape
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const message: string =
      // eslint-disable-next-line @typescript-eslint/no-unsafe-member-access
      error?.response?.data?.detail ??
      // eslint-disable-next-line @typescript-eslint/no-unsafe-member-access
      error?.response?.data?.message ??
      error?.message ??
      'An unexpected error occurred.';
    return Promise.reject(new Error(message));
  },
);

// ─────────────────────────────────────────────
// Auth API
// ─────────────────────────────────────────────

export interface AuthStatusResponse {
  admin_exists: boolean;
}

export interface AuthTokenResponse {
  access_token: string;
}

export interface SettingEntry {
  key: string;
  masked_value: string;
  is_set: boolean;
}

export interface UpdateSettingsResponse {
  updated: string[];
}

export const authApi = {
  /**
   * Check whether an admin account has been created yet.
   */
  getStatus: async (): Promise<AuthStatusResponse> => {
    const { data } = await apiClient.get<AuthStatusResponse>('/auth/status');
    return data;
  },

  /**
   * Create the first admin account (setup flow).
   */
  setup: async (username: string, password: string): Promise<AuthTokenResponse> => {
    const { data } = await apiClient.post<AuthTokenResponse>('/auth/setup', {
      username,
      password,
    });
    return data;
  },

  /**
   * Authenticate with username and password.
   */
  login: async (username: string, password: string): Promise<AuthTokenResponse> => {
    const { data } = await apiClient.post<AuthTokenResponse>('/auth/login', {
      username,
      password,
    });
    return data;
  },
};

// ─────────────────────────────────────────────
// Settings API
// ─────────────────────────────────────────────

export const settingsApi = {
  /**
   * Retrieve current API key settings (masked values).
   */
  getSettings: async (): Promise<SettingEntry[]> => {
    const { data } = await apiClient.get<SettingEntry[]>('/settings');
    return data;
  },

  /**
   * Update one or more API key settings.
   */
  updateSettings: async (updates: Record<string, string>): Promise<UpdateSettingsResponse> => {
    const { data } = await apiClient.put<UpdateSettingsResponse>('/settings', updates);
    return data;
  },
};

// ─────────────────────────────────────────────
// Search API
// ─────────────────────────────────────────────

export const searchApi = {
  /**
   * Create a new search session and start the search.
   */
  create: async (
    query: string,
    options?: Partial<SearchRequest>,
  ): Promise<SearchSession> => {
    const { data } = await apiClient.post<SearchSession>('/search', {
      query,
      ...options,
    });
    return data;
  },

  /**
   * Poll the status of an existing search session.
   */
  getStatus: async (sessionId: string): Promise<SearchSession> => {
    const { data } = await apiClient.get<SearchSession>(`/search/${sessionId}/status`);
    return data;
  },

  /**
   * Fetch the full results for a completed search session.
   */
  getResults: async (sessionId: string): Promise<SearchResults> => {
    const { data } = await apiClient.get<SearchResults>(`/search/${sessionId}/results`);
    return data;
  },

  /**
   * Request a background re-check / refresh of prices for an existing session.
   */
  refresh: async (sessionId: string): Promise<SearchSession> => {
    const { data } = await apiClient.post<SearchSession>(`/search/${sessionId}/refresh`);
    return data;
  },
};

// ─────────────────────────────────────────────
// History API
// ─────────────────────────────────────────────

export const historyApi = {
  /**
   * List paginated search history, optionally filtered by a query string.
   */
  list: async (
    page = 1,
    limit = 20,
    q?: string,
  ): Promise<HistoryListResponse> => {
    const params: Record<string, unknown> = { page, limit };
    if (q) params['q'] = q;
    const { data } = await apiClient.get<HistoryListResponse>('/history', { params });
    return data;
  },

  /**
   * Delete a single history entry.
   */
  delete: async (sessionId: string): Promise<void> => {
    await apiClient.delete(`/history/${sessionId}`);
  },

  /**
   * Delete all history entries for the current user.
   */
  deleteAll: async (): Promise<void> => {
    await apiClient.delete('/history');
  },
};

// ─────────────────────────────────────────────
// Utility — format price to locale string
// ─────────────────────────────────────────────

export const formatPrice = (price: number): string =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(price);

export const formatHistoryItem = (item: HistoryItem) => ({
  ...item,
  bestPriceFormatted: item.best_price !== null ? formatPrice(item.best_price) : null,
});
