import React, { createContext, useState, useEffect, useContext } from 'react';
import { CognitoUserPool, CognitoUser, AuthenticationDetails, CognitoUserAttribute } from 'amazon-cognito-identity-js';
import axios from 'axios';

const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
  const [userPool, setUserPool] = useState(null);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [newPasswordRequired, setNewPasswordRequired] = useState(false);
  const [cognitoUser, setCognitoUser] = useState(null);
  const [authConfig, setAuthConfig] = useState(null);

  // 从后端获取 Cognito 配置
  useEffect(() => {
    const initializeAuth = async () => {
      try {
        console.log('🔍 Starting authentication initialization...');
        setLoading(true);
        
        console.log('🔍 Fetching auth config from backend API...');
        const response = await axios.get('/api/auth/config');
        // console.log('🔍 Auth config API response:', response.data);
        
        const { userPoolId, clientId, region } = response.data;
        setAuthConfig(response.data);
        
        if (!userPoolId || !clientId) {
          console.error('❌ Invalid auth configuration - missing userPoolId or clientId');
          throw new Error('Invalid authentication configuration');
        }
        
        // console.log(`🔍 Configuring Cognito User Pool with ID: ${userPoolId} and Client ID: ${clientId}`);
        // 配置 Cognito User Pool
        const poolData = {
          UserPoolId: userPoolId,
          ClientId: clientId
        };
        
        const userPoolInstance = new CognitoUserPool(poolData);
        console.log('✅ User pool instance created successfully');
        setUserPool(userPoolInstance);
        
        // 检查用户是否已登录
        console.log('🔍 Checking for existing user session...');
        const currentUser = userPoolInstance.getCurrentUser();
        
        if (currentUser) {
          console.log(`🔍 Found existing user: ${currentUser.getUsername()}`);
          currentUser.getSession((err, session) => {
            if (err) {
              console.error('❌ Session error:', err);
              setLoading(false);
              return;
            }
            
            if (session && session.isValid()) {
              console.log('✅ User session is valid');
              // 获取用户属性
              currentUser.getUserAttributes((err, attributes) => {
                if (err) {
                  console.error('❌ Error getting user attributes:', err);
                  setLoading(false);
                  return;
                }
                
                console.log('🔍 User attributes:', attributes);
                const userData = {
                  username: currentUser.getUsername(),
                  attributes: attributes ? attributes.reduce((acc, attr) => {
                    acc[attr.getName()] = attr.getValue();
                    return acc;
                  }, {}) : {},
                  token: session.getIdToken().getJwtToken()
                };
                
                console.log('✅ User data processed successfully');
                // 将用户数据存储在 localStorage 中
                const expirationTime = new Date().getTime() + 60 * 60 * 4000; // 4小时
                localStorage.setItem('user', JSON.stringify({
                  user: userData,
                  expiration: expirationTime
                }));
                
                setUser(userData);
                setLoading(false);
              });
            } else {
              console.log('⚠️ User session is invalid or expired');
              setLoading(false);
            }
          });
        } else {
          console.log('🔍 No current user found, checking localStorage...');
          // 检查localStorage中是否有用户数据
          const storedUserData = localStorage.getItem('user');
          if (storedUserData) {
            console.log('🔍 Found user data in localStorage');
            const parsedData = JSON.parse(storedUserData);
            const now = new Date().getTime();
            
            // 检查数据是否过期
            if (parsedData.expiration > now) {
              console.log('✅ localStorage user data is valid');
              setUser(parsedData.user);
            } else {
              console.log('⚠️ localStorage user data is expired');
              // 数据已过期，清除localStorage
              localStorage.removeItem('user');
            }
          } else {
            console.log('🔍 No user data found in localStorage');
          }
          
          setLoading(false);
        }
      } catch (err) {
        console.error('❌ Auth initialization error:', err);
        console.error('❌ Error details:', JSON.stringify(err, null, 2));
        setError(err.message);
        setLoading(false);
      }
    };

    initializeAuth();
  }, []);

  // 登录函数
  const signIn = (username, password) => {
    return new Promise((resolve, reject) => {
      console.log(`🔍 Starting sign in process for user: ${username}`);
      
      if (!userPool) {
        console.error('❌ Authentication not initialized - userPool is null');
        reject(new Error('Authentication not initialized'));
        return;
      }
      
      setLoading(true);
      setError(null);
      
      console.log('🔍 Creating authentication details...');
      const authenticationDetails = new AuthenticationDetails({
        Username: username,
        Password: password
      });
      
      console.log('🔍 Creating Cognito user instance...');
      const cognitoUserInstance = new CognitoUser({
        Username: username,
        Pool: userPool
      });
      
      console.log('🔍 Calling authenticateUser...');
      cognitoUserInstance.authenticateUser(authenticationDetails, {
        onSuccess: (result) => {
          console.log('✅ Authentication successful');
          // 提取用户数据
          console.log('🔍 Extracting user data from token...');
          console.log('🔍 Token payload:', result.getIdToken().payload);
          
          const userData = {
            username: result.getIdToken().payload['cognito:username'] || cognitoUserInstance.getUsername(),
            email: result.getIdToken().payload.email,
            token: result.getIdToken().getJwtToken()
          };
          
          console.log('🔍 User data:', userData);
          
          // 设置过期时间（例如，4小时后）
          const expirationTime = new Date().getTime() + 60 * 60 * 4000; // 4小时
          
          // 将用户数据与过期时间结合
          const userDataWithExpiration = {
            user: userData,
            expiration: expirationTime
          };
          
          // 将用户数据存储在 localStorage 中
          localStorage.setItem('user', JSON.stringify(userDataWithExpiration));
          
          setUser(userData);
          setLoading(false);
          resolve(userData);
        },
        onFailure: (err) => {
          console.error('❌ Authentication failed:', err);
          console.error('❌ Error details:', JSON.stringify(err, null, 2));
          setError(err.message || 'Login failed');
          setLoading(false);
          reject(err);
        },
        newPasswordRequired: (userAttributes, requiredAttributes) => {
          console.log('⚠️ New password required');
          console.log('🔍 User attributes:', userAttributes);
          console.log('🔍 Required attributes:', requiredAttributes);
          
          // 处理需要设置新密码的情况
          setCognitoUser(cognitoUserInstance);
          setNewPasswordRequired(true);
          setLoading(false);
          reject(new Error('New password required'));
        }
      });
    });
  };

  // 完成新密码设置
  const completeNewPassword = (newPassword) => {
    return new Promise((resolve, reject) => {
      console.log('🔍 Starting complete new password process...');
      
      if (!cognitoUser) {
        console.error('❌ User not authenticated - cognitoUser is null');
        reject(new Error('User not authenticated'));
        return;
      }
      
      setLoading(true);
      
      console.log('🔍 Calling completeNewPasswordChallenge...');
      cognitoUser.completeNewPasswordChallenge(newPassword, {}, {
        onSuccess: (result) => {
          console.log('✅ New password set successfully');
          // 提取用户数据
          const userData = {
            username: cognitoUser.getUsername(),
            token: result.getIdToken().getJwtToken()
          };
          
          console.log('🔍 User data after password change:', userData);
          
          // 设置过期时间
          const expirationTime = new Date().getTime() + 60 * 60 * 4000; // 4小时
          
          // 存储用户数据
          localStorage.setItem('user', JSON.stringify({
            user: userData,
            expiration: expirationTime
          }));
          
          setUser(userData);
          setNewPasswordRequired(false);
          setCognitoUser(null);
          setLoading(false);
          resolve(userData);
        },
        onFailure: (err) => {
          console.error('❌ Set new password error:', err);
          console.error('❌ Error details:', JSON.stringify(err, null, 2));
          setError(err.message || 'Failed to set new password');
          setLoading(false);
          reject(err);
        }
      });
    });
  };

  // 注册函数
  const signUp = (username, password, email) => {
    return new Promise((resolve, reject) => {
      console.log(`🔍 Starting sign up process for user: ${username}, email: ${email}`);
      
      if (!userPool) {
        console.error('❌ Authentication not initialized - userPool is null');
        reject(new Error('Authentication not initialized'));
        return;
      }
      
      setLoading(true);
      
      const attributeList = [];
      
      const dataEmail = {
        Name: 'email',
        Value: email
      };
      
      console.log('🔍 Creating attribute list...');
      const attributeEmail = new CognitoUserAttribute(dataEmail);
      attributeList.push(attributeEmail);
      
      console.log('🔍 Calling signUp...');
      userPool.signUp(username, password, attributeList, null, (err, result) => {
        setLoading(false);
        
        if (err) {
          console.error('❌ Sign up error:', err);
          console.error('❌ Error details:', JSON.stringify(err, null, 2));
          setError(err.message || 'Failed to sign up');
          reject(err);
          return;
        }
        
        console.log('✅ Sign up successful');
        console.log('🔍 Sign up result:', result);
        resolve(result.user);
      });
    });
  };

  // 确认注册函数
  const confirmSignUp = (username, code) => {
    return new Promise((resolve, reject) => {
      console.log(`🔍 Starting confirm sign up process for user: ${username}, code: ${code}`);
      
      if (!userPool) {
        console.error('❌ Authentication not initialized - userPool is null');
        reject(new Error('Authentication not initialized'));
        return;
      }
      
      setLoading(true);
      
      console.log('🔍 Creating Cognito user instance...');
      const cognitoUserInstance = new CognitoUser({
        Username: username,
        Pool: userPool
      });
      
      console.log('🔍 Calling confirmRegistration...');
      cognitoUserInstance.confirmRegistration(code, true, (err, result) => {
        setLoading(false);
        
        if (err) {
          console.error('❌ Confirm sign up error:', err);
          console.error('❌ Error details:', JSON.stringify(err, null, 2));
          setError(err.message || 'Failed to confirm sign up');
          reject(err);
          return;
        }
        
        console.log('✅ Confirm sign up successful');
        console.log('🔍 Confirm sign up result:', result);
        resolve(result);
      });
    });
  };

  // 登出函数
  const signOut = () => {
    console.log('🔍 Starting sign out process...');
    
    const currentUser = userPool?.getCurrentUser();
    if (currentUser) {
      console.log(`🔍 Signing out user: ${currentUser.getUsername()}`);
      currentUser.signOut();
      localStorage.removeItem('user');
      setUser(null);
      console.log('✅ Sign out successful');
    } else {
      console.log('⚠️ No current user to sign out');
      localStorage.removeItem('user');
      setUser(null);
    }
  };

  // 忘记密码函数
  const forgotPassword = (username) => {
    return new Promise((resolve, reject) => {
      console.log(`🔍 Starting forgot password process for user: ${username}`);
      
      if (!userPool) {
        console.error('❌ Authentication not initialized - userPool is null');
        reject(new Error('Authentication not initialized'));
        return;
      }
      
      setLoading(true);
      setError(null);
      
      console.log('🔍 Creating Cognito user instance...');
      const cognitoUserInstance = new CognitoUser({
        Username: username,
        Pool: userPool
      });
      
      console.log('🔍 Calling forgotPassword...');
      cognitoUserInstance.forgotPassword({
        onSuccess: (data) => {
          console.log('✅ Forgot password request successful');
          console.log('🔍 Forgot password data:', data);
          setLoading(false);
          resolve(data);
        },
        onFailure: (err) => {
          console.error('❌ Forgot password error:', err);
          console.error('❌ Error details:', JSON.stringify(err, null, 2));
          setError(err.message || 'Failed to send reset code');
          setLoading(false);
          reject(err);
        }
      });
    });
  };

  // 确认忘记密码（重置密码）函数
  const confirmPassword = (username, code, newPassword) => {
    return new Promise((resolve, reject) => {
      console.log(`🔍 Starting confirm password process for user: ${username}`);
      
      if (!userPool) {
        console.error('❌ Authentication not initialized - userPool is null');
        reject(new Error('Authentication not initialized'));
        return;
      }
      
      setLoading(true);
      setError(null);
      
      console.log('🔍 Creating Cognito user instance...');
      const cognitoUserInstance = new CognitoUser({
        Username: username,
        Pool: userPool
      });
      
      console.log('🔍 Calling confirmPassword...');
      cognitoUserInstance.confirmPassword(code, newPassword, {
        onSuccess: () => {
          console.log('✅ Password reset successful');
          setLoading(false);
          resolve();
        },
        onFailure: (err) => {
          console.error('❌ Confirm password error:', err);
          console.error('❌ Error details:', JSON.stringify(err, null, 2));
          setError(err.message || 'Failed to reset password');
          setLoading(false);
          reject(err);
        }
      });
    });
  };

  // 重置错误状态
  const clearError = () => setError(null);

  const value = {
    user,
    loading,
    error,
    newPasswordRequired,
    signIn,
    signUp,
    confirmSignUp,
    signOut,
    completeNewPassword,
    forgotPassword,
    confirmPassword,
    clearError,
    authConfig // 添加配置信息，方便调试
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export default AuthContext;
