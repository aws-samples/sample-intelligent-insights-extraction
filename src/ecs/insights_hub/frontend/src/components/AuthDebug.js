import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';

const AuthDebug = () => {
  const { user, loading, error, authConfig } = useAuth();
  const [apiStatus, setApiStatus] = useState('Checking...');
  const [backendResponse, setBackendResponse] = useState(null);
  const [networkInfo, setNetworkInfo] = useState({});

  useEffect(() => {
    const checkApi = async () => {
      try {
        console.log('🔍 AuthDebug: Checking API status...');
        const response = await fetch('/api/auth/config');
        
        if (response.ok) {
          const data = await response.json();
          setApiStatus('OK');
          setBackendResponse(data);
          console.log('🔍 AuthDebug: API response:', data);
        } else {
          setApiStatus(`Error: ${response.status}`);
          console.error('❌ AuthDebug: API error:', response.status);
        }
      } catch (err) {
        setApiStatus(`Fetch Error: ${err.message}`);
        console.error('❌ AuthDebug: API fetch error:', err);
      }
    };

    const getNetworkInfo = () => {
      const info = {
        online: navigator.onLine,
        userAgent: navigator.userAgent,
        language: navigator.language,
        cookiesEnabled: navigator.cookieEnabled,
        localStorage: typeof localStorage !== 'undefined',
        sessionStorage: typeof sessionStorage !== 'undefined'
      };
      
      setNetworkInfo(info);
      console.log('🔍 AuthDebug: Network info:', info);
    };

    checkApi();
    getNetworkInfo();
  }, []);

  return (
    <div className="debug-container" style={{ padding: '20px', background: '#f8f8f8', borderRadius: '8px', margin: '20px 0' }}>
      <h2>Authentication Debug Information</h2>
      
      <div className="debug-section">
        <h3>Auth Status</h3>
        <ul>
          <li><strong>Loading:</strong> {loading ? 'Yes' : 'No'}</li>
          <li><strong>Authenticated:</strong> {user ? 'Yes' : 'No'}</li>
          <li><strong>Error:</strong> {error || 'None'}</li>
        </ul>
      </div>
      
      <div className="debug-section">
        <h3>User Information</h3>
        {user ? (
          <pre>{JSON.stringify(user, null, 2)}</pre>
        ) : (
          <p>No user authenticated</p>
        )}
      </div>
      
      <div className="debug-section">
        <h3>Auth Configuration</h3>
        {authConfig ? (
          <pre>{JSON.stringify(authConfig, null, 2)}</pre>
        ) : (
          <p>No auth configuration available</p>
        )}
      </div>
      
      <div className="debug-section">
        <h3>API Status</h3>
        <p><strong>Status:</strong> {apiStatus}</p>
        {backendResponse && (
          <pre>{JSON.stringify(backendResponse, null, 2)}</pre>
        )}
      </div>
      
      <div className="debug-section">
        <h3>Network Information</h3>
        <pre>{JSON.stringify(networkInfo, null, 2)}</pre>
      </div>
      
      <div className="debug-section">
        <h3>Local Storage</h3>
        <pre>{JSON.stringify({ user: localStorage.getItem('user') ? 'exists' : 'not found' }, null, 2)}</pre>
        {localStorage.getItem('user') && (
          <details>
            <summary>User Data (click to expand)</summary>
            <pre>{localStorage.getItem('user')}</pre>
          </details>
        )}
      </div>
      
      <div className="debug-actions">
        <button 
          onClick={() => console.log('🔍 Current auth state:', { user, loading, error, authConfig })}
          style={{ padding: '8px 16px', margin: '5px' }}
        >
          Log Auth State to Console
        </button>
        <button 
          onClick={() => localStorage.removeItem('user')}
          style={{ padding: '8px 16px', margin: '5px' }}
        >
          Clear Local Storage
        </button>
        <button 
          onClick={() => window.location.reload()}
          style={{ padding: '8px 16px', margin: '5px' }}
        >
          Reload Page
        </button>
      </div>
    </div>
  );
};

export default AuthDebug;
