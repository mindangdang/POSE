import type { SavedItem } from '../types/item';

export enum SearchState {
  IDLE = 'idle',
  LOADING = 'loading',
  SUCCESS = 'success',
  EMPTY = 'empty',
  ERROR = 'error'
}

export const mergeUniqueResults = (prev: SavedItem[], incoming: SavedItem[]) => {
  const existingUrls = new Set(prev.map(i => i.url).filter(Boolean));
  const uniqueIncoming = incoming.filter((i: SavedItem) => !i.url || !existingUrls.has(i.url));
  return [...prev, ...uniqueIncoming];
};