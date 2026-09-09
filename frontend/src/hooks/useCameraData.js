/**
 * useCameraData — polls the camera backend and returns live threat/zone data for the selected camera.
 * Polls /live_prevention.json every 2 s and /zones every 2 s.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { fetchLivePrevention, fetchZones } from '../api/cameraApi';

const POLL_MS = 2000;

function initialState() {
  return {
    prevention: null,   // /live_prevention.json payload
    zones: null,        // /zones payload
    loading: true,
    error: null,
    lastUpdated: null,
    backendOnline: false,
  };
}

export function useCameraData(selectedCam = 'cam1', role = 'manager') {
  const [state, setState] = useState(initialState);
  const mounted = useRef(true);

  const poll = useCallback(async () => {
    try {
      const [prevention, zones] = await Promise.all([
        fetchLivePrevention(selectedCam, role),
        fetchZones(selectedCam, role),
      ]);
      if (!mounted.current) return;
      setState({
        prevention,
        zones,
        loading: false,
        error: null,
        lastUpdated: new Date(),
        backendOnline: true,
        isDemoMode: Boolean(prevention?.demo_mode),
        demoScenario: prevention?.demo_scenario || 'normal',
      });
    } catch (err) {
      if (!mounted.current) return;
      setState(prev => ({
        ...prev,
        loading: false,
        error: 'Camera backend unavailable',
        backendOnline: false,
      }));
    }
  }, [selectedCam, role]);

  useEffect(() => {
    mounted.current = true;
    poll();
    const id = setInterval(poll, POLL_MS);
    return () => {
      mounted.current = false;
      clearInterval(id);
    };
  }, [poll]);

  return { ...state, refetch: poll };
}
