import axios from 'axios';

// =============================================================================
// CONFIGURAZIONE API
// =============================================================================

// In produzione usa URL relativo, in locale usa porta 5001
const API_URL = import.meta.env.VITE_API_URL || 
  (window.location.hostname === 'localhost' ? 'http://localhost:5001/api' : '/api');

// LocalStorage keys (same as AuthContext)
const TOKEN_KEY = 'auth_token';
const TOKEN_EXPIRY_KEY = 'auth_token_expiry';

// =============================================================================
// TOKEN HELPERS
// =============================================================================

/**
 * Check if the stored token is expired
 */
const isTokenExpired = () => {
  const expiry = localStorage.getItem(TOKEN_EXPIRY_KEY);
  if (!expiry) return true;
  
  const expiryDate = new Date(expiry);
  const now = new Date();
  
  // Add 1 minute buffer
  return now >= new Date(expiryDate.getTime() - 60000);
};

/**
 * Get the current auth token from localStorage
 */
const getToken = () => {
  if (isTokenExpired()) {
    // Clear expired token
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(TOKEN_EXPIRY_KEY);
    return null;
  }
  return localStorage.getItem(TOKEN_KEY);
};

// =============================================================================
// AXIOS INSTANCE
// =============================================================================

const apiClient = axios.create({
  baseURL: API_URL,
});

// =============================================================================
// REQUEST INTERCEPTOR - Add JWT token to all requests
// =============================================================================

apiClient.interceptors.request.use(
  (config) => {
    const token = getToken();
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// =============================================================================
// RESPONSE INTERCEPTOR - Handle 401 errors (redirect to login)
// =============================================================================

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear token and trigger re-authentication
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(TOKEN_EXPIRY_KEY);
      
      // Dispatch custom event for AuthContext to handle
      window.dispatchEvent(new CustomEvent('auth:unauthorized'));
    }
    return Promise.reject(error);
  }
);

// =============================================================================
// HELPERS
// =============================================================================

// Headers with JWT token (already handled by interceptor, but kept for explicit calls)
const getAuthHeaders = () => {
  const token = getToken();
  return token ? { headers: { 'Authorization': `Bearer ${token}` } } : {};
};

// =============================================================================
// API EXPORTS
// =============================================================================

export const api = {
  // Authentication
  login: (username, password) => apiClient.post('/auth/login', { username, password }),
  
  // Endpoint pubblici (GET - JWT required via interceptor)
  getStats: () => apiClient.get('/stats'),
  getDraft: () => apiClient.get('/draft'),
  getMetricsRange: (startDate, endDate) => {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    return apiClient.get(`/metrics/range?${params.toString()}`);
  },
  getSessionsRange: (startDate, endDate) => {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    return apiClient.get(`/sessions/range?${params.toString()}`);
  },
  
  // Endpoint protetti (POST - JWT required via interceptor)
  generateEmail: () => apiClient.post('/generate', {}),
  approveDraft: () => apiClient.post('/approve', {}),
  rejectDraft: () => apiClient.post('/reject', {}),
  backfill: (startDate, endDate, options = {}) => apiClient.post('/backfill', { 
    start_date: startDate, 
    end_date: endDate,
    ...options
  }),
};
