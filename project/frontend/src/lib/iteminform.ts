import type { SavedItem } from '../types/item';

type ParsedFacts = Record<string, unknown>;

export function parseItemInforms(item: SavedItem): ParsedFacts {
  return {
    item_id: item.item_id,
    title: item.title,
    price: item.price,
    brand: item.brand,
    category: item.category,
    is_available: item.is_available,
    shop: item.shop,
    source_url: item.source_url,
  };
}

export function getItemTitle(item: SavedItem): string {
  return item.title || '제목 없음';
}
