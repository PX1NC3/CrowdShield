import { Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useCameraData } from '../hooks/useCameraData';
import { useLocationData } from '../hooks/useLocationData';
import RiskBadge from '../components/RiskBadge';
import { riskColor, trendIcon, trendClass, formatTimestamp } from '../utils';
import './Dashboard.css';

function StatCard({ icon, label, value, sub, color }) {
  return (
    <div className="stat-card card" style={{ '--stat-color': color }}>
      <span className="stat-card__icon">{icon}</span>
      <div className="stat-card__body">
        <span className="stat-card__value">{value ?? '—'}</span>
        <span className="stat-card__label">{label}</span>
        {sub && <span className="stat-card__sub">{sub}</span>}
      </div>
    </div>
  );
}

function QuickLink({ to, icon, label, description, badge }) {
  return (
    <Link to={to} className="quick-link card">
      <div className="quick-link__icon">{icon}</div>
      <div className="quick-link__body">
        <span className="quick-link__label">{label}</span>
        <span className="quick-link__desc">{description}</span>
      </div>
      {badge && <span className="quick-link__badge">{badge}</span>}
      <span className="quick-link__arrow">›</span>
    </Link>
  );
}

export default function Dashboard() {
  const { role, isManager, switchRolePrompt, selectUserRole } = useAuth();
  const camera   = useCameraData('cam1', role);
  const location = useLocationData(role);

  const prevention = camera.prevention;
  const zones      = camera.zones?.zones ?? [];
  const topThreat  = prevention?.threats?.[0];

  const highestRiskLevel = prevention?.highest_risk_level ?? 'LOW';
  const totalPeople      = prevention?.total_people ?? 0;
  const threatCount      = prevention?.threat_count ?? 0;
  const highestZone      = prevention?.highest_risk_zone ?? '—';
  const defaultNotice = isManager
    ? 'No active threats. Continue monitoring.'
    : 'You are doing great! Clear paths and smooth movement across all walkways.';
  const topAction = topThreat?.recommended_action ?? defaultNotice;

  // Location summary
  const locationCells    = location.heatmap?.cells ?? [];
  const locationAlerts   = location.areas?.areas ?? [];
  const highRiskCells    = locationCells.filter(c => c.risk_level === 'HIGH' || c.risk_level === 'CRITICAL');

  const cameraOnline   = camera.backendOnline;
  const locationOnline = location.backendOnline;

  return (
    <main className="page dashboard">
      {/* ── Brand header ────────────────────────────────────────── */}
      <header className="dashboard__brand">
        <div className="dashboard__logo">
          <span className="dashboard__logo-icon">🛡</span>
          <div>
            <h1 className="dashboard__title">CrowdShield</h1>
            <p className="dashboard__subtitle">
              Crowd Intelligence Platform ·{' '}
              <button
                className="role-badge-link"
                onClick={switchRolePrompt}
                title="Click to switch role / authenticate"
              >
                {isManager ? '👔 Manager Mode 🔒' : '🚶 Public User View'}
              </button>
            </p>
          </div>
        </div>
        <div className="dashboard__status-dots">
          <span
            className={`status-dot ${cameraOnline ? 'status-dot--online' : 'status-dot--offline'}`}
            title={cameraOnline ? 'Camera backend online' : 'Camera backend offline'}
          />
          <span
            className={`status-dot ${locationOnline ? 'status-dot--online' : 'status-dot--offline'}`}
            title={locationOnline ? 'Location server online' : 'Location server offline'}
          />
        </div>
      </header>

      {/* ── Overall status hero ─────────────────────────────────── */}
      <section className="dashboard__risk-hero card" aria-label="Overall crowd status">
        <div className="dashboard__risk-hero-left">
          <span className="dashboard__risk-label">{isManager ? 'Overall Risk' : 'Overall Crowd Density'}</span>
          {isManager ? (
            <RiskBadge
              level={highestRiskLevel}
              score={topThreat?.risk_score}
              pulse
              size="lg"
            />
          ) : (
            <span
              className="cam-risk-tag"
              style={{
                fontSize: '1.05rem',
                padding: '6px 14px',
                fontWeight: 800,
                background: highestRiskLevel === 'Crowded' ? 'var(--risk-high-bg)' : (highestRiskLevel === 'Moderate' ? 'var(--risk-medium-bg)' : 'var(--risk-low-bg)'),
                color: highestRiskLevel === 'Crowded' ? 'var(--risk-high)' : (highestRiskLevel === 'Moderate' ? 'var(--risk-medium)' : 'var(--risk-low)'),
              }}
            >
              {highestRiskLevel === 'Crowded' ? 'Busy Corridor' : (highestRiskLevel === 'Moderate' ? 'Moderate Movement' : 'Clear & Smooth')}
            </span>
          )}
          {highestZone !== '—' && isManager && (
            <span className="dashboard__risk-zone">Most critical: <strong>{highestZone}</strong></span>
          )}
        </div>
        {isManager ? (
          <div
            className="dashboard__risk-score-ring"
            style={{ '--ring-color': riskColor(highestRiskLevel) }}
          >
            <span className="dashboard__risk-score-num">
              {topThreat?.risk_score ? Math.round(topThreat.risk_score) : 0}
            </span>
            <span className="dashboard__risk-score-label">score</span>
          </div>
        ) : (
          <div
            className="dashboard__risk-score-ring"
            style={{ '--ring-color': highestRiskLevel === 'Crowded' ? 'var(--risk-high)' : (highestRiskLevel === 'Moderate' ? 'var(--risk-medium)' : 'var(--risk-low)') }}
          >
            <span className="dashboard__risk-score-num" style={{ fontSize: '1.4rem' }}>
              {highestRiskLevel === 'Crowded' ? 'Busy' : (highestRiskLevel === 'Moderate' ? 'Normal' : 'Clear')}
            </span>
            <span className="dashboard__risk-score-label">status</span>
          </div>
        )}
      </section>

      {/* ── Stats grid ───────────────────────────────────────────── */}
      <div className="stats-grid">
        {isManager ? (
          <>
            <StatCard
              icon="👥"
              label="Total People"
              value={totalPeople}
              color="var(--accent)"
            />
            <StatCard
              icon="⚠"
              label="Active Threats"
              value={threatCount}
              color={threatCount > 0 ? 'var(--risk-high)' : 'var(--risk-low)'}
            />
            <StatCard
              icon="📍"
              label="Hot Cells"
              value={highRiskCells.length || (locationOnline ? 0 : '—')}
              color="var(--risk-medium)"
            />
            <StatCard
              icon="📷"
              label="Mode"
              value={cameraOnline ? 'LIVE' : 'OFFLINE'}
              color={cameraOnline ? 'var(--risk-low)' : 'var(--text-muted)'}
            />
          </>
        ) : (
          <>
            <StatCard
              icon="🗺"
              label="Areas Monitored"
              value={locationCells.length || 6}
              color="var(--accent)"
            />
            <StatCard
              icon="🧭"
              label="Navigation"
              value="Active"
              color="var(--risk-low)"
            />
            <StatCard
              icon="🚶"
              label="Flow Guidance"
              value={highestRiskLevel === 'Crowded' ? 'Reroute' : 'Clear'}
              color={highestRiskLevel === 'Crowded' ? 'var(--risk-medium)' : 'var(--risk-low)'}
            />
            <StatCard
              icon="🛡"
              label="Safety Status"
              value="Secure"
              color="var(--risk-low)"
            />
          </>
        )}
      </div>

      {/* ── Latest action ─────────────────────────────────────────── */}
      <section className="dashboard__action card" aria-label="Latest prevention recommendation">
        <div className="section-heading">
          <span>{isManager ? '🛡' : '🧭'}</span> {isManager ? 'Latest Recommendation' : 'Safe Walking Notice'}
        </div>
        <p className="dashboard__action-text">{topAction}</p>
        {topThreat && isManager && (
          <div className="dashboard__action-meta">
            <span className="chip">{topThreat.zone || topThreat.cell_id}</span>
            {topThreat.trend && (
              <span className={`chip ${trendClass(topThreat.trend)}`}>
                {trendIcon(topThreat.trend)} {topThreat.trend}
              </span>
            )}
            {topThreat.possible_origin && topThreat.possible_origin !== 'UNKNOWN' && (
              <span className="chip">From {topThreat.possible_origin}</span>
            )}
            {topThreat.safe_alternative && (
              <span className="chip chip--safe">➔ {topThreat.safe_alternative}</span>
            )}
          </div>
        )}
        {topThreat && !isManager && (
          <div className="dashboard__action-meta">
            <span className="chip">{topThreat.zone || 'Monitored Concourse'}</span>
            {topThreat.safe_alternative && (
              <span className="chip chip--safe">➔ Clear path at {topThreat.safe_alternative}</span>
            )}
          </div>
        )}
        {prevention?.timestamp && (
          <time className="dashboard__action-time">{formatTimestamp(prevention.timestamp)}</time>
        )}
      </section>

      {/* ── Quick navigation (Manager Only) ─────────────────────── */}
      {isManager && (
        <>
          <div className="section-heading">
            <span>🧭</span> Control Center Navigation
          </div>
          <div className="quick-links">
            <QuickLink
              to="/camera"
              icon="📷"
              label="Camera Intelligence"
              description="Live stream with 3x3 zone optical tracking"
              badge={threatCount > 0 ? threatCount : null}
            />
            <QuickLink
              to="/heatmap"
              icon="🗺"
              label="Heatmap Mode"
              description="Location GPS cells and crowd clusters"
              badge={locationAlerts.length > 0 ? locationAlerts.length : null}
            />
            <QuickLink
              to="/alerts"
              icon="🔔"
              label="Threat Intelligence & Alerts"
              description="Live threat warnings & historical log"
              badge={threatCount > 0 ? threatCount : null}
            />
          </div>
        </>
      )}

      {/* ── Public User Safe Travel Notice ──────────────────────── */}
      {!isManager && (
        <section className="card" style={{ borderLeft: '4px solid var(--accent)', background: 'var(--bg-elevated)', padding: 'var(--space-4)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: '1.4rem' }}>🚶</span>
            <div>
              <strong style={{ color: 'var(--text-primary)', fontSize: '0.9rem' }}>Safe Movement Portal Active</strong>
              <p style={{ margin: '2px 0 0', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                This public dashboard provides real-time crowd congestion updates and clear routes. No tracking or camera data is broadcasted to mobile users.
              </p>
            </div>
          </div>
        </section>
      )}

      {/* ── Backend offline warning ──────────────────────────────── */}
      {!cameraOnline && !camera.loading && isManager && (
        <div className="error-banner" role="alert">
          <span>⚡</span>
          Camera backend offline — start detect.py to enable live monitoring.
        </div>
      )}
    </main>
  );
}
