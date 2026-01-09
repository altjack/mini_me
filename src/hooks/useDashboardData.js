import { useQuery } from '@tanstack/react-query';
import { api } from '../services/api';

export function useDashboardMetrics(startDate, endDate) {
  return useQuery({
    queryKey: ['metrics', startDate, endDate],
    queryFn: async () => {
      const res = await api.getMetricsRange(startDate, endDate);
      if (!res.data.success) {
        throw new Error(res.data.error || 'Errore nel caricamento dati SWI');
      }
      return res.data; // Returns { data: [...], meta: {...} }
    },
    enabled: !!startDate && !!endDate,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

export function useDashboardSessions(startDate, endDate) {
  return useQuery({
    queryKey: ['sessions', startDate, endDate],
    queryFn: async () => {
      const res = await api.getSessionsRange(startDate, endDate);
      if (!res.data.success) {
        throw new Error(res.data.error || 'Errore nel caricamento sessioni');
      }
      return res.data; // Returns { data: {...}, meta: {...} }
    },
    enabled: !!startDate && !!endDate,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

export const DATE_PRESETS = [
  { label: 'Ultimi 7 giorni', days: 7 },
  { label: 'Ultimi 14 giorni', days: 14 },
  { label: 'Ultimi 30 giorni', days: 30 },
  { label: 'Ultimi 45 giorni', days: 45 },
  { label: 'Ultimi 60 giorni', days: 60 },
];
