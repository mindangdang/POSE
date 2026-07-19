import type { SavedItem } from '../types/item';

export enum SearchState {
  IDLE = 'idle',
  LOADING = 'loading',
  SUCCESS = 'success',
  EMPTY = 'empty',
  ERROR = 'error'
}

export const mergeUniqueResults = (prev: SavedItem[], incoming: SavedItem[]) => {
  const existingUrls = new Set(prev.map(i => i.source_url).filter(Boolean));
  const uniqueIncoming = incoming.filter((i: SavedItem) => !i.source_url || !existingUrls.has(i.source_url));
  return [...prev, ...uniqueIncoming];
};