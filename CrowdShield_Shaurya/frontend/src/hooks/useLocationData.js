/**
 * useLocationData — polls the location backend heatmap endpoint
 * and manages opt-in location sharing.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { fetchHeatmap, fetchAreas, fetchLocationStatus, postLocationUpdate } from '../api/locationApi';

const POLL_MS = 5000;
const SHARE_INTERVAL_MS = 15000;   // How often to upload own location (if sharing)
const LOCATION_PERM_KEY = 'crowdshield-location-sharing';

function anonymousSessionId() {
  let id = sessionStorage.getItem('cs-session');
  if (!id) {
    id = Math.random().toString(36).slice(2) + Date.now().toString(36);
    sessionStorage.setItem('cs-session', id);
  }
  return id;
}

// Realistic synthetic simulation cells when demo mode is active
function generateFrontendDemoData(scenario = 'normal', role = 'manager') {
  const now_iso = new Date().toISOString();
  const cells_meta = [
    { cell_id: '18.5200_73.8570', lat: 18.5204, lon: 73.8567, name: 'Central Plaza & Main Gate' },
    { cell_id: '18.5210_73.8570', lat: 18.5214, lon: 73.8567, name: 'North Promenade' },
    { cell_id: '18.5190_73.8570', lat: 18.5194, lon: 73.8567, name: 'South Entrance Corridor' },
    { cell_id: '18.5200_73.8580', lat: 18.5204, lon: 73.8577, name: 'East Transit Hub' },
    { cell_id: '18.5200_73.8560', lat: 18.5204, lon: 73.8557, name: 'West Food Court Alley' },
    { cell_id: '18.5210_73.8580', lat: 18.5214, lon: 73.8577, name: 'Northeast Overflow Grounds' },
  ];

  let densities, trends, risk_levels, risk_scores;
  if (scenario === 'buildup') {
    densities = [68, 42, 54, 32, 26, 14];
    trends = ['RISING', 'RISING', 'RISING', 'STABLE', 'STABLE', 'STABLE'];
    risk_levels = ['HIGH', 'MEDIUM', 'HIGH', 'LOW', 'LOW', 'LOW'];
    risk_scores = [74.0, 48.0, 66.0, 28.0, 22.0, 12.0];
  } else if (scenario === 'critical') {
    densities = [112, 78, 88, 55, 44, 22];
    trends = ['RISING', 'RISING', 'RISING', 'RISING', 'STABLE', 'STABLE'];
    risk_levels = ['CRITICAL', 'HIGH', 'CRITICAL', 'MEDIUM', 'MEDIUM', 'LOW'];
    risk_scores = [94.0, 78.0, 88.0, 52.0, 46.0, 18.0];
  } else if (scenario === 'dispersal') {
    densities = [32, 18, 20, 42, 16, 35];
    trends = ['FALLING', 'FALLING', 'FALLING', 'STABLE', 'FALLING', 'RISING'];
    risk_levels = ['MEDIUM', 'LOW', 'LOW', 'LOW', 'LOW', 'LOW'];
    risk_scores = [38.0, 20.0, 22.0, 24.0, 18.0, 22.0];
  } else {
    densities = [24, 18, 20, 15, 12, 8];
    trends = ['STABLE', 'STABLE', 'STABLE', 'STABLE', 'STABLE', 'STABLE'];
    risk_levels = ['LOW', 'LOW', 'LOW', 'LOW', 'LOW', 'LOW'];
    risk_scores = [18.0, 14.0, 16.0, 12.0, 10.0, 6.0];
  }

  const cells = cells_meta.map((m, idx) => {
    const d = densities[idx];
    const r_lvl = risk_levels[idx];
    const r_score = risk_scores[idx];
    const crowd_status = r_lvl === 'CRITICAL' ? 'Crowded' : (r_lvl === 'HIGH' || r_lvl === 'MEDIUM' ? 'Moderate' : 'Low');

    if (role === 'user') {
      return {
        cell_id: m.cell_id,
        name: m.name,
        latitude: m.lat,
        longitude: m.lon,
        lat: m.lat,
        lon: m.lon,
        crowd_status,
        safe_guidance: crowd_status === 'Crowded' ? `High activity at ${m.name}. Recommended alternate route: Northeast Overflow Grounds.` : `Clear and smooth passage at ${m.name}.`,
        wayfinding: `Follow pedestrian wayfinding signs toward open grounds.`,
        safer_area: crowd_status === 'Crowded' ? 'Northeast Overflow Grounds' : null,
        last_updated: now_iso,
      };
    }

    return {
      cell_id: m.cell_id,
      name: m.name,
      latitude: m.lat,
      longitude: m.lon,
      lat: m.lat,
      lon: m.lon,
      density: d,
      active_sessions: d,
      confidence: Math.min(d / 20.0, 1.0),
      trend: trends[idx],
      risk_score: r_score,
      risk_level: r_lvl,
      risk_cause: 'GPS signal concentration + upward surge',
      action: r_lvl === 'CRITICAL' ? `IMMEDIATE ACCESS CONTROL: Restrict inflow to ${m.name}` : `Monitor ${m.name} ingress rates`,
      safe_alternative: 'Northeast Overflow Grounds',
      last_updated: now_iso,
    };
  });

  const areas = cells.filter(c => role === 'user' ? (c.crowd_status === 'Moderate' || c.crowd_status === 'Crowded') : (c.risk_level === 'MEDIUM' || c.risk_level === 'HIGH' || c.risk_level === 'CRITICAL'));

  return {
    heatmap: {
      timestamp: now_iso,
      role,
      demo_mode: true,
      demo_scenario: scenario,
      cell_count: cells.length,
      cells,
    },
    areas: {
      timestamp: now_iso,
      role,
      demo_mode: true,
      demo_scenario: scenario,
      area_count: areas.length,
      areas,
    },
    serverStatus: {
      status: 'active',
      demo_mode: true,
      total_cells: cells.length,
      active_sessions: densities.reduce((a, b) => a + b, 0),
    }
  };
}

export function useLocationData(role = 'manager') {
  const [heatmap, setHeatmap]       = useState(null);
  const [areas, setAreas]           = useState(null);
  const [serverStatus, setServerStatus] = useState(null);
  const [clientDemo, setClientDemo] = useState(() => localStorage.getItem('cs_loc_demo') === 'true');
  const [clientScenario, setClientScenario] = useState(() => localStorage.getItem('cs_loc_scenario') || 'normal');
  const [sharing, setSharing]       = useState(() =>
    localStorage.getItem(LOCATION_PERM_KEY) === 'true'
  );
  const [permState, setPermState]   = useState('unknown'); // 'unknown'|'granted'|'denied'|'unavailable'
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState(null);
  const [backendOnline, setBackendOnline] = useState(false);

  const mounted = useRef(true);
  const shareTimer = useRef(null);

  // ── Heatmap polling ───────────────────────────────────────────
  const pollHeatmap = useCallback(async () => {
    try {
      const [hm, ar, st] = await Promise.all([
        fetchHeatmap(role),
        fetchAreas(role),
        fetchLocationStatus(role),
      ]);
      if (!mounted.current) return;
      setHeatmap(hm);
      setAreas(ar);
      setServerStatus(st);
      setError(null);
      setBackendOnline(true);
      setLoading(false);
    } catch {
      if (!mounted.current) return;
      // Fallback: If client demo mode enabled or server down, provide mock demo data if requested
      if (clientDemo) {
        const demoData = generateFrontendDemoData(clientScenario, role);
        setHeatmap(demoData.heatmap);
        setAreas(demoData.areas);
        setServerStatus(demoData.serverStatus);
        setBackendOnline(true);
        setError(null);
      } else {
        setError('Location server unavailable');
        setBackendOnline(false);
      }
      setLoading(false);
    }
  }, [role, clientDemo, clientScenario]);

  const toggleDemoMode = useCallback(async (enabled) => {
    const nextState = enabled !== null ? Boolean(enabled) : !clientDemo;
    setClientDemo(nextState);
    localStorage.setItem('cs_loc_demo', String(nextState));
    try {
      await fetch(`${LOCATION_BASE}/api/demo/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: nextState }),
      });
    } catch { /* client-side fallback handles it */ }
    // Update local state immediately
    const demoData = generateFrontendDemoData(clientScenario, role);
    if (nextState) {
      setHeatmap(demoData.heatmap);
      setAreas(demoData.areas);
      setServerStatus(demoData.serverStatus);
      setBackendOnline(true);
      setError(null);
    } else {
      pollHeatmap();
    }
  }, [clientDemo, clientScenario, role, pollHeatmap]);

  const setScenario = useCallback(async (scenario) => {
    setClientScenario(scenario);
    localStorage.setItem('cs_loc_scenario', scenario);
    try {
      await fetch(`${LOCATION_BASE}/api/demo/scenario`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario }),
      });
    } catch { /* client-side fallback handles it */ }
    const demoData = generateFrontendDemoData(scenario, role);
    setHeatmap(demoData.heatmap);
    setAreas(demoData.areas);
    setServerStatus(demoData.serverStatus);
  }, [role]);

  useEffect(() => {
    mounted.current = true;
    pollHeatmap();
    const id = setInterval(pollHeatmap, POLL_MS);
    return () => {
      mounted.current = false;
      clearInterval(id);
    };
  }, [pollHeatmap]);

  // ── Location sharing (opt-in) ─────────────────────────────────
  const uploadLocation = useCallback(async () => {
    if (!sharing || !mounted.current) return;
    if (!('geolocation' in navigator)) {
      setPermState('unavailable');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        if (!mounted.current) return;
        setPermState('granted');
        try {
          await postLocationUpdate(
            pos.coords.latitude,
            pos.coords.longitude,
            anonymousSessionId()
          );
        } catch { /* silent — backend might be down */ }
      },
      () => {
        if (mounted.current) setPermState('denied');
      },
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 30000 }
    );
  }, [sharing]);

  useEffect(() => {
    if (sharing) {
      uploadLocation();
      shareTimer.current = setInterval(uploadLocation, SHARE_INTERVAL_MS);
    } else {
      clearInterval(shareTimer.current);
    }
    return () => clearInterval(shareTimer.current);
  }, [sharing, uploadLocation]);

  const enableSharing = useCallback(() => {
    localStorage.setItem(LOCATION_PERM_KEY, 'true');
    setSharing(true);
  }, []);

  const disableSharing = useCallback(() => {
    localStorage.setItem(LOCATION_PERM_KEY, 'false');
    setSharing(false);
  }, []);

  const isDemo = Boolean(heatmap?.demo_mode) || clientDemo;

  return {
    heatmap,
    areas,
    serverStatus,
    sharing,
    permState,
    loading,
    error,
    backendOnline: isDemo || backendOnline,
    isDemoMode: isDemo,
    demoScenario: heatmap?.demo_scenario || clientScenario,
    refetch: pollHeatmap,
    toggleDemoMode,
    setScenario,
    enableSharing,
    disableSharing,
  };
}

