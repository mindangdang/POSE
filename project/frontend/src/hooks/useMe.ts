import { useQuery } from '@tanstack/react-query';

import { apiJson } from '../lib/api';
import { hasAccessToken } from '../lib/token';
import type { AppUser } from '../types/user';

type MeResponse = {
  user: AppUser;
};

export const meQueryKey = ['auth', 'me'] as const;

export function useMe(enabled = hasAccessToken()) {
  return useQuery({
    queryKey: meQueryKey,
    queryFn: async () => {
      const data = await apiJson<MeResponse>('/api/auth/me');
      return data.user;
    },
    enabled,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}
