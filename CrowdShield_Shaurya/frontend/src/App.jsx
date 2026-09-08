import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './hooks/useAuth';
import { useCameraData } from './hooks/useCameraData';
import NavBar from './components/NavBar';
import RoleSelectModal from './components/RoleSelectModal';

// Manager Operational Pages
import Dashboard from './pages/Dashboard';
import Camera    from './pages/Camera';
import Heatmap   from './pages/Heatmap';
import Alerts    from './pages/Alerts';
import Settings  from './pages/Settings';

// Public Visitor Safety & Guidance Pages
import PublicHome     from './pages/PublicHome';
import PublicGuidance from './pages/PublicGuidance';
import PublicHelp     from './pages/PublicHelp';

function AppContent() {
  const { role, isManager } = useAuth();
  const camera = useCameraData('cam1', role);
  const threatCount = camera.prevention?.threat_count ?? 0;

  return (
    <BrowserRouter>
      <div className="app-shell">
        <RoleSelectModal />
        <Routes>
          {isManager ? (
            <>
              {/* Full Manager Operational Control Center */}
              <Route path="/"         element={<Dashboard />} />
              <Route path="/camera"   element={<Camera />} />
              <Route path="/heatmap"  element={<Heatmap />} />
              <Route path="/alerts"   element={<Alerts />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="*"         element={<Navigate to="/" replace />} />
            </>
          ) : (
            <>
              {/* Calm, Simplified Public Visitor Guidance */}
              <Route path="/"         element={<PublicHome />} />
              <Route path="/guidance" element={<PublicGuidance />} />
              <Route path="/help"     element={<PublicHelp />} />

              {/* Strict Route Guard: Direct navigation to operational routes redirects to Home */}
              <Route path="/camera"   element={<Navigate to="/" replace />} />
              <Route path="/heatmap"  element={<Navigate to="/" replace />} />
              <Route path="/alerts"   element={<Navigate to="/" replace />} />
              <Route path="/settings" element={<Navigate to="/" replace />} />
              <Route path="*"         element={<Navigate to="/" replace />} />
            </>
          )}
        </Routes>
        <NavBar threatCount={threatCount} />
      </div>
    </BrowserRouter>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
