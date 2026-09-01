/**
 * ThreatCard — shows threat intelligence for managers or safe route wayfinding for public users.
 */
import RiskBadge from './RiskBadge';
import { trendIcon, trendClass, formatTimestamp } from '../utils';
import './ThreatCard.css';

export default function ThreatCard({ threat, source = 'camera', timestamp }) {
  if (!threat) return null;
  const {
    zone, density, risk_score, risk_level,
    risk_cause, possible_origin, safe_alternative, recommended_action, trend,
    // public role fields
    crowd_status, safe_guidance, safety_instruction, recommended_route, area_name, suggested_safer_area, navigation_hint,
    // location-mode fields
    cell_id, lat, lon,
  } = threat;

  const zoneLabel = zone || area_name || cell_id || '—';
  const isLocationSource = source === 'location';
  const isPublicUser = crowd_status !== undefined && risk_score === undefined;

  if (isPublicUser) {
    const statusColor = crowd_status === 'Crowded' ? 'var(--risk-high)' : (crowd_status === 'Moderate' ? 'var(--risk-medium)' : 'var(--risk-low)');
    const statusBg = crowd_status === 'Crowded' ? 'var(--risk-high-bg)' : (crowd_status === 'Moderate' ? 'var(--risk-medium-bg)' : 'var(--risk-low-bg)');

    return (
      <article className="threat-card animate-fade-in" style={{ borderLeft: `4px solid ${statusColor}` }}>
        <header className="threat-card__header">
          <div className="threat-card__zone">
            <span className="threat-card__zone-label">{isLocationSource ? '📍' : '🚶'}</span>
            <span className="threat-card__zone-name">{zoneLabel}</span>
          </div>
          <span
            className="cam-risk-tag"
            style={{ background: statusBg, color: statusColor, fontWeight: 700 }}
          >
            {crowd_status} Activity
          </span>
        </header>

        <div className="threat-card__metrics" style={{ marginTop: 8 }}>
          {(safe_alternative || suggested_safer_area) && (
            <div className="threat-card__metric" style={{ gridColumn: 'span 2' }}>
              <span className="threat-card__metric-label">Recommended Route</span>
              <span className="threat-card__metric-value safe">
                ➔ Head toward {safe_alternative || suggested_safer_area}
              </span>
            </div>
          )}
        </div>

        {(safe_guidance || recommended_action) && (
          <div className="threat-card__action" style={{ background: 'var(--bg-elevated)', marginTop: 8 }}>
            <span className="threat-card__action-icon">🧭</span>
            <p className="threat-card__action-text">{safe_guidance || recommended_action}</p>
          </div>
        )}

        {safety_instruction && (
          <div className="threat-card__cause" style={{ color: 'var(--text-secondary)' }}>
            <span className="threat-card__cause-icon">ℹ</span>
            <span>{safety_instruction}</span>
          </div>
        )}

        {timestamp && (
          <footer className="threat-card__footer">
            <time className="threat-card__time">{formatTimestamp(timestamp)}</time>
          </footer>
        )}
      </article>
    );
  }

  // Manager Intelligence Card
  const effectiveLevel = risk_level || 'LOW';

  return (
    <article className={`threat-card threat-card--${effectiveLevel.toLowerCase()} animate-fade-in`}>
      <header className="threat-card__header">
        <div className="threat-card__zone">
          <span className="threat-card__zone-label">{isLocationSource ? '📍' : '📷'}</span>
          <span className="threat-card__zone-name">{zoneLabel}</span>
        </div>
        <RiskBadge level={effectiveLevel} score={risk_score} pulse={effectiveLevel === 'HIGH' || effectiveLevel === 'CRITICAL'} />
      </header>

      <div className="threat-card__metrics">
        <div className="threat-card__metric">
          <span className="threat-card__metric-label">Density</span>
          <span className="threat-card__metric-value">{density ?? '—'}</span>
        </div>

        {trend && (
          <div className="threat-card__metric">
            <span className="threat-card__metric-label">Trend</span>
            <span className={`threat-card__metric-value ${trendClass(trend)}`}>
              {trendIcon(trend)} {trend}
            </span>
          </div>
        )}

        {possible_origin && possible_origin !== 'UNKNOWN' && (
          <div className="threat-card__metric">
            <span className="threat-card__metric-label">Origin</span>
            <span className="threat-card__metric-value">{possible_origin}</span>
          </div>
        )}

        {safe_alternative && safe_alternative !== 'NO ALTERNATIVE YET' && (
          <div className="threat-card__metric">
            <span className="threat-card__metric-label">Safe Alt.</span>
            <span className="threat-card__metric-value safe">{safe_alternative}</span>
          </div>
        )}
      </div>

      {risk_cause && (
        <div className="threat-card__cause">
          <span className="threat-card__cause-icon">⚠</span>
          <span>{risk_cause}</span>
        </div>
      )}

      {recommended_action && (
        <div className="threat-card__action">
          <span className="threat-card__action-icon">🛡</span>
          <p className="threat-card__action-text">{recommended_action}</p>
        </div>
      )}

      {timestamp && (
        <footer className="threat-card__footer">
          <time className="threat-card__time">{formatTimestamp(timestamp)}</time>
        </footer>
      )}
    </article>
  );
}
