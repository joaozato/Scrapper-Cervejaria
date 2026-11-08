import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import useStore from './store/useStore';
import Login from './pages/Login';
import Home from './pages/Home';
import CargasDashboard from './pages/CargasDashboard';
import RelatoriosCargas from './pages/RelatoriosCargas';
import EstatisticasDashboard from './pages/EstatisticasDashboard';
import AuditDashboard from './pages/AuditDashboard';
import AssistenteIA from './pages/AssistenteIA';
import Layout from './components/Layout';

function ProtectedRoute({ children }) {
  const user = useStore((s) => s.user);
  if (!user) return <Navigate to="/login" replace />;
  return <Layout>{children}</Layout>;
}

function AdminRoute({ children }) {
  const user = useStore((s) => s.user);
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== 'admin') return <Navigate to="/" replace />;
  return <Layout>{children}</Layout>;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Home />
            </ProtectedRoute>
          }
        />
        
        <Route
          path="/cargas"
          element={
            <ProtectedRoute>
              <CargasDashboard />
            </ProtectedRoute>
          }
        />

        <Route
          path="/relatorios"
          element={
            <ProtectedRoute>
              <RelatoriosCargas />
            </ProtectedRoute>
          }
        />

        <Route
          path="/estatisticas"
          element={
            <ProtectedRoute>
              <EstatisticasDashboard />
            </ProtectedRoute>
          }
        />

        <Route
          path="/auditoria"
          element={
            <ProtectedRoute>
              <AuditDashboard />
            </ProtectedRoute>
          }
        />
        
        <Route
          path="/assistente-ia"
          element={
            <ProtectedRoute>
              <AssistenteIA />
            </ProtectedRoute>
          }
        />

        <Route path="/faturamento" element={<Navigate to="/estatisticas" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
