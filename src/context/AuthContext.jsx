import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { api, setToken, clearToken, getToken, isTokenExpired } from '../services/api';

// =============================================================================
// AUTH CONTEXT
// =============================================================================
// 
// Hybrid authentication system:
// - Primary: HttpOnly cookies (most secure, for same-domain deployments)
// - Fallback: Bearer token in localStorage (for cross-domain like Vercel)
//
// The backend returns token in response body AND sets a cookie.
// Frontend stores token in localStorage as fallback.
// =============================================================================

const AuthContext = createContext(null);

// =============================================================================
// AUTH PROVIDER
// =============================================================================

export const AuthProvider = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  /**
   * Initialize auth state
   * First check localStorage token, then verify with backend
   */
  useEffect(() => {
    const checkAuth = async () => {
      // Quick check: do we have a valid token in localStorage?
      const token = getToken();
      
      if (!token) {
        // No token, definitely not authenticated
        setIsAuthenticated(false);
        setUser(null);
        setIsLoading(false);
        return;
      }
      
      // Token exists, verify it's still valid with backend
      try {
        await api.getStats();
        // Token is valid
        setIsAuthenticated(true);
      } catch (error) {
        // Token invalid or expired
        clearToken();
        setIsAuthenticated(false);
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    };
    
    checkAuth();
  }, []);

  /**
   * Login with username and password
   * Returns { success: boolean, error?: string }
   */
  const login = useCallback(async (username, password) => {
    try {
      const response = await api.login(username, password);
      
      if (response.data.success) {
        // Store token in localStorage (for cross-domain fallback)
        if (response.data.token) {
          setToken(response.data.token, response.data.expires_at);
        }
        
        // Backend also sets HttpOnly cookie (for same-domain)
        setIsAuthenticated(true);
        setUser(response.data.user || username);
        return { success: true };
      }

      return { 
        success: false, 
        error: response.data.error || 'Login failed' 
      };
    } catch (error) {
      console.error('Login error:', error);
      
      // Extract error message from response
      const errorMessage = error.response?.data?.error || 'Network error. Please try again.';
      
      return { 
        success: false, 
        error: errorMessage
      };
    }
  }, []);

  /**
   * Logout - clear token and call backend to clear cookie
   */
  const logout = useCallback(async () => {
    // Clear localStorage token first
    clearToken();
    
    try {
      // Call backend to clear cookie
      await api.logout();
    } catch (error) {
      console.error('Logout error:', error);
      // Continue with logout even if API call fails
    } finally {
      // Clear local state
      setIsAuthenticated(false);
      setUser(null);
    }
  }, []);

  // Context value
  const value = {
    isAuthenticated,
    isLoading,
    user,
    login,
    logout,
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
