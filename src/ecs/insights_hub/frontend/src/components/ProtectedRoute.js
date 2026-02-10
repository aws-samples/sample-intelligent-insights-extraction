import React, { useEffect } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const ProtectedRoute = () => {
  const { user, loading } = useAuth();
  const location = useLocation();

  // 记录当前尝试访问的URL，以便登录后重定向回来
  useEffect(() => {
    if (!user && !loading) {
      sessionStorage.setItem('redirectUrl', location.pathname);
    }
  }, [user, loading, location]);

  // 显示加载状态
  if (loading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner"></div>
        <p>加载中...</p>
      </div>
    );
  }

  // 如果未认证，重定向到登录页面
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  // 渲染受保护的内容
  return <Outlet />;
};

export default ProtectedRoute;
