/**
 * NavBar — bottom navigation bar.
 * Strict Role-based Isolation:
 * - Public User: Only sees Home, Guidance, Help (NO Camera, NO Heatmap, NO Alerts, NO Settings).
 * - Manager: Has access to full control center (Dashboard, Camera, Heatmap, Alerts, Settings).
 */
import { NavLink } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import './NavBar.css';

const MANAGER_NAV_ITEMS = [
  { to: '/',         icon: '⬡',  label: 'Dashboard' },
  { to: '/camera',   icon: '📹', label: 'Camera' },
  { to: '/heatmap',  icon: '🗺️', label: 'Heatmap' },
  { to: '/alerts',   icon: '🔔', label: 'Alerts' },
  { to: '/settings', icon: '⚙️', label: 'Settings' },
];

const PUBLIC_NAV_ITEMS = [
  { to: '/',         icon: '🏠', label: 'Home' },
  { to: '/guidance', icon: '📍', label: 'Guidance' },
  { to: '/help',     icon: 'ℹ️', label: 'Help' },
];

export default function NavBar({ threatCount = 0 }) {
  const { isManager } = useAuth();
  const visibleNavItems = isManager ? MANAGER_NAV_ITEMS : PUBLIC_NAV_ITEMS;

  return (
    <nav className="navbar" role="navigation" aria-label="Main navigation">
      <div className="navbar__inner">
        {visibleNavItems.map(({ to, icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `navbar__item ${isActive ? 'navbar__item--active' : ''}`
            }
            aria-label={label}
          >
            <span className="navbar__icon">
              {icon}
              {label === 'Alerts' && threatCount > 0 && isManager && (
                <span className="navbar__badge">{threatCount > 9 ? '9+' : threatCount}</span>
              )}
            </span>
            <span className="navbar__label">{label}</span>
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
