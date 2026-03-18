import { useEffect } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import Layout from './components/layout/Layout';
import SearchPage from './pages/SearchPage';
import ResultsPage from './pages/ResultsPage';
import HistoryPage from './pages/HistoryPage';
import LoginPage from './pages/LoginPage';
import SetupPage from './pages/SetupPage';
import SettingsPage from './pages/SettingsPage';
import { useAuthStore } from './store/authStore';
import { authApi } from './services/api';
import { useDarkMode } from './hooks/useDarkMode';

// ─────────────────────────────────────────────
// DarkModeInit — applies saved dark mode on mount
// Must be inside the tree so the hook registers
// ─────────────────────────────────────────────

function DarkModeInit() {
  useDarkMode();
  return null;
}

// ─────────────────────────────────────────────
// ProtectedRoute
// Redirect unauthenticated users away from /settings.
// ─────────────────────────────────────────────

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, adminExists } = useAuthStore();
  const location = useLocation();

  // Not authenticated — redirect to appropriate auth page
  if (!isAuthenticated) {
    if (adminExists === false) {
      return <Navigate to="/setup" state={{ from: location }} replace />;
    }
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

// ─────────────────────────────────────────────
// GuestRoute
// Redirect already-authenticated users away from /login and /setup.
// ─────────────────────────────────────────────

function GuestRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}

// ─────────────────────────────────────────────
// App
// ─────────────────────────────────────────────

export default function App() {
  const { setAdminExists } = useAuthStore();

  // On mount: check whether an admin account exists
  useEffect(() => {
    authApi
      .getStatus()
      .then(({ admin_exists }) => {
        setAdminExists(admin_exists);
      })
      .catch(() => {
        // Backend unreachable — leave adminExists as null
      });
  }, [setAdminExists]);

  return (
    <>
      <DarkModeInit />

      <Routes>
        {/* Auth pages — no sidebar layout */}
        <Route
          path="/login"
          element={
            <GuestRoute>
              <LoginPage />
            </GuestRoute>
          }
        />
        <Route
          path="/setup"
          element={
            <GuestRoute>
              <SetupPage />
            </GuestRoute>
          }
        />

        {/* Main app — sidebar layout */}
        <Route element={<Layout />}>
          <Route path="/" element={<SearchPage />} />
          <Route path="/results/:sessionId" element={<ResultsPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route
            path="/settings"
            element={
              <ProtectedRoute>
                <SettingsPage />
              </ProtectedRoute>
            }
          />
        </Route>

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
