import axios from 'axios';

// =============================================================================
// CONFIGURAZIONE API
// =============================================================================

// In locale usa porta 5001, in produzione usa Cloudflare Tunnel
const API_URL = import.meta.env.VITE_API_URL || 
  (window.location.hostname === 'localhost' 
    ? 'http://localhost:5001/api' 
    : 'https://api.bluetunnel.org/api');

// LocalStorage keys for cross-domain token storage
const TOKEN_KEY = 'auth_token';
const TOKEN_EXPIRY_KEY = 'auth_token_expiry';

// =============================================================================
// NOTES ON AUTHENTICATION
// =============================================================================
// Hybrid authentication system:
// - Primary: HttpOnly cookies (most secure, for same-domain deployments)
// - Fallback: Bearer token in localStorage (for cross-domain like Vercel + separate backend)
//
// The backend returns the token in the response body AND sets a cookie.
// Frontend stores token in localStorage as fallback for cross-domain scenarios.

// =============================================================================
// TOKEN HELPERS
// =============================================================================

/**
 * Check if the stored token is expired
 */
export const isTokenExpired = () => {
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
export const getToken = () => {
  if (isTokenExpired()) {
    // Clear expired token
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(TOKEN_EXPIRY_KEY);
    return null;
  }
  return localStorage.getItem(TOKEN_KEY);
};

/**
 * Store token in localStorage
 */
export const setToken = (token, expiresAt) => {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(TOKEN_EXPIRY_KEY, expiresAt);
};

/**
 * Clear token from localStorage
 */
export const clearToken = () => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(TOKEN_EXPIRY_KEY);
};

// =============================================================================
// AXIOS INSTANCE
// =============================================================================

const apiClient = axios.create({
  baseURL: API_URL,
  withCredentials: true,  // Send cookies with requests (for same-domain)
});

// =============================================================================
// REQUEST INTERCEPTOR - Add Bearer token as fallback
// =============================================================================

apiClient.interceptors.request.use(
  (config) => {
    // Add Bearer token as fallback for cross-domain
    // Cookie will be used if available (same-domain), otherwise Bearer token
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
      clearToken();
      window.dispatchEvent(new CustomEvent('auth:unauthorized'));
    }
    return Promise.reject(error);
  }
);

// =============================================================================
// API EXPORTS
// =============================================================================

export const api = {
  // Authentication
  login: (username, password) => apiClient.post('/auth/login', { username, password }),
  logout: () => apiClient.post('/auth/logout'),
  
  // Endpoint pubblici (GET - JWT required via cookie)
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
      include_channels: true,  // Sempre includi sessioni per canale
    ...options
  }),
};
