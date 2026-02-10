import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate, Link } from 'react-router-dom';

const SignUp = () => {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [formError, setFormError] = useState('');
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [confirmationCode, setConfirmationCode] = useState('');
  
  const { signUp, confirmSignUp, error, loading, clearError } = useAuth();
  const navigate = useNavigate();

  const validateForm = () => {
    clearError();
    setFormError('');
    
    if (!username || !email || !password || !confirmPassword) {
      setFormError('All fields are required');
      return false;
    }
    
    if (password !== confirmPassword) {
      setFormError('Passwords do not match');
      return false;
    }
    
    if (password.length < 8) {
      setFormError('Password must be at least 8 characters long');
      return false;
    }
    
    // Basic email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      setFormError('Please enter a valid email address');
      return false;
    }
    
    return true;
  };

  const handleSignUp = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) return;
    
    try {
      await signUp(username, password, email);
      setShowConfirmation(true);
    } catch (err) {
      setFormError(err.message || 'Failed to sign up');
    }
  };

  const handleConfirmation = async (e) => {
    e.preventDefault();
    clearError();
    setFormError('');
    
    if (!confirmationCode) {
      setFormError('Please enter the confirmation code');
      return;
    }
    
    try {
      await confirmSignUp(username, confirmationCode);
      navigate('/login');
    } catch (err) {
      setFormError(err.message || 'Failed to confirm sign up');
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-form">
        {!showConfirmation ? (
          <>
            <h2>Create an Account</h2>
            
            {(formError || error) && (
              <div className="error-message">
                {formError || error}
              </div>
            )}
            
            <form onSubmit={handleSignUp}>
              <div className="form-group">
                <label htmlFor="username">Username</label>
                <input
                  type="text"
                  id="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Choose a username"
                />
              </div>
              
              <div className="form-group">
                <label htmlFor="email">Email</label>
                <input
                  type="email"
                  id="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Enter your email"
                />
              </div>
              
              <div className="form-group">
                <label htmlFor="password">Password</label>
                <input
                  type="password"
                  id="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Create a password"
                />
              </div>
              
              <div className="form-group">
                <label htmlFor="confirmPassword">Confirm Password</label>
                <input
                  type="password"
                  id="confirmPassword"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Confirm your password"
                />
              </div>
              
              <button type="submit" className="auth-button" disabled={loading}>
                {loading ? 'Processing...' : 'Sign Up'}
              </button>
            </form>
            
            <div className="auth-links">
              <p>
                Already have an account? <Link to="/login">Sign In</Link>
              </p>
            </div>
          </>
        ) : (
          <>
            <h2>Confirm Your Account</h2>
            
            <p className="confirmation-message" style={{ marginBottom: '2rem' }}>
              We've sent a confirmation code to your email address. Please enter the code below to verify your account.
            </p>
            
            {(formError || error) && (
              <div className="error-message">
                {formError || error}
              </div>
            )}
            
            <form onSubmit={handleConfirmation}>
              <div className="form-group">
                <label htmlFor="confirmationCode">Confirmation Code</label>
                <input
                  type="text"
                  id="confirmationCode"
                  value={confirmationCode}
                  onChange={(e) => setConfirmationCode(e.target.value)}
                  placeholder="Enter confirmation code"
                />
              </div>
              
              <button type="submit" className="auth-button" disabled={loading}>
                {loading ? 'Verifying...' : 'Verify Account'}
              </button>
            </form>
            
            <div className="auth-links">
              <p>
                <button 
                  className="auth-button"
                  onClick={() => setShowConfirmation(false)}
                >
                  Back to Sign Up
                </button>
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default SignUp;
