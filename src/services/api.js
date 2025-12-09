import axios from 'axios';

// =============================================================================
// CONFIGURAZIONE API
// =============================================================================

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5001/api';
const API_KEY = import.meta.env.VITE_API_KEY || '';

// Basic Auth per staging (opzionale)
const STAGING_USER = import.meta.env.VITE_STAGING_USER || '';
const STAGING_PASSWORD = import.meta.env.VITE_STAGING_PASSWORD || '';

// =============================================================================
// AXIOS INSTANCE CON BASIC AUTH
// =============================================================================

// Crea istanza axios con configurazione base
const apiClient = axios.create({
  baseURL: API_URL,
});

// Aggiungi Basic Auth header se configurato
if (STAGING_USER && STAGING_PASSWORD) {
  const basicAuth = btoa(`${STAGING_USER}:${STAGING_PASSWORD}`);
  apiClient.defaults.headers.common['Authorization'] = `Basic ${basicAuth}`;
}

// =============================================================================
// HELPERS
// =============================================================================

// Headers con API Key per endpoint autenticati
const getAuthHeaders = () => ({
  headers: API_KEY ? { 'X-API-Key': API_KEY } : {}
});

// =============================================================================
// API EXPORTS
// =============================================================================

export const api = {
  // Endpoint pubblici (GET - no API key required, ma Basic Auth se staging)
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
  
  // Endpoint protetti (POST - API key required)
  generateEmail: () => apiClient.post('/generate', {}, getAuthHeaders()),
  approveDraft: () => apiClient.post('/approve', {}, getAuthHeaders()),
  rejectDraft: () => apiClient.post('/reject', {}, getAuthHeaders()),
  backfill: (startDate, endDate) => apiClient.post(
    '/backfill', 
    { start_date: startDate, end_date: endDate },
    getAuthHeaders()
  ),
};

