/**
 * CrowdShield Camera API
 * Communicates with the camera backend at http://127.0.0.1:8765
 */

export const CAMERA_BASE = 'http://127.0.0.1:8765';
export const getStreamUrl = (camId = 'cam1') => `${CAMERA_BASE}/stream?cam=${camId}`;
export const STREAM_URL  = `${CAMERA_BASE}/stream`;

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

/** Fetch the live threat/prevention snapshot. */
export async function fetchLivePrevention(camId, role = 'manager') {
  const params = new URLSearchParams();
  if (camId) params.append('cam', camId);
  if (role) params.append('role', role);
  const query = params.toString() ? `?${params.toString()}` : '';
  return fetchWithTimeout(`${CAMERA_BASE}/live_prevention.json${query}`);
}

/** Fetch per-zone density/trend/risk data. */
export async function fetchZones(camId, role = 'manager') {
  const params = new URLSearchParams();
  if (camId) params.append('cam', camId);
  if (role) params.append('role', role);
  const query = params.toString() ? `?${params.toString()}` : '';
  return fetchWithTimeout(`${CAMERA_BASE}/zones${query}`);
}

/** Toggle Camera Demo Mode on the backend. */
export async function toggleCameraDemo(enabled = null, scenario = null) {
  return fetchWithTimeout(`${CAMERA_BASE}/api/demo/toggle`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled, scenario }),
  });
}

/** Change active Demo Scenario. */
export async function setCameraScenario(scenario) {
  return fetchWithTimeout(`${CAMERA_BASE}/api/demo/scenario`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenario }),
  });
}

/** Fetch the last N density history rows as JSON. */
export async function fetchDensityHistory(camId) {
  const query = camId ? `?cam=${camId}` : '';
  return fetchWithTimeout(`${CAMERA_BASE}/history/density${query}`);
}

/** Fetch the last N risk history rows as JSON. */
export async function fetchRiskHistory(camId) {
  const query = camId ? `?cam=${camId}` : '';
  return fetchWithTimeout(`${CAMERA_BASE}/history/risk${query}`);
}

