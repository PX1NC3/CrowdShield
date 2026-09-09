/**
 * Heatmap.jsx
 * 
 * Camera-Derived Venue Crowd Intelligence Heatmap for CrowdShield.
 * Derived directly from real camera footage and YOLOv8n + ByteTrack detections.
 * 
 * Dual synchronized visualizations:
 *   [ 2D VENUE ] — Real spatial distribution on visible camera ground plane
 *   [ 3D VENUE ] — Shared continuous intelligence surface (Height = Density, Color = Risk)
 * 
 * Both modes share the exact same spatial crowd field with 100% mathematical correspondence.
 */

import { useState, useMemo } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useLocationData } from '../hooks/useLocationData';
import { toggleCameraDemo, setCameraScenario } from '../api/cameraApi';
import VenueHeatmap2D from '../components/VenueHeatmap2D';
import VenueHeatmap3D from '../components/VenueHeatmap3D';
import RiskBadge from '../components/RiskBadge';
import { trendIcon, trendClass } from '../utils';
import { normalizeHeatmapData, RISK_PALETTE, CAMERA_VENUE_INFO } from '../utils/venueHeatmapModel';
import './Heatmap.css';

export default function Heatmap() {
  const { role, isManager, switchRolePrompt, selectUserRole } = useAuth();

  // Active camera selection: 'cam1' (Crowd Test) vs 'cam2' (Busy Pedestrian Street Aerial)
  const [activeCam, setActiveCam] = useState('cam1');

  const {
    heatmap, areas, serverStatus,
    sharing, permState, loading, backendOnline,
    isDemoMode, demoScenario,
    toggleDemoMode, setScenario,
    enableSharing, disableSharing,
  } = useLocationData(role, activeCam);

  // Visualization mode: '2d' or '3d'
  const [viewMode, setViewMode] = useState('2d'); // '2d' | '3d'
  const [filter, setFilter] = useState('ALL'); // ALL | HIGH | CRITICAL | MODERATE | CROWDED
  const [selectedCellId, setSelectedCellId] = useState(null);

  // ── Transform raw camera-derived cells into unified normalized venue coordinates ──
  const rawCells = heatmap?.cells ?? [];
  const normalizedPoints = useMemo(() => {
    return normalizeHeatmapData(rawCells, role);
  }, [rawCells, role]);

  const detections = heatmap?.detections ?? [];

  // Selected point object
  const selectedPoint = useMemo(() => {
    if (!selectedCellId) return null;
    return normalizedPoints.find(p => p.id === selectedCellId || p.name === selectedCellId) || null;
  }, [selectedCellId, normalizedPoints]);

  const handleSelectPoint = (pt) => {
    setSelectedCellId(pt ? pt.id : null);
  };

  const handleToggleDemo = async () => {
    const nextState = !isDemoMode;
    if (toggleDemoMode) {
      await toggleDemoMode(nextState);
    }
    try {
      await toggleCameraDemo(nextState);
    } catch {}
  };

  const handleScenarioChange = async (newScenario) => {
    if (setScenario) {
      await setScenario(newScenario);
    }
    try {
      await setCameraScenario(newScenario);
    } catch {}
  };

  const cameraMeta = {
    id: activeCam,
    name: activeCam === 'cam1' ? 'CAM 1 - Crowd Test' : 'CAM 2 - Stock Footage Busy Pedestrian Street (Aerial)',
    totalPeople: heatmap?.total_people ?? (detections.length || normalizedPoints.reduce((a, b) => a + b.density, 0)),
  };

  return (
    <main className="page heatmap-page">
      {/* ── Page Header Row ─────────────────────────────────────── */}
      <div className="camera-header-row">
        <h1 className="page-title">
          <span>🏟️</span> Venue Crowd Intelligence Heatmap
          {isDemoMode ? (
            <span className="demo-badge-pill" title="Synthetic Simulation Active">
              <span className="pulse-dot" style={{ background: 'var(--accent)' }} />
              DEMO MODE
            </span>
          ) : (
            backendOnline && (
              <span className="live-pill">
                <span className="pulse-dot" style={{ background: 'var(--risk-low)' }} />
                LIVE
              </span>
            )
          )}
        </h1>

        {/* ── Role & Live/Demo Mode Bar ──────────────────────────── */}
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

      {/* ── Camera Source Selection Bar (CAM 1 <-> CAM 2) ─────────── */}
      <section className="camera-source-selector card" aria-label="Camera Ground-Plane Selection">
        <div className="cam-selector-bar">
          <div className="cam-selector-label-group">
            <span className="cam-badge-tag">CAMERA-DERIVED VENUE MODEL</span>
            <span className="cam-badge-sub">SPATIAL DATA: REAL DETECTIONS (GROUND-PLANE PROJECTION)</span>
          </div>
          <div className="cam-switch-pair">
            <button
              type="button"
              id="btn-cam1-source"
              className={`cam-source-btn ${activeCam === 'cam1' ? 'cam-source-btn--active' : ''}`}
              onClick={() => {
                setActiveCam('cam1');
                setSelectedCellId(null);
              }}
            >
              <span className="cam-source-dot" />
              <span>📹 CAM 1: Crowd Test</span>
              {activeCam === 'cam1' && (
                <span className="cam-active-count">{cameraMeta.totalPeople} pax</span>
              )}
            </button>
            <button
              type="button"
              id="btn-cam2-source"
              className={`cam-source-btn ${activeCam === 'cam2' ? 'cam-source-btn--active' : ''}`}
              onClick={() => {
                setActiveCam('cam2');
                setSelectedCellId(null);
              }}
            >
              <span className="cam-source-dot" />
              <span>📹 CAM 2: Pedestrian Street Aerial</span>
              {activeCam === 'cam2' && (
                <span className="cam-active-count">{cameraMeta.totalPeople} pax</span>
              )}
            </button>
          </div>
        </div>
      </section>

      {/* ── Venue Visualization Mode Switcher: [ 2D VENUE ] [ 3D VENUE ] ── */}
      <section className="heatmap-view-selector card" aria-label="Venue Heatmap Visualization Mode">
        <div className="venue-mode-bar">
          <div className="venue-mode-toggle-group">
            <span className="venue-mode-label">VIEW MODE:</span>
            <div className="venue-btn-pair">
              <button
                type="button"
                id="btn-venue-2d"
                className={`venue-toggle-btn ${viewMode === '2d' ? 'venue-toggle-btn--active' : ''}`}
                onClick={() => setViewMode('2d')}
                aria-pressed={viewMode === '2d'}
              >
                <span>🗺</span> [ 2D VENUE ]
              </button>
              <button
                type="button"
                id="btn-venue-3d"
                className={`venue-toggle-btn ${viewMode === '3d' ? 'venue-toggle-btn--active' : ''}`}
                onClick={() => setViewMode('3d')}
                aria-pressed={viewMode === '3d'}
              >
                <span>🧊</span> [ 3D VENUE ]
              </button>
            </div>
          </div>

          {/* ── Operational Risk & Terrain Legend ─────────────────── */}
          <div className="venue-legend-container">
            <div className="venue-risk-scale">
              <span className="legend-title">RISK LEVEL:</span>
              <div className="legend-items">
                {['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map((lvl) => {
                  const item = RISK_PALETTE[lvl];
                  return (
                    <div key={lvl} className="legend-chip" title={item.desc}>
                      <span className="legend-color-dot" style={{ background: item.hex }} />
                      <span className="legend-chip-label">{item.label}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {viewMode === '3d' && (
              <div className="venue-3d-mapping-tag">
                <span className="mapping-text">HEIGHT = <strong>CROWD DENSITY</strong></span>
                <span className="mapping-sep">·</span>
                <span className="mapping-text">COLOUR = <strong>RISK LEVEL</strong></span>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* ── Demo Scenario Controls (Shared across both 2D and 3D) ──── */}
      {isDemoMode && (
        <section className="demo-controls-card card animate-slide-in">
          <div className="demo-controls-header">
            <span className="demo-tag">DEMO SIMULATION SCENARIOS</span>
            <span className="demo-hint">
              Simulates crowd distribution, continuous heat dispersion &amp; 3D terrain elevation on real spatial coordinates
            </span>
          </div>
          <div className="scenario-buttons">
            {[
              { id: 'normal', label: '1. Normal Crowd', icon: '🟢' },
              { id: 'buildup', label: '2. Crowd Build-up', icon: '🟡' },
              { id: 'critical', label: '3. High/Critical Risk', icon: '🔴' },
              { id: 'dispersal', label: '4. Dispersal', icon: '🔵' },
            ].map((sc) => (
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

      {/* ── Server Offline Alert ─────────────────────────────────── */}
      {!backendOnline && !loading && !isDemoMode && (
        <div className="error-banner" role="alert">
          <span>⚡</span>
          Location server offline — toggle <em>DEMO</em> mode above or launch <code>location_server.py</code>.
        </div>
      )}

      {/* ── Privacy & Opt-in Ground Signal Indicator ─────────────── */}
      <div className="heatmap-privacy card">
        <div className="heatmap-privacy__info">
          <span className="heatmap-privacy__icon">🔒</span>
          <div>
            <span className="heatmap-privacy__title">Camera Ground-Plane Spatial Mapping</span>
            <span className="heatmap-privacy__desc">
              Visible ground-plane model X ∈ [0, 1], Y ∈ [0, 1] · Source: {cameraMeta.name} · {cameraMeta.totalPeople} real people detected
            </span>
          </div>
        </div>
        <label className="toggle" htmlFor="location-toggle">
          <input
            id="location-toggle"
            type="checkbox"
            checked={sharing}
            onChange={(e) => (e.target.checked ? enableSharing() : disableSharing())}
          />
          <span className="toggle-track"><span className="toggle-thumb" /></span>
          <span className="sr-only">{sharing ? 'Disable' : 'Enable'} location sharing</span>
        </label>
      </div>

      {permState === 'denied' && (
        <p className="heatmap-perm-warning">
          ⚠ Location permission denied. Enable it in browser settings.
        </p>
      )}

      {/* ── Filter Chips ────────────────────────────────────────── */}
      <div className="heatmap-filters" role="group" aria-label="Crowd filter">
        {isManager
          ? ['ALL', 'HIGH', 'CRITICAL'].map((f) => (
              <button
                key={f}
                className={`heatmap-filter-btn ${filter === f ? 'heatmap-filter-btn--active' : ''}`}
                onClick={() => setFilter(f)}
                aria-pressed={filter === f}
              >
                {f}
              </button>
            ))
          : ['ALL', 'MODERATE', 'CROWDED'].map((f) => (
              <button
                key={f}
                className={`heatmap-filter-btn ${filter === f ? 'heatmap-filter-btn--active' : ''}`}
                onClick={() => setFilter(f)}
                aria-pressed={filter === f}
              >
                {f === 'ALL' ? 'All Areas' : f === 'MODERATE' ? 'Moderate Flow' : 'Busy Areas'}
              </button>
            ))}
      </div>

      {/* ── Main Visualization Area: 2D VENUE vs 3D VENUE ───────── */}
      <section className="venue-visualizer-section card" aria-label="Venue Heatmap Display">
        {viewMode === '2d' ? (
          <VenueHeatmap2D
            points={normalizedPoints}
            detections={detections}
            cameraInfo={cameraMeta}
            selectedPoint={selectedPoint}
            onSelectPoint={handleSelectPoint}
            isManager={isManager}
            filter={filter}
          />
        ) : (
          <VenueHeatmap3D
            points={normalizedPoints}
            detections={detections}
            cameraInfo={cameraMeta}
            selectedPoint={selectedPoint}
            onSelectPoint={handleSelectPoint}
            isManager={isManager}
            filter={filter}
          />
        )}
      </section>

      {/* ── Selected Hotspot Detail Card ─────────────────────────── */}
      {selectedPoint && (
        <section className="cell-detail card animate-slide-in" aria-label="Selected venue area detail">
          <div className="cell-detail__header">
            <div>
              <strong className="cell-detail__id">{selectedPoint.name}</strong>
              <span className="cell-detail__sector" style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                SPATIAL REGION: {selectedPoint.spatialCoord || `X ${selectedPoint.x.toFixed(2)} / Y ${selectedPoint.y.toFixed(2)}`} · CAMERA GROUND PLANE
              </span>
            </div>
            {isManager ? (
              <RiskBadge level={selectedPoint.riskLevel} score={selectedPoint.riskScore} />
            ) : (
              <span className="cam-risk-tag" style={{ fontWeight: 700, background: 'var(--bg-elevated)' }}>
                {selectedPoint.crowdStatus}
              </span>
            )}
            <button
              className="btn btn-ghost"
              onClick={() => setSelectedCellId(null)}
              aria-label="Close cell detail"
              style={{ marginLeft: 'auto', padding: '4px 10px' }}
            >
              ✕
            </button>
          </div>

          {isManager ? (
            <>
              <div className="cell-detail__metrics">
                <div className="cell-detail__metric">
                  <span>Density (Pax)</span>
                  <strong>{selectedPoint.density}</strong>
                </div>
                <div className="cell-detail__metric">
                  <span>Trend</span>
                  <strong className={trendClass(selectedPoint.trend)}>
                    {trendIcon(selectedPoint.trend)} {selectedPoint.trend}
                  </strong>
                </div>
                <div className="cell-detail__metric">
                  <span>Spatial Region</span>
                  <strong style={{ color: 'var(--text-primary)' }}>{selectedPoint.spatialCoord}</strong>
                </div>
                <div className="cell-detail__metric">
                  <span>3D Density Relief</span>
                  <strong style={{ color: 'var(--text-secondary)' }}>
                    {selectedPoint.density >= 10 ? 'Prominent Peak' : (selectedPoint.density >= 4 ? 'Elevated Hill' : 'Gentle Relief')}
                  </strong>
                </div>
              </div>
              {selectedPoint.riskCause && (
                <p className="cell-detail__cause">⚠ {selectedPoint.riskCause}</p>
              )}
              {selectedPoint.action && (
                <div className="cell-detail__action">
                  <span>🛡</span>
                  <p>{selectedPoint.action}</p>
                </div>
              )}
            </>
          ) : (
            <div className="public-cell-guidance" style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
              <div className="cell-detail__action" style={{ background: 'var(--bg-elevated)' }}>
                <span>🧭</span>
                <p>{selectedPoint.action || 'Clear pedestrian passage. Follow wayfinding signage.'}</p>
              </div>
              {selectedPoint.safeAlternative && (
                <p className="safe" style={{ fontSize: '0.8rem', fontWeight: 600 }}>
                  ➔ Recommended alternate path: {selectedPoint.safeAlternative}
                </p>
              )}
            </div>
          )}
        </section>
      )}

      {/* ── Active Camera Hotspots List ──────────────────────────── */}
      <section aria-label="Camera Hotspots">
        <div className="section-heading">
          <span>🔥</span> {isManager ? `Active Camera Hotspots (${normalizedPoints.length})` : `Crowded Regions (${normalizedPoints.length})`}
        </div>
        {normalizedPoints.length === 0 ? (
          <div className="empty-state">
            <span className="empty-state-icon">✅</span>
            <span className="empty-state-title">No crowd signals</span>
            <p>All camera ground regions within normal parameters.</p>
          </div>
        ) : (
          <div className="areas-list">
            {normalizedPoints.map((pt) => {
              const [r, g, b] = [
                RISK_PALETTE[pt.riskLevel]?.rgb[0] ?? 34,
                RISK_PALETTE[pt.riskLevel]?.rgb[1] ?? 197,
                RISK_PALETTE[pt.riskLevel]?.rgb[2] ?? 94,
              ];
              const isSelected = selectedCellId === pt.id;

              return (
                <button
                  key={pt.id}
                  className={`area-card card ${isSelected ? 'area-card--selected' : ''}`}
                  onClick={() => setSelectedCellId((prev) => (prev === pt.id ? null : pt.id))}
                  aria-label={`Hotspot ${pt.name}`}
                >
                  <div className="area-card__left">
                    <div
                      className="area-card__dot"
                      style={{
                        background: `rgb(${r}, ${g}, ${b})`,
                        boxShadow: `0 0 10px rgba(${r}, ${g}, ${b}, 0.5)`,
                      }}
                    />
                    <div className="area-card__body">
                      <code className="area-card__id">{pt.name}</code>
                      <span className="area-card__sub">
                        {isManager
                          ? `Density: ${pt.density} pax · Risk: ${pt.riskLevel} · Spatial: ${pt.spatialCoord}`
                          : `Status: ${pt.crowdStatus}`}
                      </span>
                    </div>
                  </div>
                  {isManager ? (
                    <RiskBadge level={pt.riskLevel} score={pt.riskScore} size="sm" />
                  ) : (
                    <span
                      className="cam-risk-tag"
                      style={{
                        background: 'var(--bg-elevated)',
                        color: `rgb(${r}, ${g}, ${b})`,
                        fontWeight: 700,
                      }}
                    >
                      {pt.crowdStatus}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </section>

      {/* ── Ground Model Statistics Footer ───────────────────────── */}
      <div className="heatmap-server-stats">
        <span>
          📊 {normalizedPoints.length} active camera hotspots · {cameraMeta.totalPeople} real people detected · {cameraMeta.name} · CAMERA-DERIVED SPATIAL MODEL
        </span>
      </div>
    </main>
  );
}
