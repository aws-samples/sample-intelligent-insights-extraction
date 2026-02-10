import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';

const Favorites = () => {
  const [designs, setDesigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { user } = useAuth();

  useEffect(() => {
    const fetchFavoriteDesigns = async () => {
      try {
        setLoading(true);
        
        // 获取用户名，如果没有则使用测试用户
        const username = user?.username || user?.email || 'test_user';
        
        const response = await axios.get('/api/designs/searchFavorite', {
          params: {
            user_name: username
          }
        });
        
        setDesigns(response.data);
        setError(null);
      } catch (err) {
        console.error('Error fetching favorite designs:', err);
        setError('Failed to load favorite designs. Please try again later.');
      } finally {
        setLoading(false);
      }
    };

    fetchFavoriteDesigns();
  }, [user]);

  if (loading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner"></div>
        <p>Loading favorite designs...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-message">{error}</div>
    );
  }

  return (
    <div className="designs-container">
      <div className="header-flex-container">
        <div className="design-insights-title">
          <h1>My Favorite Designs</h1>
        </div>
      </div>
      
      {designs.length === 0 ? (
        <div className="empty-state">
          <p>No favorite designs found.</p>
          <p>Start exploring and favorite some designs!</p>
          <Link to="/designs" className="back-link">Browse Designs</Link>
        </div>
      ) : (
        <div className="designs-grid">
          {designs.map(design => (
            <Link to={`/designs/${design.id}`} key={design.id} className="design-card">
              <div className="design-image">
                <img src={design.imageUrl} alt={design.title} />
              </div>
              <div className="design-info">
                <h3>{design.title}</h3>
                <p>{design.description.substring(0, 100)}...</p>
                <div className="design-tags">
                  {design.tags && design.tags.map(tag => (
                    <span key={tag} className="design-tag">{tag}</span>
                  ))}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
};

export default Favorites;
