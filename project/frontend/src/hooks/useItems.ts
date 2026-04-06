import { useCallback, useEffect, useState } from 'react';

import type { SavedItem } from '../types/item';
import type { AppUser } from '../types/user';

export function useItems(user: AppUser | null) {
  const [items, setItems] = useState<SavedItem[]>([]);

  const refreshItems = useCallback(async () => {
    if (!user) {
      setItems([]);
      return;
    }

    try {
      const res = await fetch(`/api/items?user_id=${user.id}`, { cache: 'no-store' });

      if (!res.ok) {
        throw new Error(`Failed to fetch items: ${res.status}`);
      }

      const data = await res.json();
      setItems(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Failed to fetch items:', error);
      setItems([]);
    }
  }, [user]);

  useEffect(() => {
    void refreshItems();
  }, [refreshItems]);

  return {
    items,
    setItems,
    refreshItems,
  };
}
