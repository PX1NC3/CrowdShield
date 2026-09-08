/**
 * CrowdShield Location API
 * Communicates with the location aggregation server at http://127.0.0.1:8766
 */

export const LOCATION_BASE = 'http://127.0.0.1:8766';

const DEFAULT_TIMEOUT = 5000;

async function fetchWithTimeout(url, options = {}) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    clearTimeout(id);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  } catch (err) {
    clearTimeout(id);
    throw err;
  }
}

/** Fetch the full heatmap data (all cells). */
export async function fetchHeatmap(role = 'manager', demo = null, cam = null) {
  const params = new URLSearchParams();
  if (role) params.set('role', role);
  if (demo !== null && demo !== undefined) params.set('demo', demo ? '1' : '0');
  if (cam) params.set('cam', cam);
  const query = params.toString() ? `?${params.toString()}` : '';
  return fetchWithTimeout(`${LOCATION_BASE}/api/heatmap${query}`);
}

/** Fetch only medium/high/critical risk areas. */
export async function fetchAreas(role = 'manager', demo = null, cam = null) {
  const params = new URLSearchParams();
  if (role) params.set('role', role);
  if (demo !== null && demo !== undefined) params.set('demo', demo ? '1' : '0');
  if (cam) params.set('cam', cam);
  const query = params.toString() ? `?${params.toString()}` : '';
  return fetchWithTimeout(`${LOCATION_BASE}/api/areas${query}`);
}

/** Fetch location server status/health. */
export async function fetchLocationStatus(role = 'manager', demo = null) {
  const params = new URLSearchParams();
  if (role) params.set('role', role);
  if (demo !== null && demo !== undefined) params.set('demo', demo ? '1' : '0');
  const query = params.toString() ? `?${params.toString()}` : '';
  return fetchWithTimeout(`${LOCATION_BASE}/api/location/status${query}`);
}

/** Toggle Heatmap Demo Mode on the backend. */
export async function toggleHeatmapDemo(enabled = null, scenario = null) {
  return fetchWithTimeout(`${LOCATION_BASE}/api/demo/toggle`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled, scenario }),
  });
}

/** Change active Demo Scenario for Heatmap. */
export async function setHeatmapScenario(scenario) {
  return fetchWithTimeout(`${LOCATION_BASE}/api/demo/scenario`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenario }),
  });
}

/**
 * Submit a location update.
 * @param {number} lat
 * @param {number} lon
 * @param {string|null} sessionId  — optional anonymous device ID
 */
export async function postLocationUpdate(lat, lon, sessionId = null) {
  return fetchWithTimeout(`${LOCATION_BASE}/api/location/update`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      latitude: lat,
      longitude: lon,
      timestamp: new Date().toISOString(),
      session_id: sessionId,
    }),
  });
}
