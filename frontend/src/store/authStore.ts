import { create } from 'zustand';

// ─────────────────────────────────────────────
// State interface
// ─────────────────────────────────────────────

export interface AuthState {
  token: string | null;
  isAuthenticated: boolean;
  adminExists: boolean | null; // null = not yet checked

  login: (token: string) => void;
  logout: () => void;
  setAdminExists: (v: boolean) => void;
}

const STORAGE_KEY = 'shopcompare_token';

// ─────────────────────────────────────────────
// Store
// ─────────────────────────────────────────────

export const useAuthStore = create<AuthState>((set) => {
  // Load token from localStorage on initialisation
  const stored = localStorage.getItem(STORAGE_KEY);
  const initialToken = stored ?? null;

  return {
    token: initialToken,
    isAuthenticated: initialToken !== null,
    adminExists: null,

    login: (token: string) => {
      localStorage.setItem(STORAGE_KEY, token);
      set({ token, isAuthenticated: true });
    },

    logout: () => {
      localStorage.removeItem(STORAGE_KEY);
      set({ token: null, isAuthenticated: false });
    },

    setAdminExists: (v: boolean) => {
      set({ adminExists: v });
    },
  };
});
