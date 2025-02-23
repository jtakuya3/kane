// React is automatically imported by Vite
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { onAuthStateChanged, User } from 'firebase/auth';
import { auth } from './firebase';

import LoginPage from './pages/LoginPage';
import SelectPage from './pages/SelectPage';

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      setUser(user);
      setLoading(false);
    });
    return () => unsubscribe();
  }, []);

  if (loading) return <div>Loading...</div>;

  return (
    <Router>
      <Routes>
        <Route path="/" element={!user ? <LoginPage /> : <Navigate to="/select" />} />
        <Route path="/select" element={user ? <SelectPage /> : <Navigate to="/" />} />
      </Routes>
    </Router>
  );
}

export default App;
