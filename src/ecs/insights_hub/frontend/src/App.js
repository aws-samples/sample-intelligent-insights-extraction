import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Navigation from './components/Navigation';
import Login from './components/Login';
import SignUp from './components/SignUp';
import ForgotPassword from './components/ForgotPassword';
import ProtectedRoute from './components/ProtectedRoute';
import DesignList from './components/DesignList';
import DesignDetail from './components/DesignDetail';
import Favorites from './components/Favorites';
import ChatPage from './components/ChatPage';
import Dashboard from './components/Dashboard';
import AuthDebug from './components/AuthDebug';
import './styles/main.css';

// Redirect component for after login
const RedirectAfterLogin = () => {
  const { user } = useAuth();
  
  useEffect(() => {
    if (user) {
      const redirectUrl = sessionStorage.getItem('redirectUrl') || '/designs';
      sessionStorage.removeItem('redirectUrl');
      window.location.href = redirectUrl;
    }
  }, [user]);
  
  return (
    <div className="loading-container">
      <div className="loading-spinner"></div>
      <p>Login successful, redirecting...</p>
    </div>
  );
};

// Debug route component
const DebugRoute = () => {
  return (
    <div className="main-content">
      <h1>Authentication Debug Page</h1>
      <p>This page shows detailed information about the authentication state.</p>
      <AuthDebug />
    </div>
  );
};

function App() {
  const isDevelopment = process.env.NODE_ENV === 'development';
  
  return (
    <Router>
      <AuthProvider>
        <div className="app">
          <Navigation />
          <main className="main-content">
            <Routes>
              {/* Public routes - no authentication required */}
              <Route path="/login" element={<Login />} />
              <Route path="/signup" element={<SignUp />} />
              <Route path="/forgot-password" element={<ForgotPassword />} />
              <Route path="/redirect" element={<RedirectAfterLogin />} />
              
              {/* Debug route - only in development */}
              {isDevelopment && (
                <Route path="/debug" element={<DebugRoute />} />
              )}
              
              {/* Protected routes - authentication required */}
              <Route element={<ProtectedRoute />}>
                <Route path="/designs" element={<DesignList />} />
                <Route path="/designs/:id" element={<DesignDetail />} />
                <Route path="/favorites" element={<Favorites />} />
                <Route path="/chat" element={<ChatPage />} />
              </Route>

              {/* Adhoc local debug */}
              <Route path="/designs" element={<DesignList />} />
              <Route path="/designs/:id" element={<DesignDetail />} />
              <Route path="/favorites" element={<Favorites />} />
              <Route path="/chat" element={<ChatPage />} />
              {/*<Route path="/dashboard" element={<Dashboard />} />*/}
              
              {/* Redirect root path to designs */}
              <Route path="/" element={<Navigate to="/designs" replace />} />
              
              {/* Default route - redirect to designs */}
              <Route path="*" element={<Navigate to="/designs" replace />} />
            </Routes>
          </main>
          <footer className="footer">
            <div className="footer-content">
              <p>&copy; {new Date().getFullYear()} Insights Hub. All rights reserved.</p>
              {isDevelopment && (
                <p>
                  <a href="/debug" style={{ color: 'inherit', textDecoration: 'underline' }}>
                    Debug Authentication
                  </a>
                </p>
              )}
            </div>
          </footer>
        </div>
      </AuthProvider>
    </Router>
  );
}

export default App;
