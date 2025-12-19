import React, { createContext, useContext, useState, useCallback } from 'react';

// =============================================================================
// PROMO CONTEXT
// =============================================================================
//
// Global state for promo comparison settings.
// Persists selected promo and comparison dates when navigating between pages.
// =============================================================================

const PromoContext = createContext(null);

// =============================================================================
// PROMO PROVIDER
// =============================================================================

export const PromoProvider = ({ children }) => {
  // Selected promotion
  const [selectedPromo, setSelectedPromo] = useState(null);

  // Comparison period dates
  const [compStartDate, setCompStartDate] = useState('');
  const [compEndDate, setCompEndDate] = useState('');

  /**
   * Update comparison dates
   */
  const setComparisonDates = useCallback((start, end) => {
    setCompStartDate(start || '');
    setCompEndDate(end || '');
  }, []);

  /**
   * Clear all promo state
   */
  const clearPromoState = useCallback(() => {
    setSelectedPromo(null);
    setCompStartDate('');
    setCompEndDate('');
  }, []);

  // Context value
  const value = {
    selectedPromo,
    setSelectedPromo,
    compStartDate,
    setCompStartDate,
    compEndDate,
    setCompEndDate,
    setComparisonDates,
    clearPromoState,
  };

  return (
    <PromoContext.Provider value={value}>
      {children}
    </PromoContext.Provider>
  );
};

// =============================================================================
// HOOK
// =============================================================================

export const usePromo = () => {
  const context = useContext(PromoContext);
  if (!context) {
    throw new Error('usePromo must be used within a PromoProvider');
  }
  return context;
};

export default PromoContext;
