/**
 * PublicHelp.jsx
 * 
 * Public Visitor Help & Emergency Assistance Page.
 * Provides visitor safety resources, emergency contacts, and staff login.
 */

import { Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import './PublicHome.css';

export default function PublicHelp() {
  const { switchRolePrompt } = useAuth();

  return (
    <main className="page public-page animate-fade-in">
      {/* ── Header ────────────────────────────────────────────── */}
      <header className="public-header">
        <div className="public-brand">
          <span className="public-logo">ℹ️</span>
          <div>
            <h1 className="public-title">Visitor Help &amp; Safety</h1>
            <p className="public-subtitle">Assistance, Contacts &amp; Protocols</p>
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

      {/* ── Immediate Assistance Card ─────────────────────────── */}
      <section className="card" style={{ padding: '20px', borderLeft: '4px solid #ef4444' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px' }}>
          <span style={{ fontSize: '1.8rem', lineHeight: 1 }}>🚨</span>
          <div>
            <strong style={{ fontSize: '1rem', color: 'var(--text-primary)', display: 'block', marginBottom: '4px' }}>
              Immediate Emergency Assistance
            </strong>
            <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
              If you or someone near you requires medical attention or urgent help, contact the nearest safety steward immediately or alert emergency personnel.
            </p>
          </div>
        </div>
      </section>

      {/* ── Venue Contacts Directory ──────────────────────────── */}
      <section className="card" style={{ padding: '20px' }}>
        <div className="public-section-title" style={{ marginBottom: '14px' }}>
          <span>📞</span> Venue Assistance Contacts
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 14px',
              background: 'var(--bg-elevated)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <div>
              <strong style={{ display: 'block', fontSize: '0.88rem' }}>Venue Safety Desk</strong>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>General safety &amp; questions</span>
            </div>
            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--accent)' }}>
              Ext 401 / Intercom
            </span>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 14px',
              background: 'var(--bg-elevated)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <div>
              <strong style={{ display: 'block', fontSize: '0.88rem' }}>First Aid &amp; Medical</strong>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>Central Concourse Station</span>
            </div>
            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#10b981' }}>
              Open 24/7
            </span>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 14px',
              background: 'var(--bg-elevated)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <div>
              <strong style={{ display: 'block', fontSize: '0.88rem' }}>Lost &amp; Found / Meeting Hub</strong>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>East Plaza Pavilion</span>
            </div>
            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-primary)' }}>
              Station E-1
            </span>
          </div>
        </div>
      </section>

      {/* ── Privacy & Safety Guarantee ────────────────────────── */}
      <section className="card" style={{ padding: '20px' }}>
        <div className="public-section-title" style={{ marginBottom: '10px' }}>
          <span>🔒</span> Privacy &amp; Public Safety
        </div>
        <p style={{ margin: '0 0 8px', fontSize: '0.84rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
          CrowdShield protects public visitors with strict privacy standards:
        </p>
        <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
          <li>No personal identification or facial recognition is collected.</li>
          <li>No individual device tracking or private location history is logged.</li>
          <li>Surveillance feeds and internal control tools are restricted strictly to authorized safety managers.</li>
        </ul>
      </section>

      {/* ── Venue Staff / Manager Access ──────────────────────── */}
      <section
        className="card"
        style={{
          padding: '20px',
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border-default)',
          textAlign: 'center',
        }}
      >
        <strong style={{ display: 'block', fontSize: '0.95rem', color: 'var(--text-primary)', marginBottom: '4px' }}>
          Are you an Event Operator or Venue Manager?
        </strong>
        <p style={{ margin: '0 0 14px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
          Log in with authorized control credentials to access camera streams, heatmaps, and operational intelligence.
        </p>
        <button
          type="button"
          className="btn btn-primary"
          onClick={switchRolePrompt}
          style={{ padding: '8px 22px', fontSize: '0.85rem' }}
        >
          👔 Switch to Control Manager Mode
        </button>
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
