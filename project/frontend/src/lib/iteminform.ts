import type { SavedItem } from '../types/item';

type ParsedFacts = Record<string, unknown>;

export function parseItemInforms(item: SavedItem): ParsedFacts {
  return {
    product_id: item.product_id,
    title: item.title,
    price: item.price,
    currency: item.currency,
    brand: item.brand,
    category: item.category,
    is_soldout: item.is_soldout,
    shop: item.shop,
    source_url: item.source_url,
    image_url: item.image_url,
    image_vector: item.image_vector,
    created_at: item.created_at,
  };
}

export function getItemTitle(item: SavedItem): string {
  return item.title || '제목 없음';
}
