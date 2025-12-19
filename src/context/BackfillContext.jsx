import React, { createContext, useContext, useState, useCallback, useRef } from 'react';
import { api } from '../services/api';
import { logError } from '../utils/logger';

// =============================================================================
// BACKFILL CONTEXT
// =============================================================================
//
// Global state for backfill operations.
// Allows backfill to continue running even when navigating between pages.
// =============================================================================

const BackfillContext = createContext(null);

// =============================================================================
// BACKFILL PROVIDER
// =============================================================================

export const BackfillProvider = ({ children }) => {
  // Backfill state
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Parameters of the current/last backfill
  const [params, setParams] = useState(null);

  // Reference to track if backfill was cancelled
  const cancelledRef = useRef(false);

  /**
   * Start a new backfill operation
   * @param {string} startDate - Start date in YYYY-MM-DD format
   * @param {string} endDate - End date in YYYY-MM-DD format
   * @param {Function} onComplete - Optional callback when backfill completes
   * @returns {Promise<{success: boolean, data?: any, error?: string}>}
   */
  const startBackfill = useCallback(async (startDate, endDate, onComplete) => {
    // Don't allow starting if already running
    if (isRunning) {
      return { success: false, error: 'A backfill is already in progress' };
    }

    // Reset state
    setIsRunning(true);
    setResult(null);
    setError(null);
    setParams({ startDate, endDate });
    cancelledRef.current = false;

    try {
      const res = await api.backfill(startDate, endDate);

      // Check if cancelled while waiting for response
      if (cancelledRef.current) {
        return { success: false, error: 'Backfill was cancelled' };
      }

      const resultData = {
        success: true,
        data: res.data,
        completedAt: new Date().toISOString(),
      };

      setResult(resultData);

      // Call completion callback if provided
      if (onComplete) {
        onComplete();
      }

      return { success: true, data: res.data };
    } catch (err) {
      logError('Backfill failed', err);

      const errorMsg = err.response?.data?.error || err.message || 'Backfill failed';
      setError(errorMsg);
      setResult({
        success: false,
        error: errorMsg,
        completedAt: new Date().toISOString(),
      });

      return { success: false, error: errorMsg };
    } finally {
      setIsRunning(false);
    }
  }, [isRunning]);

  /**
   * Clear the last result (useful to reset UI)
   */
  const clearResult = useCallback(() => {
    setResult(null);
    setError(null);
    setParams(null);
  }, []);

  /**
   * Cancel a pending backfill (only works if the API call hasn't returned yet)
   * Note: This doesn't actually cancel the server-side operation
   */
  const cancelBackfill = useCallback(() => {
    cancelledRef.current = true;
    setIsRunning(false);
  }, []);

  // Context value
  const value = {
    // State
    isRunning,
    result,
    error,
    params,

    // Actions
    startBackfill,
    clearResult,
    cancelBackfill,
  };

  return (
    <BackfillContext.Provider value={value}>
      {children}
    </BackfillContext.Provider>
  );
};

// =============================================================================
// HOOK
// =============================================================================

export const useBackfill = () => {
  const context = useContext(BackfillContext);
  if (!context) {
    throw new Error('useBackfill must be used within a BackfillProvider');
  }
  return context;
};

export default BackfillContext;
