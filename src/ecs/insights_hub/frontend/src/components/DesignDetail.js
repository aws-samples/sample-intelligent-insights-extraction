import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';

// 无图片占位符组件
const ImagePlaceholder = ({ className = '', alt = 'No image', size = 'large' }) => (
  <div className={`image-placeholder ${className} ${size}`}>
    <svg
      width={size === 'large' ? '80' : '48'}
      height={size === 'large' ? '80' : '48'}
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

// 图片模态框组件
const ImageModal = ({ isOpen, onClose, images, currentIndex, onPrevious, onNext, onJumpTo, title }) => {
  const handleKeyDown = React.useCallback((e) => {
    if (e.key === 'Escape') onClose();
    if (e.key === 'ArrowLeft') onPrevious();
    if (e.key === 'ArrowRight') onNext();
  }, [onClose, onPrevious, onNext]);

  React.useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, handleKeyDown]);

  // 所有 hooks 调用完成后再进行条件检查
  if (!isOpen || !images || images.length === 0) return null;

  const currentImage = images[currentIndex];
  if (!currentImage || currentImage.trim() === '') return null;

  return (
    <div className="image-modal-overlay" onClick={onClose}>
      <div className="image-modal-content" onClick={(e) => e.stopPropagation()}>
        {/* 关闭按钮 */}
        <button className="image-modal-close" onClick={onClose}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>

        {/* 图片计数器 */}
        <div className="image-modal-counter">
          {currentIndex + 1} / {images.length}
        </div>

        {/* 主图片 */}
        <div className="image-modal-image-container">
          <img
            src={currentImage}
            alt={`${title} - 图片 ${currentIndex + 1}`}
            className="image-modal-image"
            referrerPolicy="no-referrer"
            onLoad={(e) => {
              // 图片加载完成后显示
              e.target.style.opacity = '1';
            }}
            onError={(e) => {
              e.target.style.display = 'none';
            }}
            style={{ opacity: 0 }} // 初始隐藏，加载完成后显示
          />
        </div>

        {/* 导航按钮 */}
        {images.length > 1 && (
          <>
            <button
              className="image-modal-nav image-modal-prev"
              onClick={onPrevious}
              disabled={currentIndex === 0}
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <path d="M15 18l-6-6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <button
              className="image-modal-nav image-modal-next"
              onClick={onNext}
              disabled={currentIndex === images.length - 1}
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <path d="M9 18l6-6-6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </>
        )}

        {/* 缩略图导航 */}
        {images.length > 1 && (
          <div className="image-modal-thumbnails">
            {images.map((img, index) => (
              <div
                key={index}
                className={`image-modal-thumbnail ${index === currentIndex ? 'active' : ''}`}
                onClick={() => onJumpTo(index)}
              >
                {img && img.trim() !== '' ? (
                  <img
                    src={img}
                    alt={`缩略图 ${index + 1}`}
                    referrerPolicy="no-referrer"
                    onError={(e) => {
                      e.target.style.display = 'none';
                    }}
                  />
                ) : (
                  <div className="thumbnail-placeholder">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                      <rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" strokeWidth="1.5" />
                      <circle cx="8.5" cy="8.5" r="1.5" fill="currentColor" />
                      <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21" stroke="currentColor" strokeWidth="1.5" />
                    </svg>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

const DesignDetail = () => {
  const { id } = useParams();
  const [design, setDesign] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [favoriteLoading, setFavoriteLoading] = useState(false);
  const [favoriteMessage, setFavoriteMessage] = useState('');
  const [selectedImage, setSelectedImage] = useState(null);
  const [selectedImageIndex, setSelectedImageIndex] = useState(0);
  const { user } = useAuth();

  useEffect(() => {
    const fetchDesign = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`/api/designs/${id}`);
        console.log('Design data received:', response.data);
        console.log('Design keys:', Object.keys(response.data));
        console.log('timeUpdated value:', response.data.timeUpdated);
        console.log('originalUrl value:', response.data.originalUrl);
        setDesign(response.data);
        setError(null);
      } catch (err) {
        console.error('Error fetching design details:', err);
        setError('加载详情失败。请稍后再试。');
      } finally {
        setLoading(false);
      }
    };

    fetchDesign();
  }, [id]);

  // 图片模态框处理函数
  const handleImageClick = (imageUrl, index) => {
    setSelectedImage(imageUrl);
    setSelectedImageIndex(index);
  };

  const closeImageModal = () => {
    setSelectedImage(null);
    setSelectedImageIndex(0);
  };

  const goToPreviousImage = () => {
    if (design.relatedImages && selectedImageIndex > 0) {
      const newIndex = selectedImageIndex - 1;
      setSelectedImageIndex(newIndex);
      setSelectedImage(design.relatedImages[newIndex]);
    }
  };

  const goToNextImage = () => {
    if (design.relatedImages && selectedImageIndex < design.relatedImages.length - 1) {
      const newIndex = selectedImageIndex + 1;
      setSelectedImageIndex(newIndex);
      setSelectedImage(design.relatedImages[newIndex]);
    }
  };

  const jumpToImage = (targetIndex) => {
    if (design.relatedImages && targetIndex >= 0 && targetIndex < design.relatedImages.length) {
      setSelectedImageIndex(targetIndex);
      setSelectedImage(design.relatedImages[targetIndex]);
    }
  };

  const handleFavorite = async () => {
    try {
      setFavoriteLoading(true);
      setFavoriteMessage('');

      // 获取用户名，如果没有则使用测试用户
      const username = user?.username || user?.email || 'test_user';

      console.log('Favoriting design:', { design_id: id, username });

      const response = await axios.post('/api/designs/favorite', {
        design_id: id,
        favoriteUser: username
      });

      console.log('Favorite response:', response.data);

      if (response.data.success) {
        setFavoriteMessage(response.data.message || '已成功收藏！');
      } else {
        setFavoriteMessage('收藏失败，请稍后再试。');
      }

      // 3秒后清除消息
      setTimeout(() => {
        setFavoriteMessage('');
      }, 3000);

    } catch (err) {
      console.error('Error favoriting design:', err);
      const errorMessage = err.response?.data?.detail || '收藏失败，请稍后再试。';
      setFavoriteMessage(errorMessage);

      // 3秒后清除错误消息
      setTimeout(() => {
        setFavoriteMessage('');
      }, 3000);
    } finally {
      setFavoriteLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner"></div>
        <p>加载详情...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-container">
        <div className="error-message">{error}</div>
        <Link to="/designs" className="back-link">返回列表</Link>
      </div>
    );
  }

  if (!design) {
    return (
      <div className="not-found-container">
        <h2>未找到条目</h2>
        <p>您查找的条目不存在或已被移除。</p>
        <Link to="/designs" className="back-link">返回列表</Link>
      </div>
    );
  }

  return (
    <div className="design-detail-container">
      <div className="design-detail-header">
        <Link to="/designs" className="back-link">← 返回列表</Link>
        <h1>{design.title}</h1>
        <div className="design-tags">
          {design.tags && design.tags.map(tag => (
            <span key={tag} className="design-tag">{tag}</span>
          ))}
        </div>
      </div>

      <div className="design-detail-content">
        <div className={`design-main-image ${!design.imageUrl || design.imageUrl.trim() === '' ? 'no-image' : 'has-image'}`}>
          {design.imageUrl && design.imageUrl.trim() !== '' ? (
            <img
              src={design.imageUrl}
              alt={design.title}
              referrerPolicy="no-referrer"
              onError={(e) => {
                console.error('Main image failed to load:', design.imageUrl);
                e.target.style.display = 'none';
                // 显示占位符并更新容器类名
                const container = e.target.parentNode;
                const placeholder = container.querySelector('.fallback-placeholder');
                if (placeholder) {
                  placeholder.style.display = 'flex';
                  container.className = container.className.replace('has-image', 'no-image');
                }
              }}
            />
          ) : (
            <ImagePlaceholder
              className="fallback-placeholder show"
              alt="No image available"
              size="large"
            />
          )}
          {design.imageUrl && design.imageUrl.trim() !== '' && (
            <ImagePlaceholder
              className="fallback-placeholder"
              alt="Image failed to load"
              size="large"
            />
          )}
        </div>

        <div className="design-description">
          <h2>描述</h2>
          <p>{design.description}</p>

          {design.originalUrl && (
            <>
              <h2>原始URL</h2>
              <p>{design.originalUrl}</p>
            </>
          )}

          {design.timeUpdated && (
            <>
              <h2>更新时间</h2>
              <p>{design.timeUpdated}</p>
            </>
          )}

          <div className="design-actions">
            <div className="action-row">
              <button
                className={`action-button save ${favoriteLoading ? 'loading' : ''}`}
                onClick={handleFavorite}
                disabled={favoriteLoading}
              >
                {favoriteLoading ? '收藏中...' : '收藏'}
              </button>
              {favoriteMessage && (
                <div className={`favorite-message ${favoriteMessage.includes('失败') ? 'error' : 'success'}`}>
                  {favoriteMessage}
                </div>
              )}
            </div>
          </div>

          <div className="section-divider"></div>

          {design.basicProductInfo && (
            <>
              <h2>基本产品信息</h2>
              <div className="info-table">
                {design.basicProductInfo.coreFunctions && (
                  <div className="info-row">
                    <div className="info-label">核心功能</div>
                    <div className="info-value">{design.basicProductInfo.coreFunctions}</div>
                  </div>
                )}
                {design.basicProductInfo.materialsSpecs && (
                  <div className="info-row">
                    <div className="info-label">材料和规格</div>
                    <div className="info-value">{design.basicProductInfo.materialsSpecs}</div>
                  </div>
                )}
                {design.basicProductInfo.imagesDescriptions && (
                  <div className="info-row">
                    <div className="info-label">图片和描述</div>
                    <div className="info-value">{design.basicProductInfo.imagesDescriptions}</div>
                  </div>
                )}
              </div>
            </>
          )}

          {design.targetUsers && (
            <>
              <h2>目标用户和应用场景</h2>
              <div className="info-table">
                {design.targetUsers.mainConsumers && (
                  <div className="info-row">
                    <div className="info-label">主要消费群体</div>
                    <div className="info-value">{design.targetUsers.mainConsumers}</div>
                  </div>
                )}
                {design.targetUsers.applicationScenarios && (
                  <div className="info-row">
                    <div className="info-label">应用场景</div>
                    <div className="info-value">{design.targetUsers.applicationScenarios}</div>
                  </div>
                )}
              </div>
            </>
          )}


          {design.pricingInfo && (
            <>
              <h2>价格和竞争格局</h2>
              <div className="info-table">
                {design.pricingInfo.price && (
                  <div className="info-row">
                    <div className="info-label">价格</div>
                    <div className="info-value">{design.pricingInfo.price}</div>
                  </div>
                )}
                {design.pricingInfo.salesVolume && (
                  <div className="info-row">
                    <div className="info-label">销售量</div>
                    <div className="info-value">{design.pricingInfo.salesVolume}</div>
                  </div>
                )}
                {design.pricingInfo.competitionSection && (
                  <div className="info-row">
                    <div className="info-label">竞争分析</div>
                    <div className="info-value">{design.pricingInfo.competitionSection}</div>
                  </div>
                )}
                {design.pricingInfo.priceDifferentiators && design.pricingInfo.priceDifferentiators.length > 0 && (
                  <div className="info-row">
                    <div className="info-label">价格差异因素</div>
                    <div className="info-value">
                      <ul className="info-list">
                        {design.pricingInfo.priceDifferentiators.map((item, index) => (
                          <li key={index}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}

          {design.marketInfo && (
            <>
              <h2>市场机会和风险</h2>
              <div className="info-table">
                {design.marketInfo.opportunities && (
                  <div className="info-row">
                    <div className="info-label">机会</div>
                    <div className="info-value">{design.marketInfo.opportunities}</div>
                  </div>
                )}
                {design.marketInfo.risks && (
                  <div className="info-row">
                    <div className="info-label">风险</div>
                    <div className="info-value">{design.marketInfo.risks}</div>
                  </div>
                )}
              </div>
            </>
          )}

          {design.productDependencies && (
            <>
              <h2>产品依赖和配套需求</h2>
              <div className="info-table">
                {design.productDependencies.independentUsage !== undefined && (
                  <div className="info-row">
                    <div className="info-label">独立使用</div>
                    <div className="info-value">{design.productDependencies.independentUsage ? '是' : '否'}</div>
                  </div>
                )}
                {design.productDependencies.essentialAccessories && design.productDependencies.essentialAccessories.length > 0 && (
                  <div className="info-row">
                    <div className="info-label">必要配件</div>
                    <div className="info-value">
                      <ul className="info-list">
                        {design.productDependencies.essentialAccessories.map((item, index) => (
                          <li key={index}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
                {design.productDependencies.recommendedComplements && design.productDependencies.recommendedComplements.length > 0 && (
                  <div className="info-row">
                    <div className="info-label">推荐配套产品</div>
                    <div className="info-value">
                      <ul className="info-list">
                        {design.productDependencies.recommendedComplements.map((item, index) => (
                          <li key={index}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
                {design.productDependencies.relatedPrompts && (
                  <div className="info-row">
                    <div className="info-label">相关提示</div>
                    <div className="info-value">{design.productDependencies.relatedPrompts}</div>
                  </div>
                )}
              </div>
            </>
          )}

          {design.productInnovation && (
            <>
              <h2>产品创新和差异化</h2>
              <div className="info-table">
                {design.productInnovation.innovations && (
                  <div className="info-row">
                    <div className="info-label">创新点</div>
                    <div className="info-value">{design.productInnovation.innovations}</div>
                  </div>
                )}
                {design.productInnovation.differentiation && (
                  <div className="info-row">
                    <div className="info-label">差异化亮点</div>
                    <div className="info-value">{design.productInnovation.differentiation}</div>
                  </div>
                )}
                {design.productInnovation.patentOrExclusive && (
                  <div className="info-row">
                    <div className="info-label">专利或独家技术</div>
                    <div className="info-value">{design.productInnovation.patentOrExclusive}</div>
                  </div>
                )}
              </div>
            </>
          )}

          {design.durabilityInfo && (
            <>
              <h2>耐用性和环保属性</h2>
              <div className="info-table">
                {design.durabilityInfo.durability && (
                  <div className="info-row">
                    <div className="info-label">预计使用寿命</div>
                    <div className="info-value">
                      {design.durabilityInfo.durability.includes('Estimated lifespan') ? (
                        <>
                          {design.durabilityInfo.durability.replace(
                            /(Estimated lifespan of [^.]+\.)/,
                            '<strong class="lifespan">$1</strong>'
                          ).split('<strong class="lifespan">').map((part, i, arr) =>
                            i === 0 ? part : part.split('</strong>').map((subPart, j) =>
                              j === 0 ? <strong key={`${i}-${j}`} className="lifespan">{subPart}</strong> : subPart
                            )
                          )}
                        </>
                      ) : design.durabilityInfo.durability}
                    </div>
                  </div>
                )}
                {design.durabilityInfo.environmentalInfo && (
                  <div className="info-row">
                    <div className="info-label">环保信息</div>
                    <div className="info-value">{design.durabilityInfo.environmentalInfo}</div>
                  </div>
                )}

              </div>
            </>
          )}

          {design.supplyChainInfo && (
            <>
              <h2>供应链和库存</h2>
              <div className="info-table">
                {design.supplyChainInfo.inventory && (
                  <div className="info-row">
                    <div className="info-label">库存</div>
                    <div className="info-value">{design.supplyChainInfo.inventory}</div>
                  </div>
                )}
                {design.supplyChainInfo.supplyStability && (
                  <div className="info-row">
                    <div className="info-label">供应稳定性</div>
                    <div className="info-value">{design.supplyChainInfo.supplyStability}</div>
                  </div>
                )}
              </div>
            </>
          )}

          {design.userFeedbackInfo && (
            <>
              <h2>用户反馈和关注点</h2>
              <div className="info-table">
                {design.userFeedbackInfo.userConcerns && (
                  <div className="info-row">
                    <div className="info-label">用户关注点</div>
                    <div className="info-value">{design.userFeedbackInfo.userConcerns}</div>
                  </div>
                )}
                {design.userFeedbackInfo.commonIssues && (
                  <div className="info-row">
                    <div className="info-label">常见问题</div>
                    <div className="info-value">{design.userFeedbackInfo.commonIssues}</div>
                  </div>
                )}
                {design.userFeedbackInfo.positiveHighlights && (
                  <div className="info-row">
                    <div className="info-label">正面评价</div>
                    <div className="info-value">{design.userFeedbackInfo.positiveHighlights}</div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {design.relatedImages && design.relatedImages.length > 0 && (
        <div className="related-images">
          <h2>相关图片</h2>
          <div className="image-gallery">
            {design.relatedImages
              .filter(img => img && img.trim() !== '') // 过滤掉空的图片URL
              .map((img, index) => (
                <div key={index} className="gallery-image">
                  <div className="gallery-image-wrapper" onClick={() => handleImageClick(img, index)}>
                    <img
                      src={img}
                      alt={`${design.title} - 图片 ${index + 1}`}
                      referrerPolicy="no-referrer"
                      onError={(e) => {
                        console.error(`Related image ${index} failed to load:`, img);
                        // 隐藏失败的图片
                        e.target.style.display = 'none';
                        // 显示占位符
                        const placeholder = e.target.parentNode.parentNode.querySelector('.fallback-placeholder');
                        if (placeholder) {
                          placeholder.style.display = 'flex';
                        }
                      }}
                    />
                    <div className="gallery-image-overlay">
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                        <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                      <span>点击放大</span>
                    </div>
                  </div>
                  <ImagePlaceholder
                    className="fallback-placeholder"
                    alt={`图片加载失败`}
                    size="small"
                  />
                </div>
              ))}
          </div>
        </div>
      )}

      {/* 图片模态框 */}
      <ImageModal
        isOpen={!!selectedImage}
        onClose={closeImageModal}
        images={design?.relatedImages || []}
        currentIndex={selectedImageIndex}
        onPrevious={goToPreviousImage}
        onNext={goToNextImage}
        onJumpTo={jumpToImage}
        title={design?.title || ''}
      />
    </div>
  );
};

export default DesignDetail;
