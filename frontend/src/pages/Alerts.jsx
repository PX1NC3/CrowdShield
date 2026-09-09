import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useCameraData } from '../hooks/useCameraData';
import { useLocationData } from '../hooks/useLocationData';
import ThreatCard from '../components/ThreatCard';
import './Alerts.css';

const ALERT_HISTORY_KEY = 'crowdshield_alert_history';

export default function Alerts() {
  const { role, isManager } = useAuth();
  const camera = useCameraData('cam1', role);
  const location = useLocationData(role);
  const [filterLevel, setFilterLevel] = useState('ALL');

  // Persistent alert history (never disappears in manager mode)
  const [history, setHistory] = useState(() => {
    try {
      const saved = localStorage.getItem(ALERT_HISTORY_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const cameraThreats = (camera.prevention?.threats ?? []).map(t => ({
    ...t,
    source: 'camera',
    timestamp: camera.prevention?.timestamp || new Date().toISOString(),
  }));

  const locationThreats = (location.areas?.areas ?? []).map(a => ({
    ...a,
    source: 'location',
    timestamp: new Date().toISOString(),
  }));

  const activeThreats = [...cameraThreats, ...locationThreats];

  // Capture incoming active threats into persistent historical log
  useEffect(() => {
    if (!isManager || activeThreats.length === 0) return;

    setHistory(prevHistory => {
      let updated = [...prevHistory];
      let hasChange = false;

      for (const t of activeThreats) {
        const id = `${t.source}_${t.zone || t.cell_id || t.area_name}_${t.risk_level || t.crowd_status}`;
        // Only record if not recorded in the last 20 seconds for the same zone/severity
        const existsRecent = updated.some(h => {
          if (h.history_id !== id) return false;
          const diffMs = Math.abs(new Date(t.timestamp).getTime() - new Date(h.timestamp).getTime());
          return diffMs < 20000;
        });

        if (!existsRecent) {
          updated.unshift({
            ...t,
            history_id: id,
            logged_at: new Date().toISOString(),
          });
          hasChange = true;
        }
      }

      if (hasChange) {
        // Keep up to 50 historical entries
        const trimmed = updated.slice(0, 50);
        try { localStorage.setItem(ALERT_HISTORY_KEY, JSON.stringify(trimmed)); } catch {}
        return trimmed;
      }
      return prevHistory;
    });
  }, [activeThreats.length, isManager, camera.prevention?.timestamp]);

  const clearHistory = () => {
    setHistory([]);
    try { localStorage.removeItem(ALERT_HISTORY_KEY); } catch {}
  };

  const filterFn = t => {
    if (filterLevel === 'HIGH_CRITICAL') return t.risk_level === 'HIGH' || t.risk_level === 'CRITICAL';
    if (filterLevel === 'MEDIUM') return t.risk_level === 'MEDIUM';
    if (filterLevel === 'LOW') return t.risk_level === 'LOW';
    return true;
  };

  const filteredActive = activeThreats.filter(filterFn);
  const filteredHistory = history.filter(filterFn);

  return (
    <main className="page alerts-page">
      <div className="camera-header-row">
        <h1 className="page-title">
          <span>🔔</span> Threat Intelligence & Alerts
        </h1>
        {isManager && history.length > 0 && (
          <button
            className="btn btn-ghost"
            onClick={clearHistory}
            style={{ fontSize: '0.75rem', padding: '4px 10px' }}
            title="Clear saved historical alert records"
          >
            🗑 Clear History
          </button>
        )}
      </div>

      {/* ── Filter bar ───────────────────────────────────────── */}
      <div className="alerts-filter-bar" role="group" aria-label="Filter alerts by severity">
        {[
          { key: 'ALL', label: `All (${activeThreats.length})` },
          { key: 'HIGH_CRITICAL', label: 'High/Critical' },
          { key: 'MEDIUM', label: 'Medium' },
          { key: 'LOW', label: 'Low' },
        ].map(f => (
          <button
            key={f.key}
            className={`alerts-filter-btn ${filterLevel === f.key ? 'alerts-filter-btn--active' : ''}`}
            onClick={() => setFilterLevel(f.key)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* ── Section 1: Active Alerts (Real-Time) ──────────────── */}
      <section aria-label="Real-time active alerts">
        <div className="section-heading">
          <span style={{ color: activeThreats.length > 0 ? 'var(--risk-high)' : 'var(--risk-low)' }}>
            {activeThreats.length > 0 ? '⚡' : '🛡'}
          </span>
          Active Alerts ({filteredActive.length})
        </div>

        {filteredActive.length === 0 ? (
          <div className="empty-state">
            <span className="empty-state-icon">✅</span>
            <span className="empty-state-title">No Active Threat Alerts</span>
            <p>All monitored camera zones and location areas are within safe thresholds.</p>
          </div>
        ) : (
          <div className="alerts-list">
            {filteredActive.map((threat, idx) => (
              <ThreatCard
                key={`active_${(threat.zone || threat.cell_id) + idx}`}
                threat={threat}
                source={threat.source}
                timestamp={threat.timestamp}
              />
            ))}
          </div>
        )}
      </section>

      {/* ── Section 2: Alert History (Persistent Manager Log) ─── */}
      {isManager && (
        <section className="alerts-history-section" aria-label="Historical alerts log" style={{ marginTop: 'var(--space-4)' }}>
          <div className="section-heading" style={{ justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span>📜</span> Alert History & Incident Log ({filteredHistory.length})
            </div>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 500 }}>
              Retained across sessions
            </span>
          </div>

          {filteredHistory.length === 0 ? (
            <div className="empty-state" style={{ padding: 'var(--space-4)' }}>
              <span className="empty-state-icon">📋</span>
              <span className="empty-state-title">No Prior Alerts Recorded</span>
              <p>Triggered alerts and risk spikes will be logged here permanently for post-event audit.</p>
            </div>
          ) : (
            <div className="alerts-list alerts-list--history">
              {filteredHistory.map((item, idx) => (
                <div key={`hist_${item.history_id || idx}_${item.logged_at || idx}`} className="history-card-wrapper">
                  <div className="history-timestamp-pill">
                    ⏱ Logged: {new Date(item.logged_at || item.timestamp).toLocaleTimeString()} · {new Date(item.logged_at || item.timestamp).toLocaleDateString()}
                  </div>
                  <ThreatCard
                    threat={item}
                    source={item.source}
                    timestamp={item.timestamp}
                  />
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </main>
  );
}
