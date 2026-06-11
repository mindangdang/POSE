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
    const token = localStorage.getItem('access_token');
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const body: any = { query, page };
    if (selectedShopNames.length > 0) {
      body.domain_map = Object.fromEntries(
        selectedShopNames.map((name) => [
          getDomain(shops.find((s) => s.name === name)?.url || ''),
          name,
        ])
      );
    }

    return fetch('/api/pse', { method: 'POST', headers, body: JSON.stringify(body) });
  },

  searchLens: async (query: string, pastedFile: File | null) => {
    const token = localStorage.getItem('access_token');
    const aiHeaders: Record<string, string> = {};
    if (token) aiHeaders['Authorization'] = `Bearer ${token}`;

    const formData = new FormData();
    if (pastedFile) formData.append('file', pastedFile);
    if (query) formData.append('query', query);

    return fetch('/api/lens', { method: 'POST', headers: aiHeaders, body: formData });
  },
};