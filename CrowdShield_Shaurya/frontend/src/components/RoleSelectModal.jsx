/**
 * RoleSelectModal — Startup & On-demand Role Selection Dialog
 * Asks user whether they are Public User or Manager.
 * Manager mode requires password with light watermarked placeholder for assessor convenience.
 */
import { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import './RoleSelectModal.css';

export default function RoleSelectModal() {
  const { showRoleModal, selectUserRole, selectManagerRole, defaultManagerPass, role } = useAuth();
  const [selectedTab, setSelectedTab] = useState('user'); // 'user' | 'manager'
  const [password, setPassword] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [showHint, setShowHint] = useState(true);

  if (!showRoleModal) return null;

  const handleManagerSubmit = (e) => {
    e?.preventDefault();
    setErrorMsg('');
    const res = selectManagerRole(password);
    if (!res.success) {
      setErrorMsg(res.error);
    }
  };

  const handleQuickFill = () => {
    setPassword(defaultManagerPass);
    setErrorMsg('');
  };

  return (
    <div className="role-modal-backdrop animate-fade-in" role="dialog" aria-modal="true" aria-labelledby="role-modal-title">
      <div className="role-modal-card card animate-scale-up">
        {/* Header */}
        <div className="role-modal-header">
          <div className="role-modal-logo">🛡</div>
          <h2 id="role-modal-title" className="role-modal-title">CrowdShield Access</h2>
          <p className="role-modal-subtitle">
            Select your access role to proceed with the platform demonstration.
          </p>
        </div>

        {/* Tab selection */}
        <div className="role-tab-bar" role="tablist">
          <button
            role="tab"
            aria-selected={selectedTab === 'user'}
            className={`role-tab-btn ${selectedTab === 'user' ? 'role-tab-btn--active' : ''}`}
            onClick={() => { setSelectedTab('user'); setErrorMsg(''); }}
          >
            <span className="role-tab-icon">🚶</span>
            <span className="role-tab-title">Public User</span>
          </button>
          <button
            role="tab"
            aria-selected={selectedTab === 'manager'}
            className={`role-tab-btn ${selectedTab === 'manager' ? 'role-tab-btn--active' : ''}`}
            onClick={() => { setSelectedTab('manager'); setErrorMsg(''); }}
          >
            <span className="role-tab-icon">👔</span>
            <span className="role-tab-title">Control Manager</span>
          </button>
        </div>

        {/* Tab Content: Public User */}
        {selectedTab === 'user' && (
          <div className="role-tab-content animate-slide-in">
            <div className="role-info-box">
              <div className="role-info-item">
                <span className="role-info-check">✓</span>
                <span>Live safe crowd maps & area congestion updates</span>
              </div>
              <div className="role-info-item">
                <span className="role-info-check">✓</span>
                <span>Recommended alternate pedestrian paths & clear routes</span>
              </div>
              <div className="role-info-item">
                <span className="role-info-check">✓</span>
                <span>No login or personal tracking required</span>
              </div>
            </div>

            <button
              className="btn btn-primary role-submit-btn"
              onClick={selectUserRole}
              autoFocus
            >
              Continue as Public User →
            </button>
          </div>
        )}

        {/* Tab Content: Manager with Password Watermark Placeholder */}
        {selectedTab === 'manager' && (
          <form className="role-tab-content animate-slide-in" onSubmit={handleManagerSubmit}>
            <div className="role-info-box role-info-box--manager">
              <div className="role-info-item">
                <span className="role-info-check">⚡</span>
                <span>Full multi-camera zone metrics & YOLO optical tracking</span>
              </div>
              <div className="role-info-item">
                <span className="role-info-check">⚡</span>
                <span>Adaptive anomaly engine, origin vectors & diversion actions</span>
              </div>
              <div className="role-info-item">
                <span className="role-info-check">⚡</span>
                <span>Live / Demo scenario simulation controls</span>
              </div>
            </div>

            <div className="password-input-group">
              <label htmlFor="manager-password-input" className="password-label">
                Manager Authorization Password:
              </label>
              
              <div className="password-field-wrapper">
                <input
                  id="manager-password-input"
                  type="text"
                  className={`password-input ${errorMsg ? 'password-input--error' : ''}`}
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); setErrorMsg(''); }}
                  placeholder={`admin123`}
                  autoComplete="off"
                  autoFocus
                />
                {!password && (
                  <button
                    type="button"
                    className="watermark-autofill-btn"
                    onClick={handleQuickFill}
                    title="Click to autofill demonstration password"
                  >
                    Click to use demo key ({defaultManagerPass})
                  </button>
                )}
              </div>

              <div className="password-watermark-note">
                💡 <span className="watermark-highlight">admin123</span> is shown in placeholder above for easy demonstration testing.
              </div>

              {errorMsg && (
                <div className="role-error-banner" role="alert">
                  ⚠ {errorMsg}
                </div>
              )}
            </div>

            <div className="role-action-row">
              <button
                type="submit"
                className="btn btn-primary role-submit-btn"
              >
                Unlock Manager Console 🔓
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
