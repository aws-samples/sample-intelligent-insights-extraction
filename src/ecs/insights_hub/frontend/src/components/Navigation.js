import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const Navigation = () => {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchQuery, setSearchQuery] = useState('');

  const handleSignOut = async () => {
    try {
      await signOut();
      navigate('/login');
    } catch (error) {
      console.error('Error signing out:', error);
    }
  };

  const handleSearch = (e) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/designs?search=${encodeURIComponent(searchQuery)}`);
    }
  };

  const isActive = (path) => {
    return location.pathname === path;
  };

  return (
    <header className="header">
      <div className="header-container">
        <div className="logo">
          <Link to="/">Insights Hub</Link>
        </div>
        
        <div className="search-bar">
          <form className="search-form" onSubmit={handleSearch}>
            <input
              type="text"
              className="search-input"
              placeholder="Search insights..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <button type="submit" className="search-button">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              </svg>
            </button>
          </form>
        </div>
        
        <div className="nav-links">
          <Link to="/designs" className={isActive('/designs') ? 'active' : ''}>Insights</Link>
          <Link to="/favorites" className={isActive('/favorites') ? 'active' : ''}>Favorites</Link>
          <Link to="/chat" className={isActive('/chat') ? 'active' : ''}>Chat</Link>
          {/*{user && <Link to="/dashboard" className={isActive('/dashboard') ? 'active' : ''}>Dashboard</Link>}*/}
          {user ? (
            <a href="#" onClick={handleSignOut}>Sign Out</a>
          ) : (
            <Link to="/login" className={isActive('/login') ? 'active' : ''}>Sign In</Link>
          )}
        </div>
      </div>
    </header>
  );
};

export default Navigation;
