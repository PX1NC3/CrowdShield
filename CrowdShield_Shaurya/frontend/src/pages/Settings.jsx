import { useState, useEffect } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../hooks/useTheme';
import { CAMERA_BASE } from '../api/cameraApi';
import { LOCATION_BASE } from '../api/locationApi';
import './Settings.css';

export default function Settings() {
  const { theme, toggle, isDark } = useTheme();
  const { role, isManager, switchRolePrompt, logout, defaultManagerPass } = useAuth();
  const [demoState, setDemoState] = useState({ camera_demo: false, heatmap_demo: false, scenario: 'normal' });

  useEffect(() => {
    fetch(`${CAMERA_BASE}/api/demo/status`)
      .then(r => r.json())
      .then(setDemoState)
      .catch(() => {});
  }, []);

  const handleToggleGlobalDemo = async (target, enabled) => {
    try {
      const url = target === 'camera' ? `${CAMERA_BASE}/api/demo/toggle` : `${LOCATION_BASE}/api/demo/toggle`;
      await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
      });
      setDemoState(prev => ({
        ...prev,
        [target === 'camera' ? 'camera_demo' : 'heatmap_demo']: enabled,
      }));
    } catch { /* silent */ }
  };

  const handleSetGlobalScenario = async (scenario) => {
    try {
      await Promise.all([
        fetch(`${CAMERA_BASE}/api/demo/scenario`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ scenario }),
        }),
        fetch(`${LOCATION_BASE}/api/demo/scenario`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ scenario }),
        }),
      ]);
      setDemoState(prev => ({ ...prev, scenario }));
    } catch { /* silent */ }
  };

  return (
    <main className="page settings-page">
      <h1 className="page-title">
        <span>⚙</span> Settings & System
      </h1>

      {/* ── Active User Role Section ────────────────────────────── */}
      <section className="settings-section card" style={{ border: isManager ? '1px solid rgba(124, 58, 237, 0.35)' : '1px solid var(--border-default)' }}>
        <div className="section-heading"><span>🛡</span> Access Role & Authorization</div>
        <div className="settings-row">
          <div>
            <span className="settings-label">Current Role</span>
            <span className="settings-desc">
              {isManager ? 'Control Center Manager (Full Access)' : 'Public Mobile User (Safe Guidance View)'}
            </span>
          </div>
          <span className={`cam-risk-tag ${isManager ? 'cam-risk-tag--high' : 'cam-risk-tag--low'}`} style={{ fontSize: '0.8rem', padding: '4px 10px' }}>
            {isManager ? '👔 MANAGER' : '🚶 PUBLIC'}
          </span>
        </div>
        <div className="settings-row" style={{ gap: 8, flexWrap: 'wrap' }}>
          <button className="btn btn-primary" onClick={switchRolePrompt}>
            🔄 Switch Role / Re-authenticate
          </button>
          <button className="btn btn-ghost" onClick={logout}>
            🚪 Logout
          </button>
        </div>
      </section>

      {/* ── Demo / Simulation Mode Section (Manager Only) ──────── */}
      {isManager && (
        <section className="settings-section card" style={{ border: '1px solid rgba(124, 58, 237, 0.3)' }}>
          <div className="section-heading"><span style={{ color: 'var(--accent)' }}>🔬</span> Location Heatmap Demo Simulation</div>
          <div className="settings-row">
            <div>
              <span className="settings-label">Heatmap Demo Mode</span>
              <span className="settings-desc">Simulate live geographic GPS cells, risk levels and prevention without GPS</span>
            </div>
            <label className="toggle" htmlFor="loc-demo-toggle">
              <input
                id="loc-demo-toggle"
                type="checkbox"
                checked={demoState.heatmap_demo}
                onChange={(e) => handleToggleGlobalDemo('heatmap', e.target.checked)}
              />
              <span className="toggle-track"><span className="toggle-thumb" /></span>
            </label>
          </div>

          <div className="settings-row" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 8 }}>
            <span className="settings-label">Active Demo Scenario:</span>
            <div className="scenario-buttons">
              {[
                { id: 'normal', label: 'Normal Crowd' },
                { id: 'buildup', label: 'Crowd Build-up' },
                { id: 'critical', label: 'High/Critical Risk' },
                { id: 'dispersal', label: 'Crowd Dispersal' },
              ].map(s => (
                <button
                  key={s.id}
                  className={`scenario-btn ${demoState.scenario === s.id ? 'scenario-btn--active' : ''}`}
                  onClick={() => handleSetGlobalScenario(s.id)}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ── Theme preference ──────────────────────────────────── */}
      <section className="settings-section card">
        <div className="section-heading"><span>🎨</span> Appearance</div>
        <div className="settings-row">
          <div>
            <span className="settings-label">Dark Mode</span>
            <span className="settings-desc">Switch between dark and light themes</span>
          </div>
          <label className="toggle" htmlFor="theme-toggle">
            <input
              id="theme-toggle"
              type="checkbox"
              checked={isDark}
              onChange={toggle}
            />
            <span className="toggle-track"><span className="toggle-thumb" /></span>
          </label>
        </div>
      </section>

      {/* ── Endpoints configuration ────────────────────────────── */}
      <section className="settings-section card">
        <div className="section-heading"><span>🔌</span> Backend Endpoints</div>
        <div className="settings-row">
          <div>
            <span className="settings-label">Camera Backend</span>
            <code className="settings-url">{CAMERA_BASE}</code>
          </div>
        </div>
        <div className="settings-row">
          <div>
            <span className="settings-label">Location Server</span>
            <code className="settings-url">{LOCATION_BASE}</code>
          </div>
        </div>
      </section>

      {/* ── System Info ────────────────────────────────────────── */}
      <section className="settings-section card">
        <div className="section-heading"><span>ℹ</span> System Info</div>
        <div className="settings-row">
          <span className="settings-label">App Version</span>
          <code>v2.0.0 Mobile</code>
        </div>
        <div className="settings-row">
          <span className="settings-label">AI Engine</span>
          <code>YOLOv8 + Adaptive Risk Engine</code>
        </div>
        <div className="settings-row">
          <span className="settings-label">Architecture</span>
          <code>Vite React + Python Server</code>
        </div>
      </section>
    </main>
  );
}
