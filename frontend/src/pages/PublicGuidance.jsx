/**
 * PublicGuidance.jsx
 * 
 * Public Visitor Guidance & Safe Wayfinding Page.
 * Provides clear, non-technical pedestrian routing and venue flow guidance.
 */

import { Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useCameraData } from '../hooks/useCameraData';
import { useLocationData } from '../hooks/useLocationData';
import { getPublicStatus } from './PublicHome';
import './PublicHome.css';

export default function PublicGuidance() {
  const { switchRolePrompt } = useAuth();
  const camera = useCameraData('cam1', 'user');
  const location = useLocationData('user');

  const status = getPublicStatus(camera.prevention, location);
  const topThreat = camera.prevention?.threats?.[0];
  const safeAlt = topThreat?.safe_alternative || 'Open Concourse & Exit Grounds';

  return (
    <main className="page public-page animate-fade-in">
      {/* ── Header ────────────────────────────────────────────── */}
      <header className="public-header">
        <div className="public-brand">
          <span className="public-logo">🧭</span>
          <div>
            <h1 className="public-title">Wayfinding &amp; Flow</h1>
            <p className="public-subtitle">Real-Time Safe Pedestrian Guidance</p>
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

      {/* ── Current Flow Status ───────────────────────────────── */}
      <section
        className="public-status-card"
        style={{ background: status.bg, borderColor: status.border }}
      >
        <div className="public-status-top">
          <span className="public-status-icon">{status.icon}</span>
          <div className="public-status-meta">
            <span className="public-status-badge" style={{ color: status.color }}>
              Current Flow Status
            </span>
            <h2 className="public-status-title">{status.title}</h2>
          </div>
        </div>
        <p className="public-status-message">{status.message}</p>
      </section>

      {/* ── Active Route Recommendation ───────────────────────── */}
      <section className="card" style={{ padding: '20px' }}>
        <div className="public-section-title" style={{ marginBottom: '12px' }}>
          <span>📍</span> Recommended Walking Path
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '12px 16px',
              background: 'rgba(16, 185, 129, 0.1)',
              border: '1px solid rgba(16, 185, 129, 0.25)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <span style={{ fontSize: '1.4rem' }}>🟢</span>
            <div>
              <strong style={{ color: '#10b981', display: 'block', fontSize: '0.9rem' }}>
                Primary Recommended Route: {safeAlt}
              </strong>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                This route has clear pedestrian passage and steady forward flow.
              </span>
            </div>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '12px 16px',
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <span style={{ fontSize: '1.4rem' }}>🚶</span>
            <div>
              <strong style={{ color: 'var(--text-primary)', display: 'block', fontSize: '0.9rem' }}>
                Alternative Exit Path: External Promenade
              </strong>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                Follow overhead green signs toward outer perimeter gates.
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* ── Wayfinding Points of Interest ─────────────────────── */}
      <section className="card" style={{ padding: '20px' }}>
        <div className="public-section-title" style={{ marginBottom: '14px' }}>
          <span>🏢</span> Venue Amenities &amp; Key Locations
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
          <div
            style={{
              padding: '12px',
              background: 'var(--bg-elevated)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid rgba(255, 255, 255, 0.06)',
            }}
          >
            <span style={{ fontSize: '1.2rem', display: 'block', marginBottom: '4px' }}>🚪</span>
            <strong style={{ fontSize: '0.85rem', display: 'block' }}>Main Exits</strong>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>North &amp; South Gates</span>
          </div>

          <div
            style={{
              padding: '12px',
              background: 'var(--bg-elevated)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid rgba(255, 255, 255, 0.06)',
            }}
          >
            <span style={{ fontSize: '1.2rem', display: 'block', marginBottom: '4px' }}>🏥</span>
            <strong style={{ fontSize: '0.85rem', display: 'block' }}>First Aid</strong>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Central Concourse</span>
          </div>

          <div
            style={{
              padding: '12px',
              background: 'var(--bg-elevated)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid rgba(255, 255, 255, 0.06)',
            }}
          >
            <span style={{ fontSize: '1.2rem', display: 'block', marginBottom: '4px' }}>🤝</span>
            <strong style={{ fontSize: '0.85rem', display: 'block' }}>Meeting Point</strong>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>East Plaza Pavilion</span>
          </div>

          <div
            style={{
              padding: '12px',
              background: 'var(--bg-elevated)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid rgba(255, 255, 255, 0.06)',
            }}
          >
            <span style={{ fontSize: '1.2rem', display: 'block', marginBottom: '4px' }}>🚻</span>
            <strong style={{ fontSize: '0.85rem', display: 'block' }}>Restrooms</strong>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Available at all sectors</span>
          </div>
        </div>
      </section>

      {/* ── Return Link ───────────────────────────────────────── */}
      <div style={{ textAlign: 'center', padding: '8px 0' }}>
        <Link to="/" style={{ color: 'var(--accent)', fontSize: '0.85rem', fontWeight: 700, textDecoration: 'none' }}>
          &larr; Back to Safe Flow Home
        </Link>
      </div>
    </main>
  );
}
