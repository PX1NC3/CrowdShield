/**
 * Camera — live camera monitoring with dynamic multi-camera stream switching, alert badges, zone map and prevention panel.
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useCameraData } from '../hooks/useCameraData';
import ZoneMap from '../components/ZoneMap';
import CrowdSpatial3D from '../components/CrowdSpatial3D';
import RiskBadge from '../components/RiskBadge';
import ThreatCard from '../components/ThreatCard';
import { getStreamUrl, toggleCameraDemo, setCameraScenario } from '../api/cameraApi';
import { riskColor, trendIcon, trendClass, formatTimestamp } from '../utils';
import './Camera.css';

export default function Camera() {
  const [activeCam, setActiveCam] = useState('cam1');
  const [zoneViewMode, setZoneViewMode] = useState('3d'); // '3d' | '2d'
  const { role, isManager, switchRolePrompt, selectUserRole } = useAuth();
  const { prevention, zones, loading, error, backendOnline, lastUpdated, isDemoMode, demoScenario, refetch } = useCameraData(activeCam, role);
  const [selectedZone, setSelectedZone] = useState(null);
  const [streamError, setStreamError] = useState(false);
  const [streamReady, setStreamReady] = useState(false);
  const streamTimerRef = useRef(null);

  useEffect(() => {
    if (!backendOnline || streamError) return;
    setStreamReady(false);
    clearTimeout(streamTimerRef.current);
    streamTimerRef.current = setTimeout(() => setStreamReady(true), 1500);
    return () => clearTimeout(streamTimerRef.current);
  }, [activeCam, backendOnline, streamError, isDemoMode]);

  const zoneList    = zones?.zones ?? [];
  const threats     = prevention?.threats ?? [];
  const topThreat   = threats[0];
  const highLevel   = prevention?.highest_risk_level ?? 'LOW';
  const totalPeople = prevention?.total_people ?? 0;
  const camerasMeta = prevention?.cameras ?? {};

  // Build dynamic camera list from backend discovery
  const cameraKeys = Object.keys(camerasMeta);
  const cameraList = cameraKeys.length > 0
    ? cameraKeys.map(id => ({ id, name: camerasMeta[id].name || id.toUpperCase() }))
    : [
        { id: 'cam1', name: 'CAM 1' },
        { id: 'cam2', name: 'CAM 2' },
      ];

  const highlighted = selectedZone?.zone ?? topThreat?.zone;

  const handleCamSelect = useCallback((camId) => {
    setActiveCam(camId);
    setStreamError(false);
    setStreamReady(false);
    clearTimeout(streamTimerRef.current);
    setSelectedZone(null);
  }, []);

  const handleToggleDemo = async () => {
    try {
      await toggleCameraDemo(!isDemoMode);
      if (refetch) refetch();
    } catch { /* silent fallback */ }
  };

  const handleScenarioChange = async (newScenario) => {
    try {
      await setCameraScenario(newScenario);
      if (refetch) refetch();
    } catch { /* silent fallback */ }
  };

  return (
    <main className="page camera-page">
      <div className="camera-header-row">
        <h1 className="page-title">
          <span>📷</span> Camera Intelligence
          {isDemoMode ? (
            <span className="demo-badge-pill" title="Synthetic Simulation Active">
              <span className="pulse-dot" style={{ background: 'var(--accent)' }} />
              DEMO MODE
            </span>
          ) : (
            backendOnline && (
              <span className="live-pill">
                <span className="pulse-dot" style={{ background: 'var(--risk-low)' }} />
                LIVE ({cameraList.length} Feeds)
              </span>
            )
          )}
        </h1>

        {/* ── Role & Live/Demo Mode Bar ────────────────────────────── */}
        <div className="mode-toggle-group">
          <div className="role-switch" role="group" aria-label="User View Role">
            <button
              className={`role-btn ${isManager ? 'role-btn--active' : ''}`}
              onClick={() => {
                if (!isManager) switchRolePrompt();
              }}
              title="Click to authenticate as Manager"
            >
              👔 Manager {isManager ? '🔒' : ''}
            </button>
            <button
              className={`role-btn ${!isManager ? 'role-btn--active' : ''}`}
              onClick={selectUserRole}
              title="Switch to Public User View"
            >
              🚶 Public
            </button>
          </div>

          <div className="mode-switch">
            <button
              className={`mode-btn ${!isDemoMode ? 'mode-btn--active-live' : ''}`}
              onClick={() => isDemoMode && handleToggleDemo()}
            >
              LIVE
            </button>
            <button
              className={`mode-btn ${isDemoMode ? 'mode-btn--active-demo' : ''}`}
              onClick={() => !isDemoMode && handleToggleDemo()}
            >
              DEMO
            </button>
          </div>
        </div>
      </div>

      {/* ── Demo Scenario Controls ────────────────────────────── */}
      {isDemoMode && (
        <section className="demo-controls-card card animate-slide-in" style={{ marginBottom: 16 }}>
          <div className="demo-controls-header">
            <span className="demo-tag">CAMERA DEMO SIMULATION SCENARIOS</span>
            <span className="demo-hint">Simulates YOLO crowd surge, ByteTrack tracking, 3×3 zone density & risk escalations</span>
          </div>
          <div className="scenario-buttons">
            {[
              { id: 'normal', label: '1. Normal Crowd', icon: '🟢' },
              { id: 'buildup', label: '2. Crowd Build-up', icon: '🟡' },
              { id: 'critical', label: '3. High/Critical Risk', icon: '🔴' },
              { id: 'dispersal', label: '4. Dispersal', icon: '🔵' },
            ].map(sc => (
              <button
                key={sc.id}
                className={`scenario-btn ${demoScenario === sc.id ? 'scenario-btn--active' : ''}`}
                onClick={() => handleScenarioChange(sc.id)}
              >
                <span>{sc.icon}</span> {sc.label}
              </button>
            ))}
          </div>
        </section>
      )}

      {/* ── Dynamic Multi-Camera Switcher Bar ──────────────────────────── */}
      <section className="camera-switcher-bar card" aria-label="Camera feed selector">
        <span className="switcher-label">Active Feeds:</span>
        <div className="switcher-buttons">
          {cameraList.map((cam) => {
            const meta = camerasMeta[cam.id] || {};
            const isAlert = meta.has_serious_threat || meta.risk_level === 'HIGH' || meta.risk_level === 'CRITICAL';
            const isActive = activeCam === cam.id;

            return (
              <button
                key={cam.id}
                className={`cam-select-btn ${isActive ? 'cam-select-btn--active' : ''} ${isAlert ? 'cam-select-btn--alert' : ''}`}
                onClick={() => handleCamSelect(cam.id)}
              >
                <span className="cam-btn-text">{cam.name}</span>
                {isAlert && (
                  <span className="cam-alert-badge" title="Serious crowd threat detected on this camera!">
                    <span className="cam-alert-dot" />
                    ⚠ ALERT
                  </span>
                )}
                {meta.risk_level && (
                  <span className={`cam-risk-tag cam-risk-tag--${meta.risk_level.toLowerCase()}`}>
                    {meta.risk_level}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </section>

      {/* ── Error / Offline state ──────────────────────────────── */}
      {!backendOnline && !loading && (
        <div className="error-banner" role="alert">
          <span>⚡</span>
          Backend offline — run <code>detect.py</code> to enable multi-camera mode.
        </div>
      )}

      {/* ── MJPEG Stream ──────────────────────────────────────── */}
      <section className="camera-stream-section card" aria-label="Live camera feed">
        <div className="camera-stream-header">
          <span className="active-cam-badge">
            🔴 Live Stream — {camerasMeta[activeCam]?.name || activeCam.toUpperCase()}
          </span>
          {backendOnline && !streamReady && !streamError && (
            <span className="stream-loading-badge">⏳ Connecting…</span>
          )}
        </div>
        {backendOnline && !streamError ? (
          <div className="camera-stream-wrapper">
            <img
              key={activeCam}
              id="camera-stream"
              className={`camera-stream${streamReady ? ' camera-stream--loaded' : ''}`}
              src={getStreamUrl(activeCam)}
              alt={`Live annotated camera feed for ${activeCam}`}
              onLoad={() => setStreamReady(true)}
              onError={() => {
                // Give 3s grace before marking stream as broken
                setTimeout(() => setStreamError(true), 3000);
              }}
            />
            {!streamReady && (
              <div className="camera-stream-overlay">
                <div className="stream-spinner" />
                <span>Connecting to camera feed…</span>
              </div>
            )}
          </div>
        ) : (
          <div className="camera-stream-placeholder">
            <span className="camera-stream-placeholder__icon">📷</span>
            <span className="camera-stream-placeholder__text">
              {backendOnline ? `Stream for ${activeCam.toUpperCase()} unavailable` : 'Backend offline — run detect.py'}
            </span>
            {streamError && backendOnline && (
              <button
                className="btn btn-ghost"
                onClick={() => { setStreamError(false); }}
                style={{ marginTop: 8 }}
              >
                🔄 Retry Stream
              </button>
            )}
          </div>
        )}
      </section>

      {/* ── Overall status bar for active camera ────────────────────── */}
      <div className="camera-status-bar card">
        <div className="camera-status-item">
          <span className="camera-status-label">Active Feed</span>
          <span className="camera-status-value">{activeCam.toUpperCase()}</span>
        </div>
        {isManager ? (
          <>
            <div className="camera-status-divider" />
            <div className="camera-status-item">
              <span className="camera-status-label">People</span>
              <span className="camera-status-value">{totalPeople}</span>
            </div>
            <div className="camera-status-divider" />
            <div className="camera-status-item">
              <span className="camera-status-label">Threats</span>
              <span className="camera-status-value" style={{ color: threats.length > 0 ? 'var(--risk-high)' : 'var(--risk-low)' }}>
                {threats.length}
              </span>
            </div>
            <div className="camera-status-divider" />
            <div className="camera-status-item">
              <span className="camera-status-label">Risk Level</span>
              <RiskBadge level={highLevel} size="sm" />
            </div>
          </>
        ) : (
          <>
            <div className="camera-status-divider" />
            <div className="camera-status-item">
              <span className="camera-status-label">Crowd Status</span>
              <span
                className="camera-status-value"
                style={{
                  color: highLevel === 'Crowded' ? 'var(--risk-high)' : (highLevel === 'Moderate' ? 'var(--risk-medium)' : 'var(--risk-low)'),
                  fontWeight: 700
                }}
              >
                {highLevel || 'Low'}
              </span>
            </div>
            <div className="camera-status-divider" />
            <div className="camera-status-item">
              <span className="camera-status-label">Pathway Flow</span>
              <span className="camera-status-value safe" style={{ fontSize: '0.8rem' }}>
                {highLevel === 'Crowded' ? 'Use Alternate Route' : 'Clear Passage'}
              </span>
            </div>
          </>
        )}
        <div className="camera-status-divider" />
        <div className="camera-status-item">
          <span className="camera-status-label">Updated</span>
          <span className="camera-status-value camera-status-value--mono">
            {formatTimestamp(lastUpdated?.toISOString())}
          </span>
        </div>
      </div>

      {/* ── Zone map / 3D Spatial Model ──────────────────────────── */}
      <section aria-label="Zone density map">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
          <div className="section-heading" style={{ margin: 0 }}>
            <span>{zoneViewMode === '3d' ? '🧊' : '⬡'}</span> {isManager ? `Zone Spatial Map (${activeCam.toUpperCase()})` : `Pathway Guidance Map (${activeCam.toUpperCase()})`}
          </div>
          <div className="zone-view-toggle" role="group" aria-label="Spatial visualization view selector" style={{ display: 'flex', gap: 6 }}>
            <button
              type="button"
              className={`btn btn-sm ${zoneViewMode === '3d' ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setZoneViewMode('3d')}
              title="Interactive 3D Spatial Crowd Model"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}
            >
              <span>🧊</span> 3D Spatial
            </button>
            <button
              type="button"
              className={`btn btn-sm ${zoneViewMode === '2d' ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setZoneViewMode('2d')}
              title="Classic 2D Grid Map"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}
            >
              <span>⬡</span> 2D Grid
            </button>
          </div>
        </div>

        {zoneViewMode === '3d' ? (
          <CrowdSpatial3D
            cameraId={activeCam}
            cameraName={camerasMeta[activeCam]?.name || activeCam.toUpperCase()}
            zones={zoneList}
            prevention={prevention}
            selectedZone={selectedZone || highlighted}
            onZoneClick={setSelectedZone}
            isManager={isManager}
          />
        ) : (
          <ZoneMap
            zones={zoneList}
            onZoneClick={setSelectedZone}
            highlightZone={highlighted}
          />
        )}
      </section>

      {/* ── Selected zone detail ──────────────────────────────── */}
      {selectedZone && (
        <section className="zone-detail card animate-slide-in" aria-label="Selected zone detail">
          <div className="zone-detail__header">
            <span className="zone-detail__name">{selectedZone.zone}</span>
            {isManager ? (
              <RiskBadge level={selectedZone.risk_level} score={selectedZone.risk_score} />
            ) : (
              <span className="cam-risk-tag" style={{ fontWeight: 700, background: 'var(--bg-elevated)' }}>
                {selectedZone.crowd_status || 'Low Activity'}
              </span>
            )}
            <button
              className="zone-detail__close btn btn-ghost"
              onClick={() => setSelectedZone(null)}
              aria-label="Close zone detail"
            >✕</button>
          </div>

          {isManager ? (
            <>
              <div className="zone-detail__metrics">
                <div className="zone-detail__metric">
                  <span>Density</span><strong>{selectedZone.density}</strong>
                </div>
                <div className="zone-detail__metric">
                  <span>Trend</span>
                  <strong className={trendClass(selectedZone.trend)}>
                    {trendIcon(selectedZone.trend)} {selectedZone.trend}
                  </strong>
                </div>
                <div className="zone-detail__metric">
                  <span>Δ</span><strong>{selectedZone.density_change > 0 ? '+' : ''}{selectedZone.density_change}</strong>
                </div>
              </div>
              {selectedZone.risk_cause && (
                <p className="zone-detail__cause">{selectedZone.risk_cause}</p>
              )}
            </>
          ) : (
            <div className="public-zone-guidance" style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                {selectedZone.nav_recommendation || 'Normal pedestrian flow. Clear path.'}
              </p>
              {selectedZone.safer_alternative && (
                <p className="safe" style={{ fontSize: '0.8rem', fontWeight: 600 }}>
                  ➔ Less-crowded walking path available via {selectedZone.safer_alternative}
                </p>
              )}
            </div>
          )}
        </section>
      )}

      {/* ── Threat / Guidance cards ─────────────────────────────── */}
      <section aria-label="Active guidance notices">
        <div className="section-heading">
          <span>{isManager ? '⚠' : '🧭'}</span> {isManager ? `Active Threats (${activeCam.toUpperCase()})` : `Safe Walking Guidance (${activeCam.toUpperCase()})`}
        </div>
        {threats.length === 0 ? (
          <div className="empty-state">
            <span className="empty-state-icon">✅</span>
            <span className="empty-state-title">
              {isManager ? `No active threats on ${activeCam.toUpperCase()}` : 'All pathways clear'}
            </span>
            <p>{isManager ? 'All zones within normal parameters.' : 'Smooth walking flow across all monitored corridors.'}</p>
          </div>
        ) : (
          <div className="threats-list">
            {threats.map((t, i) => (
              <ThreatCard
                key={(t.zone || i) + i}
                threat={t}
                source="camera"
                timestamp={prevention?.timestamp}
              />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
