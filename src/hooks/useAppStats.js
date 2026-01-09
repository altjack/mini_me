import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';

export function useAppStats() {
  return useQuery({
    queryKey: ['stats'],
    queryFn: async () => {
      const res = await api.getStats();
      return res.data;
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function useAppActions() {
  const queryClient = useQueryClient();

  const invalidateStats = () => {
    queryClient.invalidateQueries({ queryKey: ['stats'] });
    queryClient.invalidateQueries({ queryKey: ['metrics'] });
  };

  return { invalidateStats };
}
