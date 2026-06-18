import { useCallback, useEffect, useState } from 'react';
import { apiFetch } from '../lib/api';
import { useAuth } from './useAuth';

export function useTaste() {
  const { user } = useAuth();
  const [taste, setTaste] = useState('');

  const refreshTaste = useCallback(async () => {
    if (!user) {
      setTaste('');
      return;
    }

    try {
      const res = await apiFetch(`/api/taste?user_id=${user.id}`, { 
        cache: 'no-store',
      });

      if (!res.ok) {
        throw new Error(`Failed to fetch taste: ${res.status}`);
      }

      const data = await res.json();
      setTaste(data?.summary ?? '');
    } catch (error) {
      console.error('Failed to fetch taste:', error);
      setTaste('');
    }
  }, [user]);

  useEffect(() => {
    void refreshTaste();
  }, [refreshTaste]);

  return {
    taste,
    setTaste,
    refreshTaste,
  };
}
