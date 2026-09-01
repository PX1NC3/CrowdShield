/** Shared risk/trend helper utilities for the frontend. */

export const RISK_LEVELS = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];

export function riskClass(level = 'LOW') {
  const map = { LOW: 'low', MEDIUM: 'medium', HIGH: 'high', CRITICAL: 'critical' };
  return map[level] ?? 'low';
}

export function riskColor(level = 'LOW') {
  const map = {
    LOW:      'var(--risk-low)',
    MEDIUM:   'var(--risk-medium)',
    HIGH:     'var(--risk-high)',
    CRITICAL: 'var(--risk-critical)',
  };
  return map[level] ?? 'var(--risk-low)';
}

export function riskBg(level = 'LOW') {
  const map = {
    LOW:      'var(--risk-low-bg)',
    MEDIUM:   'var(--risk-medium-bg)',
    HIGH:     'var(--risk-high-bg)',
    CRITICAL: 'var(--risk-critical-bg)',
  };
  return map[level] ?? 'var(--risk-low-bg)';
}

export function trendIcon(trend = 'STABLE') {
  if (trend === 'RISING')  return '↑';
  if (trend === 'FALLING') return '↓';
  return '→';
}

export function trendClass(trend = 'STABLE') {
  if (trend === 'RISING')  return 'trend-rising';
  if (trend === 'FALLING') return 'trend-falling';
  return 'trend-stable';
}

export function formatTimestamp(ts) {
  if (!ts) return '—';
  try {
    return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return ts;
  }
}

export function riskScore100(score) {
  return Math.min(Math.round(score ?? 0), 100);
}
