import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import LoginPage from './pages/LoginPage';
import SelectPage from './pages/SelectPage';
import { PrivateRoute } from './components/PrivateRoute';
import { PublicRoute } from './components/PublicRoute';

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<PublicRoute><LoginPage /></PublicRoute>} />
      <Route path="/select" element={<PrivateRoute><SelectPage /></PrivateRoute>} />
    </Routes>
  );
}

export default function App() {
  return (
    <Router>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </Router>
  );
}
