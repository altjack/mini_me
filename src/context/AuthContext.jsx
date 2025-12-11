import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

// =============================================================================
// AUTH CONTEXT
// =============================================================================

const AuthContext = createContext(null);

// LocalStorage key for JWT token
const TOKEN_KEY = 'auth_token';
const TOKEN_EXPIRY_KEY = 'auth_token_expiry';

/**
 * Check if a JWT token is expired based on stored expiry time
 */
const isTokenExpired = () => {
  const expiry = localStorage.getItem(TOKEN_EXPIRY_KEY);
  if (!expiry) return true;
  
  const expiryDate = new Date(expiry);
  const now = new Date();
  
  // Add 1 minute buffer to avoid edge cases
  return now >= new Date(expiryDate.getTime() - 60000);
};

/**
 * Parse JWT payload without verification (for client-side expiry check)
 */
const parseJwtPayload = (token) => {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
};

// =============================================================================
// AUTH PROVIDER
// =============================================================================

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check if user is authenticated
  const isAuthenticated = !!token && !isTokenExpired();

  /**
   * Initialize auth state from localStorage
   */
  useEffect(() => {
    const storedToken = localStorage.getItem(TOKEN_KEY);
    
    if (storedToken && !isTokenExpired()) {
      setToken(storedToken);
      
      // Extract user from token payload
      const payload = parseJwtPayload(storedToken);
      if (payload?.sub) {
        setUser(payload.sub);
      }
    } else {
      // Clear expired token
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(TOKEN_EXPIRY_KEY);
      setToken(null);
      setUser(null);
    }
    
    setIsLoading(false);
  }, []);

  /**
   * Login with username and password
   * Returns { success: boolean, error?: string }
   */
  const login = useCallback(async (username, password) => {
    try {
      const API_URL = import.meta.env.VITE_API_URL || 
        (window.location.hostname === 'localhost' ? 'http://localhost:5001/api' : '/api');
      
      const response = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });

      const data = await response.json();

      if (!response.ok) {
        return { 
          success: false, 
          error: data.error || 'Login failed' 
        };
      }

      if (data.success && data.token) {
        // Store token and expiry
        localStorage.setItem(TOKEN_KEY, data.token);
        localStorage.setItem(TOKEN_EXPIRY_KEY, data.expires_at);
        
        setToken(data.token);
        setUser(data.user || username);
        
        return { success: true };
      }

      return { 
        success: false, 
        error: 'Invalid response from server' 
      };
    } catch (error) {
      console.error('Login error:', error);
      return { 
        success: false, 
        error: 'Network error. Please try again.' 
      };
    }
  }, []);

  /**
   * Logout - clear token and redirect to login
   */
  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(TOKEN_EXPIRY_KEY);
    setToken(null);
    setUser(null);
  }, []);

  /**
   * Get the current auth token (for API calls)
   */
  const getToken = useCallback(() => {
    if (isTokenExpired()) {
      logout();
      return null;
    }
    return token;
  }, [token, logout]);

  // Context value
  const value = {
    isAuthenticated,
    isLoading,
    token,
    user,
    login,
    logout,
    getToken,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

// =============================================================================
// HOOK
// =============================================================================

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export default AuthContext;
