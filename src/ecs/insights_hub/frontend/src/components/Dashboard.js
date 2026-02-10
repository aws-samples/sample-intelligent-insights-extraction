import React, { useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';

const Dashboard = () => {
  const { user } = useAuth();

  useEffect(() => {
    // 这个组件是受保护的，所以用户应该始终可用
    console.log('Dashboard loaded for user:', user);
  }, [user]);

  return (
    <div className="dashboard-container">
      <div className="dashboard-header">
        <h1>您的控制台</h1>
        <p>欢迎回来，{user?.username || user?.attributes?.email || '用户'}！</p>
      </div>
      
      <div className="dashboard-content">
        <div className="dashboard-section">
          <h2>您保存的</h2>
          <div className="dashboard-cards">
            <div className="empty-state">
              <p>您还没有保存任何条目。</p>
              <p>浏览我们的条目集合并保存条目，它们将显示在这里。</p>
            </div>
          </div>
        </div>
        
        <div className="dashboard-section">
          <h2>账户信息</h2>
          <div className="account-info">
            <div className="info-item">
              <span className="label">用户名:</span>
              <span className="value">{user?.username || '不可用'}</span>
            </div>
            <div className="info-item">
              <span className="label">电子邮箱:</span>
              <span className="value">{user?.attributes?.email || '不可用'}</span>
            </div>
            <div className="info-item">
              <span className="label">账户创建时间:</span>
              <span className="value">
                {user?.attributes?.created_at 
                  ? new Date(user.attributes.created_at).toLocaleDateString() 
                  : '不可用'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
