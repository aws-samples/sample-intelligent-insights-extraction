import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const Home = () => {
  const { user } = useAuth();

  return (
    <div className="home-container">
      <div className="hero-section">
        <h1>Welcome to Insights Hub</h1>
        <p className="hero-text">
          Discover and explore innovative designs and ideas
        </p>
        
        <div className="cta-buttons">
          <Link to="/designs" className="cta-button primary">
            Browse Designs
          </Link>
          <Link to="/dashboard" className="cta-button secondary">
            Go to Dashboard
          </Link>
        </div>
      </div>
      
      <div className="features-section">
        <h2>Explore Our Features</h2>
        <div className="features-grid">
          <div className="feature-card">
            <h3>Discover Designs</h3>
            <p>Browse through our collection of innovative designs and ideas</p>
          </div>
          <div className="feature-card">
            <h3>Personalized Dashboard</h3>
            <p>Access your personalized dashboard with saved designs and preferences</p>
          </div>
          <div className="feature-card">
            <h3>Secure Authentication</h3>
            <p>Your account is protected with AWS Cognito secure authentication</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Home;
