/**
 * Heatmap — location-based crowd density map using Leaflet.
 * Uses a canvas-based heatmap drawn manually (no external leaflet.heat dependency).
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { MapContainer, TileLayer, useMap, CircleMarker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { useAuth } from '../hooks/useAuth';
import { useLocationData } from '../hooks/useLocationData';
import { toggleHeatmapDemo, setHeatmapScenario } from '../api/locationApi';
import RiskBadge from '../components/RiskBadge';
import { riskColor, riskBg, trendIcon, trendClass } from '../utils';
import './Heatmap.css';

// ── Leaflet default marker icon fix ──────────────────────────
import L from 'leaflet';
try {
  if (L?.Icon?.Default?.prototype) {
    delete L.Icon.Default.prototype._getIconUrl;
    L.Icon.Default.mergeOptions({
      iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
      iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
      shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
    });
  }
} catch {
  /* safe ignore */
}

// Default map centre (matches demo seed data in location_server.py)
const DEFAULT_CENTER = [18.5204, 73.8567];
const DEFAULT_ZOOM   = 14;

/** Circle radius for a cell, scaled by density. */
function cellRadius(density) {
  return Math.max(18, Math.min(density * 2.5, 80));
}

/** Intensity → RGBA colour string for the heatmap gradient. */
function intensityColor(intensity, riskLevel) {
  const base = riskColor(riskLevel);
  const alpha = Math.max(0.2, Math.min(intensity * 0.75, 0.85));
  // Convert CSS var to a concrete colour via inline approach
  const colorMap = {
    LOW:      `rgba(34,197,94,${alpha})`,
    MEDIUM:   `rgba(245,158,11,${alpha})`,
    HIGH:     `rgba(249,115,22,${alpha})`,
    CRITICAL: `rgba(239,68,68,${alpha})`,
  };
  return colorMap[riskLevel] ?? `rgba(99,102,241,${alpha})`;
}

/** Auto-fit the map to visible cells. */
function MapFitter({ cells }) {
  const map = useMap();
  useEffect(() => {
    if (!cells || cells.length === 0) return;
    const bounds = cells.map(c => [c.lat, c.lon]);
    if (bounds.length > 0) {
      try { map.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 }); }
      catch { /* no-op */ }
    }
  }, [cells?.length]);
  return null;
}

export default function Heatmap() {
  const { role, isManager, switchRolePrompt, selectUserRole } = useAuth();
  const {
    heatmap, areas, serverStatus,
    sharing, permState, loading, error, backendOnline,
    isDemoMode, demoScenario, refetch,
    toggleDemoMode, setScenario,
    enableSharing, disableSharing,
  } = useLocationData(role);

  const [selectedCell, setSelectedCell] = useState(null);
  const [filter, setFilter] = useState('ALL'); // ALL | HIGH | CRITICAL

  const cells = heatmap?.cells ?? [];

  const visibleCells = cells.filter(c => {
    if (filter === 'HIGH')     return c.risk_level === 'HIGH' || c.risk_level === 'CRITICAL';
    if (filter === 'CRITICAL') return c.risk_level === 'CRITICAL';
    return true;
  });

  const handleToggleDemo = async () => {
    if (toggleDemoMode) {
      await toggleDemoMode(!isDemoMode);
    }
  };

  const handleScenarioChange = async (newScenario) => {
    if (setScenario) {
      await setScenario(newScenario);
    }
  };

  return (
    <main className="page heatmap-page">
      <div className="camera-header-row">
        <h1 className="page-title">
          <span>🗺</span> Location Heatmap
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
        <section className="demo-controls-card card animate-slide-in">
          <div className="demo-controls-header">
            <span className="demo-tag">HEATMAP DEMO SIMULATION SCENARIOS</span>
            <span className="demo-hint">Simulates GPS crowd concentration, cell aggregation, risk levels & alternate routing</span>
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

      {/* ── Error banner ──────────────────────────────────────── */}
      {!backendOnline && !loading && (
        <div className="error-banner" role="alert">
          <span>⚡</span>
          Location server offline — run <code>location_server.py</code>.
        </div>
      )}

      {/* ── Privacy / sharing toggle ──────────────────────────── */}
      <div className="heatmap-privacy card">
        <div className="heatmap-privacy__info">
          <span className="heatmap-privacy__icon">🔒</span>
          <div>
            <span className="heatmap-privacy__title">Share My Location</span>
            <span className="heatmap-privacy__desc">
              Coarse location only · Anonymous · No tracking
            </span>
          </div>
        </div>
        <label className="toggle" htmlFor="location-toggle">
          <input
            id="location-toggle"
            type="checkbox"
            checked={sharing}
            onChange={e => e.target.checked ? enableSharing() : disableSharing()}
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

      {/* ── Filter chips ──────────────────────────────────────── */}
      <div className="heatmap-filters" role="group" aria-label="Crowd filter">
        {isManager
          ? ['ALL','HIGH','CRITICAL'].map(f => (
              <button
                key={f}
                className={`heatmap-filter-btn ${filter === f ? 'heatmap-filter-btn--active' : ''}`}
                onClick={() => setFilter(f)}
                aria-pressed={filter === f}
              >
                {f}
              </button>
            ))
          : ['ALL', 'MODERATE', 'CROWDED'].map(f => (
              <button
                key={f}
                className={`heatmap-filter-btn ${filter === f ? 'heatmap-filter-btn--active' : ''}`}
                onClick={() => setFilter(f)}
                aria-pressed={filter === f}
              >
                {f === 'ALL' ? 'All Areas' : (f === 'MODERATE' ? 'Moderate Flow' : 'Busy Areas')}
              </button>
            ))}
      </div>

      {/* ── Map ───────────────────────────────────────────────── */}
      <div className="heatmap-map-container card">
        <MapContainer
          center={DEFAULT_CENTER}
          zoom={DEFAULT_ZOOM}
          className="heatmap-map"
          scrollWheelZoom
          zoomControl
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          <MapFitter cells={visibleCells} />

          {visibleCells.map(cell => {
            const crowdStatus = cell.crowd_status || (cell.risk_level === 'CRITICAL' ? 'Crowded' : (cell.risk_level === 'HIGH' ? 'Moderate' : 'Low'));
            const color = crowdStatus === 'Crowded' ? 'rgba(239,68,68,0.75)' : (crowdStatus === 'Moderate' ? 'rgba(245,158,11,0.7)' : 'rgba(34,197,94,0.65)');
            const radius = cell.density ? cellRadius(cell.density) : (crowdStatus === 'Crowded' ? 45 : (crowdStatus === 'Moderate' ? 30 : 20));

            return (
              <CircleMarker
                key={cell.cell_id}
                center={[cell.lat || cell.latitude, cell.lon || cell.longitude]}
                radius={radius}
                pathOptions={{
                  fillColor: color,
                  fillOpacity: 0.7,
                  color: color,
                  weight: selectedCell?.cell_id === cell.cell_id ? 2.5 : 1,
                  opacity: 0.9,
                }}
                eventHandlers={{
                  click: () => setSelectedCell(prev =>
                    prev?.cell_id === cell.cell_id ? null : cell
                  ),
                }}
              >
                <Popup className="heatmap-popup">
                  <div className="heatmap-popup__inner">
                    <div className="heatmap-popup__header">
                      <strong className="heatmap-popup__id">{cell.name || cell.cell_id}</strong>
                      {isManager ? (
                        <RiskBadge level={cell.risk_level} score={cell.risk_score} size="sm" />
                      ) : (
                        <span className="cam-risk-tag" style={{ background: 'var(--bg-elevated)', color: color, fontWeight: 700 }}>
                          {crowdStatus}
                        </span>
                      )}
                    </div>
                    {isManager ? (
                      <div className="heatmap-popup__metrics">
                        <span>Density: <strong>{cell.density}</strong></span>
                        <span className={trendClass(cell.trend)}>
                          Trend: <strong>{trendIcon(cell.trend)} {cell.trend}</strong>
                        </span>
                      </div>
                    ) : (
                      <div className="heatmap-popup__metrics">
                        <span>Activity: <strong>{crowdStatus}</strong></span>
                        <span>{cell.wayfinding || 'Smooth pedestrian route'}</span>
                      </div>
                    )}
                    {(cell.safe_guidance || cell.action || cell.recommended_action) && (
                      <p className="heatmap-popup__action">{cell.safe_guidance || cell.action || cell.recommended_action}</p>
                    )}
                  </div>
                </Popup>
              </CircleMarker>
            );
          })}
        </MapContainer>
      </div>

      {/* ── Selected cell detail ──────────────────────────────── */}
      {selectedCell && (
        <section className="cell-detail card animate-slide-in" aria-label="Selected cell detail">
          <div className="cell-detail__header">
            <strong className="cell-detail__id">{selectedCell.name || selectedCell.cell_id}</strong>
            {isManager ? (
              <RiskBadge level={selectedCell.risk_level} score={selectedCell.risk_score} />
            ) : (
              <span className="cam-risk-tag" style={{ fontWeight: 700, background: 'var(--bg-elevated)' }}>
                {selectedCell.crowd_status || 'Low Activity'}
              </span>
            )}
            <button
              className="btn btn-ghost"
              onClick={() => setSelectedCell(null)}
              aria-label="Close cell detail"
              style={{ marginLeft: 'auto', padding: '4px 10px' }}
            >✕</button>
          </div>

          {isManager ? (
            <>
              <div className="cell-detail__metrics">
                <div className="cell-detail__metric">
                  <span>Density</span><strong>{selectedCell.density}</strong>
                </div>
                <div className="cell-detail__metric">
                  <span>Trend</span>
                  <strong className={trendClass(selectedCell.trend)}>
                    {trendIcon(selectedCell.trend)} {selectedCell.trend}
                  </strong>
                </div>
                <div className="cell-detail__metric">
                  <span>Confidence</span><strong>{selectedCell.confidence ?? '0.9'}</strong>
                </div>
              </div>
              {selectedCell.risk_cause && (
                <p className="cell-detail__cause">⚠ {selectedCell.risk_cause}</p>
              )}
              {selectedCell.action && (
                <div className="cell-detail__action">
                  <span>🛡</span>
                  <p>{selectedCell.action}</p>
                </div>
              )}
            </>
          ) : (
            <div className="public-cell-guidance" style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
              <div className="cell-detail__action" style={{ background: 'var(--bg-elevated)' }}>
                <span>🧭</span>
                <p>{selectedCell.safe_guidance || 'Clear pedestrian passage. Follow wayfinding signage.'}</p>
              </div>
              {selectedCell.safer_area && (
                <p className="safe" style={{ fontSize: '0.8rem', fontWeight: 600 }}>
                  ➔ Recommended alternate area: {selectedCell.safer_area}
                </p>
              )}
            </div>
          )}
        </section>
      )}

      {/* ── Hot areas list ────────────────────────────────────── */}
      <section aria-label="High risk areas">
        <div className="section-heading"><span>🔥</span> High-Risk Areas</div>
        {areas?.areas?.length === 0 ? (
          <div className="empty-state">
            <span className="empty-state-icon">✅</span>
            <span className="empty-state-title">No high-risk areas</span>
            <p>All location cells within normal parameters.</p>
          </div>
        ) : (
          <div className="areas-list">
            {(areas?.areas ?? []).map(cell => (
              <button
                key={cell.cell_id}
                className={`area-card card ${selectedCell?.cell_id === cell.cell_id ? 'area-card--selected' : ''}`}
                onClick={() => setSelectedCell(prev => prev?.cell_id === cell.cell_id ? null : cell)}
                aria-label={`Area ${cell.cell_id}: ${cell.risk_level} risk, density ${cell.density}`}
              >
                <div className="area-card__left">
                  <div
                    className="area-card__dot"
                    style={{ background: intensityColor(cell.intensity, cell.risk_level) }}
                  />
                  <div className="area-card__body">
                    <code className="area-card__id">{cell.cell_id}</code>
                    <span className="area-card__sub">Density {cell.density} · {trendIcon(cell.trend)} {cell.trend}</span>
                  </div>
                </div>
                <RiskBadge level={cell.risk_level} score={cell.risk_score} size="sm" />
              </button>
            ))}
          </div>
        )}
      </section>

      {/* ── Server stats ─────────────────────────────────────── */}
      {serverStatus && (
        <div className="heatmap-server-stats">
          <span>📊 {serverStatus.total_cells} cells · {serverStatus.total_samples_in_window} signals · {serverStatus.window_minutes}min window</span>
        </div>
      )}
    </main>
  );
}
