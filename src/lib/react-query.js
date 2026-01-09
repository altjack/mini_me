import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false, // Disable automatic refetch on window focus
      retry: 1, // Retry once on failure
      staleTime: 5 * 60 * 1000, // Data is fresh for 5 minutes
    },
  },
});
