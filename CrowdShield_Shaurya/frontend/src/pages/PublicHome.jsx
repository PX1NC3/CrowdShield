/**
 * PublicHome.jsx
 * 
 * Public Visitor Safety & Guidance Portal.
 * Designed for calm, clear, and reassuring pedestrian guidance.
 * 
 * Strict Privacy:
 * - NO camera feeds or surveillance imagery
 * - NO bounding boxes, tracking IDs, or coordinates
 * - NO technical heatmap or 2D/3D spatial models
 * - NO raw density counts or internal risk scores
 */

import { Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useCameraData } from '../hooks/useCameraData';
import { useLocationData } from '../hooks/useLocationData';
import './PublicHome.css';

export function getPublicStatus(prevention, location) {
  const scenario = (prevention?.demo_scenario || '').toLowerCase();
  if (scenario === 'dispersal') {
    return {
      type: 'dispersal',
      icon: '🟣',
      badge: 'Flow Update',
      title: 'Crowd Is Dispersing',
      subtitle: 'Event flow is moving toward designated exits',
      message: 'Please continue calmly toward the indicated exit.',
      color: '#a78bfa',
      bg: 'rgba(124, 58, 237, 0.12)',
      border: 'rgba(124, 58, 237, 0.3)',
    };
  }

  const rawLevel = (prevention?.highest_risk_level || 'LOW').toUpperCase();
  if (rawLevel === 'CRITICAL') {
    return {
      type: 'critical',
      icon: '🔴',
      badge: 'Guidance Notice',
      title: 'Please Move Calmly',
      subtitle: 'Heavy foot-traffic reported in primary walkways',
      message: 'Follow staff instructions and move toward the nearest indicated safe route.',
      color: '#ef4444',
      bg: 'rgba(239, 68, 68, 0.12)',
      border: 'rgba(239, 68, 68, 0.3)',
    };
  }
  if (rawLevel === 'HIGH' || rawLevel === 'CROWDED') {
    return {
      type: 'high',
      icon: '🟠',
      badge: 'Traffic Alert',
      title: 'Busier Area Ahead',
      subtitle: 'Higher foot-traffic currently passing through',
      message: 'Please keep moving and follow the alternate route shown by event staff.',
      color: '#f97316',
      bg: 'rgba(249, 115, 22, 0.12)',
      border: 'rgba(249, 115, 22, 0.3)',
    };
  }
  if (rawLevel === 'MEDIUM' || rawLevel === 'MODERATE') {
    return {
      type: 'moderate',
      icon: '🟡',
      badge: 'Notice',
      title: 'A Little Busy Here',
      subtitle: 'Moderate foot-traffic along main routes',
      message: 'Please keep moving at a steady pace and avoid blocking walkways.',
      color: '#eab308',
      bg: 'rgba(234, 179, 8, 0.12)',
      border: 'rgba(234, 179, 8, 0.3)',
    };
  }
  return {
    type: 'low',
    icon: '🟢',
    badge: 'Safe & Clear',
    title: 'Area Looks Calm',
    subtitle: 'You are in a safe-flow area',
    message: 'Enjoy the event and keep moving comfortably along the marked concourses.',
    color: '#22c55e',
    bg: 'rgba(34, 197, 94, 0.12)',
    border: 'rgba(34, 197, 94, 0.3)',
  };
}

export default function PublicHome() {
  const { switchRolePrompt } = useAuth();
  const camera = useCameraData('cam1', 'user');
  const location = useLocationData('user');

  const status = getPublicStatus(camera.prevention, location);
  const topThreat = camera.prevention?.threats?.[0];
  const safeAlt = topThreat?.safe_alternative;

  return (
    <main className="page public-page animate-fade-in">
      {/* ── Header ────────────────────────────────────────────── */}
      <header className="public-header">
        <div className="public-brand">
          <span className="public-logo">🛡️</span>
          <div>
            <h1 className="public-title">CrowdShield</h1>
            <p className="public-subtitle">Visitor Safety &amp; Wayfinding Portal</p>
          </div>
        </div>
        <button
          type="button"
          className="public-staff-btn"
          onClick={switchRolePrompt}
          title="Authenticate as Venue Operator / Manager"
        >
          👔 Staff Login
        </button>
      </header>

      {/* ── Status Hero Card ──────────────────────────────────── */}
      <section
        className="public-status-card animate-scale-up"
        style={{
          background: status.bg,
          borderColor: status.border,
        }}
        aria-live="polite"
      >
        <div className="public-status-top">
          <span className="public-status-icon">{status.icon}</span>
          <div className="public-status-meta">
            <span className="public-status-badge" style={{ color: status.color }}>
              <span className="pulse-dot" style={{ background: status.color, width: 6, height: 6 }} />
              {status.badge}
            </span>
            <h2 className="public-status-title">{status.title}</h2>
          </div>
        </div>
        <p className="public-status-message">{status.message}</p>
        <p className="public-status-sub">{status.subtitle}</p>
      </section>

      {/* ── Alternate Route / Direction Guidance ───────────────── */}
      {safeAlt && (
        <section className="public-route-banner animate-slide-in">
          <span className="public-route-icon">🧭</span>
          <div className="public-route-body">
            <strong>Recommended Walking Route Available</strong>
            <p>
              Pedestrian passage via <strong>{safeAlt}</strong> is currently clearer and recommended for smoother movement.
            </p>
          </div>
        </section>
      )}

      {/* ── Calm Actionable Walking Instructions ──────────────── */}
      <section className="public-tips-section" aria-label="Walking Guidelines">
        <div className="public-section-title">
          <span>🚶</span> Simple Guidelines for Safe Movement
        </div>
        <div className="public-tips-list">
          <div className="public-tip-card">
            <span className="public-tip-icon">🚶</span>
            <div className="public-tip-body">
              <strong>Keep moving at a steady pace</strong>
              <p>Avoid sudden stops in busy thoroughfares and entrance corridors.</p>
            </div>
          </div>
          <div className="public-tip-card">
            <span className="public-tip-icon">➡️</span>
            <div className="public-tip-body">
              <strong>Follow marked exit &amp; signage</strong>
              <p>Look for illuminated directional signs and overhead exit markers.</p>
            </div>
          </div>
          <div className="public-tip-card">
            <span className="public-tip-icon">🧍</span>
            <div className="public-tip-body">
              <strong>Avoid stopping in narrow passages</strong>
              <p>Step to open areas or designated meeting spots when waiting for friends.</p>
            </div>
          </div>
          <div className="public-tip-card">
            <span className="public-tip-icon">🤝</span>
            <div className="public-tip-body">
              <strong>Stay with your group</strong>
              <p>Agree on a designated meeting location in case members get separated.</p>
            </div>
          </div>
          <div className="public-tip-card">
            <span className="public-tip-icon">📢</span>
            <div className="public-tip-body">
              <strong>Follow staff instructions</strong>
              <p>Venue safety marshals and event stewards are positioned to guide you.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Help & Information Banner ─────────────────────────── */}
      <section className="public-help-card">
        <div className="public-help-left">
          <span className="public-help-icon">ℹ️</span>
          <div className="public-help-body">
            <strong>Need assistance or medical aid?</strong>
            <span>Information desks and first aid stations are open throughout the venue.</span>
          </div>
        </div>
        <Link to="/help" className="public-help-link">
          View Help &rsaquo;
        </Link>
      </section>
    </main>
  );
}
