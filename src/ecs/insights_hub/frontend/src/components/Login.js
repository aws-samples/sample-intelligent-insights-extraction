import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate, Link, useLocation } from 'react-router-dom';

const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  const [formError, setFormError] = useState('');
  const [debugInfo, setDebugInfo] = useState(null);
  
  const { signIn, completeNewPassword, newPasswordRequired, error, loading, clearError, authConfig } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Get the page user was trying to access, if any
  const from = location.state?.from?.pathname || '/';

  // Add debug info when component mounts
  useEffect(() => {
    const getDebugInfo = async () => {
      try {
        console.log('🔍 Login component mounted, collecting debug info...');
        
        // Check if we can access the backend API
        let apiStatus = 'Unknown';
        try {
          const response = await fetch('/api/auth/config');
          if (response.ok) {
            apiStatus = 'OK';
            const data = await response.json();
            console.log('🔍 API response:', data);
          } else {
            apiStatus = `Error: ${response.status}`;
            console.error('❌ API error:', response.status);
          }
        } catch (err) {
          apiStatus = `Fetch Error: ${err.message}`;
          console.error('❌ API fetch error:', err);
        }
        
        // Collect browser info
        const info = {
          timestamp: new Date().toISOString(),
          userAgent: navigator.userAgent,
          apiStatus,
          authConfig: authConfig || 'Not available',
          localStorage: localStorage.getItem('user') ? 'Has user data' : 'No user data',
          error: error || 'None'
        };
        
        console.log('🔍 Debug info:', info);
        setDebugInfo(info);
      } catch (err) {
        console.error('❌ Error collecting debug info:', err);
      }
    };
    
    getDebugInfo();
  }, [authConfig, error]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');
    clearError();
    console.log('🔍 Login form submitted');

    if (!username || !password) {
      console.log('❌ Validation error: Missing username or password');
      setFormError('Please enter both username and password');
      return;
    }

    try {
      console.log(`🔍 Attempting to sign in user: ${username}`);
      await signIn(username, password);
      
      console.log('✅ Sign in successful, redirecting...');
      // Redirect to the page user was trying to access
      const redirectUrl = sessionStorage.getItem('redirectUrl') || from;
      navigate(redirectUrl, { replace: true });
    } catch (err) {
      console.error('❌ Sign in error:', err);
      if (err.message === 'New password required') {
        console.log('⚠️ New password required flow triggered');
        // Don't set error, this is expected flow
      } else {
        setFormError(err.message || 'Failed to sign in');
      }
    }
  };

  const handleNewPassword = async (e) => {
    e.preventDefault();
    setFormError('');
    clearError();
    console.log('🔍 New password form submitted');

    if (!newPassword || !confirmNewPassword) {
      console.log('❌ Validation error: Missing new password or confirmation');
      setFormError('Please enter new password and confirmation');
      return;
    }

    if (newPassword !== confirmNewPassword) {
      console.log('❌ Validation error: Passwords do not match');
      setFormError('Passwords do not match');
      return;
    }

    try {
      console.log('🔍 Attempting to complete new password challenge');
      await completeNewPassword(newPassword);
      
      console.log('✅ New password set successfully, redirecting...');
      // Redirect to the page user was trying to access
      const redirectUrl = sessionStorage.getItem('redirectUrl') || from;
      navigate(redirectUrl, { replace: true });
    } catch (err) {
      console.error('❌ New password error:', err);
      setFormError(err.message || 'Failed to set new password');
    }
  };

  // Show debug information in development mode
  const renderDebugInfo = () => {
    if (process.env.NODE_ENV !== 'production' && debugInfo) {
      return (
        <div className="debug-info" style={{marginTop: '20px', padding: '10px', background: '#f0f0f0', borderRadius: '4px', fontSize: '12px'}}>
          <h4>Debug Information</h4>
          <pre style={{whiteSpace: 'pre-wrap', overflow: 'auto'}}>
            {JSON.stringify(debugInfo, null, 2)}
          </pre>
        </div>
      );
    }
    return null;
  };

  if (newPasswordRequired) {
    return (
      <div className="auth-container">
        <div className="auth-form">
          <h2>Set New Password</h2>
          
          {(formError || error) && (
            <div className="error-message">
              {formError || error}
            </div>
          )}
          
          <form onSubmit={handleNewPassword}>
            <div className="form-group">
              <label htmlFor="newPassword">New Password</label>
              <input
                type="password"
                id="newPassword"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Enter new password"
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="confirmNewPassword">Confirm New Password</label>
              <input
                type="password"
                id="confirmNewPassword"
                value={confirmNewPassword}
                onChange={(e) => setConfirmNewPassword(e.target.value)}
                placeholder="Confirm new password"
              />
            </div>
            
            <button type="submit" className="auth-button" disabled={loading}>
              {loading ? 'Processing...' : 'Set New Password'}
            </button>
          </form>
          
          {renderDebugInfo()}
        </div>
      </div>
    );
  }

  return (
    <div className="auth-container">
      <div className="auth-form">
        <h2>Sign In</h2>
        
        {(formError || error) && (
          <div className="error-message">
            {formError || error}
          </div>
        )}
        
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="username">Username or Email</label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your username or email"
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
            />
          </div>
          
          <button type="submit" className="auth-button" disabled={loading}>
            {loading ? 'Signing In...' : 'Sign In'}
          </button>
        </form>
        
        <div className="auth-links">
          <p>
            Don't have an account? <Link to="/signup">Sign Up</Link>
          </p>
          <p>
            <Link to="/forgot-password">Forgot Password?</Link>
          </p>
        </div>
        
        {renderDebugInfo()}
      </div>
    </div>
  );
};

export default Login;
