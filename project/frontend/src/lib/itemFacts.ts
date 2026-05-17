import type { SavedItem } from '../types/item';

type ParsedFacts = Record<string, unknown> | null;

export function parseItemFacts(item: SavedItem): ParsedFacts {
  if (!item.facts) return null;

  if (typeof item.facts === 'string') {
    try {
      const parsed = JSON.parse(item.facts);
      return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : null;
    } catch {
      return null;
    }
  }

  return item.facts;
}

export function getItemTitle(item: SavedItem): string {
  const facts = parseItemFacts(item);
  const lowerTitle = typeof facts?.title === 'string' ? facts.title : undefined;
  const upperTitle = typeof facts?.Title === 'string' ? facts.Title : undefined;
  const title = lowerTitle || upperTitle;

  return title || item.recommend || '제목 없음';
}
