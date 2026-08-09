import type { SavedItem } from '../types/item';

export enum SearchState {
  IDLE = 'idle',
  LOADING = 'loading',
  SUCCESS = 'success',
  EMPTY = 'empty',
  ERROR = 'error'
}

export const mergeUniqueResults = (prev: SavedItem[], incoming: SavedItem[]) => {
  const existingIds = new Set(prev.map((item) => item.product_id));
  const uniqueIncoming = incoming.filter((item: SavedItem) => !existingIds.has(item.product_id));
  return [...prev, ...uniqueIncoming];
};