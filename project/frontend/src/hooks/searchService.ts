import { apiFetch } from '../lib/api';
import type { SavedItem } from '../types/item';

const getDomain = (url: string) => {
  try {
    return new URL(url).hostname.replace('www.', '');
  } catch {
    return url.replace(/^https?:\/\//, '').split('/')[0];
  }
};

export const searchService = {
  searchDigging: async (query: string, page: number, selectedShopNames: string[], shops: any[]) => {
    console.log(`[DEBUG] searchDigging 요청: query='${query}', page=${page}`);
    const body: any = { query, page };
    if (selectedShopNames.length > 0) {
      body.domain_map = Object.fromEntries(
        selectedShopNames.map((name) => [
          getDomain(shops.find((s) => s.name === name)?.url || ''),
          name,
        ])
      );
    }

    return apiFetch('/api/pse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  },

  searchLens: async (query: string, pastedFile: File | null) => {
    const formData = new FormData();
    if (pastedFile) formData.append('file', pastedFile);
    if (query) formData.append('query', query);

    return apiFetch('/api/lens', { method: 'POST', body: formData });
  },
};
