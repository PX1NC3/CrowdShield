import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './hooks/useAuth';
import { useCameraData } from './hooks/useCameraData';
import NavBar from './components/NavBar';
import RoleSelectModal from './components/RoleSelectModal';

import Dashboard from './pages/Dashboard';
import Camera    from './pages/Camera';
import Heatmap   from './pages/Heatmap';
import Alerts    from './pages/Alerts';
import Settings  from './pages/Settings';

function AppContent() {
  const { role, isManager } = useAuth();
  const camera = useCameraData('cam1', role);
  const threatCount = camera.prevention?.threat_count ?? 0;

  return (
    <BrowserRouter>
      <div className="app-shell">
        <RoleSelectModal />
        <Routes>
          <Route path="/"         element={<Dashboard />} />
          <Route path="/camera"   element={isManager ? <Camera /> : <Navigate to="/" replace />} />
          <Route path="/heatmap"  element={isManager ? <Heatmap /> : <Navigate to="/" replace />} />
          <Route path="/alerts"   element={isManager ? <Alerts /> : <Navigate to="/" replace />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*"         element={<Navigate to="/" replace />} />
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
