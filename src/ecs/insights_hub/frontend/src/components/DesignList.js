import React, { useState, useEffect, useRef } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import axios from 'axios';

// 无图片占位符组件
const ImagePlaceholder = ({ className = '', alt = 'No image' }) => (
  <div className={`image-placeholder ${className}`}>
    <svg
      width="48"
      height="48"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <rect x="3" y="3" width="18" height="18" rx="2" stroke="#9CA3AF" strokeWidth="1.5" fill="none" />
      <circle cx="8.5" cy="8.5" r="1.5" fill="#9CA3AF" />
      <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21" stroke="#9CA3AF" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
    <span className="placeholder-text">{alt}</span>
  </div>
);

const DesignList = () => {
  const [allDesigns, setAllDesigns] = useState([]);  // 存储所有数据
  const [filteredDesigns, setFilteredDesigns] = useState([]);  // 存储筛选后的数据
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedTags, setSelectedTags] = useState([]);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);
  const location = useLocation();
  const navigate = useNavigate();

  // 获取数据的 useEffect
  useEffect(() => {
    const fetchDesigns = async () => {
      try {
        setLoading(true);

        // 检查是否有搜索参数
        const urlParams = new URLSearchParams(location.search);
        const searchParam = urlParams.get('search');

        if (searchParam) {
          // 如果有搜索参数，调用搜索API
          const response = await axios.get(`/api/designs/search?q=${encodeURIComponent(searchParam)}`);
          setAllDesigns(response.data);
          setFilteredDesigns(response.data);
        } else if (allDesigns.length === 0) {
          // 只在第一次加载且没有数据时获取所有设计
          const response = await axios.get('/api/designs');
          setAllDesigns(response.data);
          setFilteredDesigns(response.data);
        }

        setError(null);
      } catch (err) {
        console.error('Error fetching designs:', err);
        setError('Failed to load designs. Please try again later.');
      } finally {
        setLoading(false);
      }
    };

    fetchDesigns();
  }, [location.search]); // 只依赖搜索参数变化

  // 前端筛选的 useEffect
  useEffect(() => {
    if (selectedTags.length === 0) {
      // 没有选中标签时显示所有数据
      setFilteredDesigns(allDesigns);
    } else {
      // 有选中标签时进行筛选
      const filtered = allDesigns.filter(design =>
        design.tags && design.tags.some(tag => selectedTags.includes(tag))
      );
      setFilteredDesigns(filtered);
    }
  }, [allDesigns, selectedTags]); // 依赖所有数据和选中的标签

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const clearSearch = () => {
    navigate('/designs');
  };

  const toggleTagSelection = (tag) => {
    setSelectedTags(prevTags => {
      if (prevTags.includes(tag)) {
        return prevTags.filter(t => t !== tag);
      } else {
        return [...prevTags, tag];
      }
    });
  };

  const handleTagRemove = (tagToRemove) => {
    setSelectedTags(selectedTags.filter(tag => tag !== tagToRemove));
  };

  const getAllTags = () => {
    const tagsSet = new Set();
    allDesigns.forEach(design => {  // 使用 allDesigns 获取所有可能的标签
      if (design.tags && Array.isArray(design.tags)) {
        design.tags.forEach(tag => tagsSet.add(tag));
      }
    });
    return Array.from(tagsSet);
  };

  return (
    <div className="designs-container">
      <div className="header-flex-container">
        <div className="design-insights-title">
          <h1>Insights</h1>
        </div>

        <div className="search-filter-container">
          <div className="custom-dropdown-container" ref={dropdownRef}>
            <div
              className="dropdown-header"
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
            >
              <span>{selectedTags.length > 0 ? `${selectedTags.length} tags selected` : 'Select tags'}</span>
              <span className="dropdown-arrow">{isDropdownOpen ? '▲' : '▼'}</span>
            </div>

            {isDropdownOpen && (
              <div className="dropdown-menu">
                {getAllTags().map(tag => (
                  <div
                    key={tag}
                    className={`dropdown-item ${selectedTags.includes(tag) ? 'selected' : ''}`}
                    onClick={() => toggleTagSelection(tag)}
                  >
                    <span className="checkbox">{selectedTags.includes(tag) ? '✓' : ''}</span>
                    <span>{tag}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {selectedTags.length > 0 && (
        <div className="selected-tags-container">
          <div className="selected-tags">
            {selectedTags.map(tag => (
              <span key={tag} className="selected-tag">
                {tag}
                <button
                  className="tag-remove-btn"
                  onClick={() => handleTagRemove(tag)}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        </div>
      )}

      {/*/!* Show current search query *!/*/}
      {/*{new URLSearchParams(location.search).get('search') && (*/}
      {/*  <div className="search-status">*/}
      {/*    <p>*/}
      {/*      Searching for: "<strong>{new URLSearchParams(location.search).get('search')}</strong>"*/}
      {/*      <button className="clear-search-btn" onClick={clearSearch}>*/}
      {/*        Clear search*/}
      {/*      </button>*/}
      {/*    </p>*/}
      {/*  </div>*/}
      {/*)}*/}

      {loading ? (
        <div className="loading-container">
          <div className="loading-spinner"></div>
          <p>Loading insights...</p>
        </div>
      ) : error ? (
        <div className="error-message">{error}</div>
      ) : filteredDesigns.length === 0 ? (
        <div className="empty-state">
          <p>No designs found.</p>
          {selectedTags.length > 0 && (
            <p>Try removing tag filters or searching with different keywords.</p>
          )}
        </div>
      ) : (
        <div className="designs-grid">
          {filteredDesigns.map(design => (
            <Link to={`/designs/${design.id}`} key={design.id} className="design-card">
              <div className="design-image">
                {design.imageUrl && design.imageUrl.trim() !== '' ? (
                  <img
                    src={design.imageUrl}
                    alt={design.title}
                    referrerPolicy="no-referrer"
                    onError={(e) => {
                      console.error('Design card image failed to load:', design.imageUrl);
                      e.target.style.display = 'none';
                      // 显示占位符
                      const placeholder = e.target.parentNode.querySelector('.fallback-placeholder');
                      if (placeholder) {
                        placeholder.style.display = 'flex';
                      }
                    }}
                  />
                ) : null}
                <ImagePlaceholder
                  className={`fallback-placeholder ${!design.imageUrl || design.imageUrl.trim() === '' ? 'show' : ''}`}
                  alt="No image available"
                />
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

export default DesignList;
