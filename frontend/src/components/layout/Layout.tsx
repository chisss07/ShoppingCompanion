import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';

// ─────────────────────────────────────────────
// Layout
// Root layout wrapping all routes.
// Left sidebar (280px) + main content area.
// ─────────────────────────────────────────────

export default function Layout() {
  return (
    <div className="flex h-screen overflow-hidden bg-neutral-100">
      {/* Sidebar — hidden on mobile, visible md+ */}
      <div className="hidden md:flex">
        <Sidebar />
      </div>

      {/* Main content */}
      <main
        id="main-content"
        className="flex-1 overflow-y-auto focus:outline-none"
        tabIndex={-1}
        aria-label="Main content"
      >
        <Outlet />
      </main>
    </div>
  );
}
