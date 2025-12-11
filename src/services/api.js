import axios from 'axios';

// =============================================================================
// CONFIGURAZIONE API
// =============================================================================

// In produzione usa URL relativo, in locale usa porta 5001
const API_URL = import.meta.env.VITE_API_URL || 
  (window.location.hostname === 'localhost' ? 'http://localhost:5001/api' : '/api');

// =============================================================================
// NOTES ON AUTHENTICATION
// =============================================================================
// Authentication is now handled via HttpOnly cookies set by the backend.
// This is more secure than localStorage as cookies cannot be accessed by JavaScript,
// protecting against XSS attacks.

// =============================================================================
// AXIOS INSTANCE
// =============================================================================

const apiClient = axios.create({
  baseURL: API_URL,
  withCredentials: true,  // Send cookies with requests (HttpOnly cookie support)
});

// =============================================================================
// REQUEST INTERCEPTOR - No token needed (using HttpOnly cookies)
// =============================================================================

// Cookies are automatically sent by the browser with withCredentials: true
// No need to manually add Authorization header

// =============================================================================
// RESPONSE INTERCEPTOR - Handle 401 errors (redirect to login)
// =============================================================================

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Cookie is handled by backend - just trigger re-authentication
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
    ...options
  }),
};
