/**
 * NavBar — bottom mobile navigation bar.
 * Public User role only sees Dashboard and Settings.
 * Manager role has access to all tabs (Dashboard, Camera, Heatmap, Alerts, Settings).
 */
import { NavLink } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import './NavBar.css';

const ALL_NAV_ITEMS = [
  { to: '/',         icon: '⬡',  label: 'Dashboard', roles: ['user', 'manager'] },
  { to: '/camera',   icon: '📷', label: 'Camera',    roles: ['manager'] },
  { to: '/heatmap',  icon: '🗺',  label: 'Heatmap',   roles: ['manager'] },
  { to: '/alerts',   icon: '🔔', label: 'Alerts',    roles: ['manager'] },
  { to: '/settings', icon: '⚙',  label: 'Settings',  roles: ['user', 'manager'] },
];

export default function NavBar({ threatCount = 0 }) {
  const { role } = useAuth();
  const currentRole = role || 'user';

  const visibleNavItems = ALL_NAV_ITEMS.filter(item => item.roles.includes(currentRole));

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
              {label === 'Alerts' && threatCount > 0 && (
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
