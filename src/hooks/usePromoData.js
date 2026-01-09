import { useQuery } from '@tanstack/react-query';
import { api } from '../services/api';

/**
 * Hook per recuperare le metriche di un range specifico
 * Usato sia per il periodo promo che per il confronto
 */
export function useMetricsRange(startDate, endDate, enabled = true) {
  return useQuery({
    queryKey: ['metrics', startDate, endDate],
    queryFn: async () => {
      const res = await api.getMetricsRange(startDate, endDate);
      if (!res.data.success) {
        throw new Error(res.data.error || 'Errore nel caricamento metriche');
      }
      return res.data;
    },
    enabled: enabled && !!startDate && !!endDate,
    staleTime: 10 * 60 * 1000,
  });
}

/**
 * Hook per recuperare SWI per commodity
 */
export function useSwiByCommodity(startDate, endDate, enabled = true) {
  return useQuery({
    queryKey: ['swi-by-commodity', startDate, endDate],
    queryFn: async () => {
      const res = await api.getSwiByCommodityRange(startDate, endDate);
      if (!res.data.success) {
        throw new Error(res.data.error || 'Errore nel caricamento SWI per commodity');
      }
      return res.data;
    },
    enabled: enabled && !!startDate && !!endDate,
    staleTime: 10 * 60 * 1000,
  });
}

/**
 * Hook per recuperare performance prodotti
 */
export function useProductsPerformance(startDate, endDate, enabled = true) {
  return useQuery({
    queryKey: ['products-performance', startDate, endDate],
    queryFn: async () => {
      const res = await api.getProductsRange(startDate, endDate);
      if (!res.data.success) {
        throw new Error(res.data.error || 'Errore nel caricamento performance prodotti');
      }
      return res.data;
    },
    enabled: enabled && !!startDate && !!endDate,
    staleTime: 10 * 60 * 1000,
  });
}
