import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AuthProvider } from '@/contexts/AuthContext';
import LoginPage from '@/pages/LoginPage';
import SelectPage from '@/pages/SelectPage';
import { PrivateRoute } from '@/components/PrivateRoute';
import { PublicRoute } from '@/components/PublicRoute';
// @ts-ignore Import errors will be fixed by tsconfig.json

const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<PublicRoute><LoginPage /></PublicRoute>} />
      <Route path="/select" element={<PrivateRoute><SelectPage /></PrivateRoute>} />
    </Routes>
  );
};

const App: React.FC = () => {
  return (
    <Router>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </Router>
  );
};

export default App;
