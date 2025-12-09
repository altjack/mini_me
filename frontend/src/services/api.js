import axios from 'axios';

// Configurazione API
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5001/api';
const API_KEY = import.meta.env.VITE_API_KEY || '';

// Headers con API Key per endpoint autenticati
const getAuthHeaders = () => ({
  headers: API_KEY ? { 'X-API-Key': API_KEY } : {}
});

export const api = {
  // Endpoint pubblici (GET - no auth required)
  getStats: () => axios.get(`${API_URL}/stats`),
  getDraft: () => axios.get(`${API_URL}/draft`),
  getMetricsRange: (startDate, endDate) => {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    return axios.get(`${API_URL}/metrics/range?${params.toString()}`);
  },
  getSessionsRange: (startDate, endDate) => {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    return axios.get(`${API_URL}/sessions/range?${params.toString()}`);
  },
  
  // Endpoint protetti (POST - API key required)
  generateEmail: () => axios.post(`${API_URL}/generate`, {}, getAuthHeaders()),
  approveDraft: () => axios.post(`${API_URL}/approve`, {}, getAuthHeaders()),
  rejectDraft: () => axios.post(`${API_URL}/reject`, {}, getAuthHeaders()),
  backfill: (startDate, endDate) => axios.post(
    `${API_URL}/backfill`, 
    { start_date: startDate, end_date: endDate },
    getAuthHeaders()
  ),
};

