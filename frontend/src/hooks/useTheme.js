/**
 * useTheme — persists and applies dark/light theme via localStorage and
 * the [data-theme] attribute on <html>. Theme state is stored in a module-level
 * singleton to avoid re-initialization when the Settings page mounts/unmounts.
 */
import { useState, useEffect, useCallback } from 'react';

const STORAGE_KEY = 'crowdshield-theme';

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) {
    meta.setAttribute('content', theme === 'dark' ? '#0B0D0F' : '#F2F4F5');
  }
}

function getInitialTheme() {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === 'dark' || stored === 'light') return stored;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

// ─── Module-level singleton so theme doesn't reset when Settings mounts ───────
const _initialTheme = getInitialTheme();
applyTheme(_initialTheme); // Apply immediately before any render to prevent flash

let _theme = _initialTheme;
const _listeners = new Set();

function setGlobalTheme(next) {
  if (next === _theme) return;
  _theme = next;
  applyTheme(_theme);
  localStorage.setItem(STORAGE_KEY, _theme);
  _listeners.forEach(fn => fn(_theme));
}

// ─── Hook ─────────────────────────────────────────────────────────────────────
export function useTheme() {
  const [theme, setTheme] = useState(() => _theme);

  useEffect(() => {
    // Subscribe to global theme changes so all instances stay in sync
    function handleChange(t) { setTheme(t); }
    _listeners.add(handleChange);
    return () => _listeners.delete(handleChange);
  }, []);

  const toggle   = useCallback(() => setGlobalTheme(_theme === 'dark' ? 'light' : 'dark'), []);
  const setDark  = useCallback(() => setGlobalTheme('dark'),  []);
  const setLight = useCallback(() => setGlobalTheme('light'), []);

  return { theme, toggle, setDark, setLight, isDark: theme === 'dark' };
}
