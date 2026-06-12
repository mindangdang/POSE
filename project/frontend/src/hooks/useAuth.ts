import { useCallback, useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { apiJson } from '../lib/api';
import {
  hasAccessToken,
  removeAccessToken,
  setAccessToken,
} from '../lib/token';
import type { AuthResponse } from '../types/auth';
import type { AppUser } from '../types/user';
import { meQueryKey, useMe } from './useMe';

export function useAuth() {
  const queryClient = useQueryClient();
  const [hasToken, setHasToken] = useState(hasAccessToken);
  const meQuery = useMe(hasToken);

  const setSession = useCallback((session: AuthResponse) => {
    setAccessToken(session.access_token);
    setHasToken(true);
    queryClient.setQueryData<AppUser>(meQueryKey, session.user);
  }, [queryClient]);

  const logout = useCallback(() => {
    removeAccessToken();
    setHasToken(false);
    queryClient.setQueryData(meQueryKey, null);
    queryClient.removeQueries({ queryKey: meQueryKey });
  }, [queryClient]);

  const loginAsGuest = useCallback(async () => {
    const session = await apiJson<AuthResponse>('/api/auth/guest', {
      method: 'POST',
    });
    setSession(session);
    return session.user;
  }, [setSession]);

  useEffect(() => {
    if (hasToken && meQuery.isError) {
      logout();
    }
  }, [hasToken, logout, meQuery.isError]);

  return {
    user: hasToken ? meQuery.data ?? null : null,
    isAuthenticated: hasToken && Boolean(meQuery.data),
    isInitializing: hasToken && meQuery.isLoading,
    login: setSession,
    loginAsGuest,
    logout,
  };
}
