import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const ForgotPassword = () => {
  const [step, setStep] = useState(1); // 1: 输入用户名, 2: 输入验证码和新密码
  const [username, setUsername] = useState('');
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [message, setMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const { forgotPassword, confirmPassword: confirmPasswordReset, loading, error, clearError } = useAuth();
  const navigate = useNavigate();

  const handleSendCode = async (e) => {
    e.preventDefault();
    
    if (!username.trim()) {
      setMessage('Please enter your username or email');
      return;
    }
    
    setIsSubmitting(true);
    clearError();
    
    try {
      await forgotPassword(username);
      setMessage('Reset code sent to your email. Please check your inbox.');
      setStep(2);
    } catch (err) {
      setMessage(err.message || 'Failed to send reset code');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    
    if (!code.trim()) {
      setMessage('Please enter the verification code');
      return;
    }
    
    if (!newPassword.trim()) {
      setMessage('Please enter a new password');
      return;
    }
    
    if (newPassword !== confirmPassword) {
      setMessage('Passwords do not match');
      return;
    }
    
    if (newPassword.length < 8) {
      setMessage('Password must be at least 8 characters long');
      return;
    }
    
    setIsSubmitting(true);
    clearError();
    
    try {
      await confirmPasswordReset(username, code, newPassword);
      setMessage('Password reset successful! You can now log in with your new password.');
      setTimeout(() => {
        navigate('/login');
      }, 2000);
    } catch (err) {
      setMessage(err.message || 'Failed to reset password');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleBackToStep1 = () => {
    setStep(1);
    setCode('');
    setNewPassword('');
    setConfirmPassword('');
    setMessage('');
    clearError();
  };

  return (
    <div className="auth-container">
      <div className="auth-form">
        <h2>Reset Password</h2>
        
        {step === 1 ? (
          <form onSubmit={handleSendCode}>
            <div className="form-group">
              <label htmlFor="username">Username or Email</label>
              <input
                type="text"
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your username or email"
                disabled={loading || isSubmitting}
                required
              />
            </div>
            
            <button 
              type="submit" 
              className="auth-button"
              disabled={loading || isSubmitting}
            >
              {loading || isSubmitting ? 'Sending...' : 'Send Reset Code'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleResetPassword}>
            <div className="form-group">
              <label htmlFor="code">Verification Code</label>
              <input
                type="text"
                id="code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="Enter the code from your email"
                disabled={loading || isSubmitting}
                required
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="newPassword">New Password</label>
              <input
                type="password"
                id="newPassword"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Enter your new password"
                disabled={loading || isSubmitting}
                required
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="confirmPassword">Confirm New Password</label>
              <input
                type="password"
                id="confirmPassword"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Confirm your new password"
                disabled={loading || isSubmitting}
                required
              />
            </div>
            
            <button 
              type="submit" 
              className="auth-button"
              disabled={loading || isSubmitting}
            >
              {loading || isSubmitting ? 'Resetting...' : 'Reset Password'}
            </button>
            
            <button 
              type="button" 
              className="auth-button secondary"
              onClick={handleBackToStep1}
              disabled={loading || isSubmitting}
            >
              Back
            </button>
          </form>
        )}
        
        {(message || error) && (
          <div className={`message ${error ? 'error' : 'success'}`}>
            {error || message}
          </div>
        )}
        
        <div className="auth-links">
          <p>
            Remember your password? <Link to="/login">Sign In</Link>
          </p>
          <p>
            Don't have an account? <Link to="/signup">Sign Up</Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default ForgotPassword;
