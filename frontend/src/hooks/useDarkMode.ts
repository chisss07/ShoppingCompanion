import { useEffect, useState } from 'react';

const STORAGE_KEY = 'shopcompare_theme';

// ─────────────────────────────────────────────
// useDarkMode
// Reads/writes dark mode preference to localStorage and
// toggles the `dark` class on <html>.
// ─────────────────────────────────────────────

export function useDarkMode() {
  const [isDark, setIsDark] = useState<boolean>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored !== null) return stored === 'dark';
    // Fall back to OS preference
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  // Apply class to <html> whenever isDark changes
  useEffect(() => {
    const root = document.documentElement;
    if (isDark) {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    localStorage.setItem(STORAGE_KEY, isDark ? 'dark' : 'light');
  }, [isDark]);

  const toggle = () => setIsDark((prev) => !prev);

  return { isDark, toggle };
}
