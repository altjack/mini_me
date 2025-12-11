import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';

// =============================================================================
// AUTH CONTEXT
// =============================================================================
// 
// Authentication is now handled via HttpOnly cookies.
// This provides better security against XSS attacks as cookies cannot be 
// accessed by JavaScript.
//
// The backend sets/clears the cookie on login/logout.
// The frontend simply tracks authentication state and user info.
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
   * Initialize auth state by checking with backend
   * (cookie is HttpOnly so we can't check it client-side)
   */
  useEffect(() => {
    const checkAuth = async () => {
      try {
        // Try to fetch stats as a way to check if authenticated
        await api.getStats();
        // If successful, we're authenticated (cookie is valid)
        setIsAuthenticated(true);
      } catch (error) {
        // If 401, not authenticated
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
        // Backend sets HttpOnly cookie automatically
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
   * Logout - call backend to clear cookie
   */
  const logout = useCallback(async () => {
    try {
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
