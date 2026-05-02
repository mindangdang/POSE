import { motion } from 'framer-motion';
import { Instagram, Sparkles, Trash2 } from 'lucide-react';

import { getItemTitle, parseItemFacts } from '../lib/itemFacts';
import type { SavedItem } from '../types/item';

type FeedItemCardProps = {
  item: SavedItem;
  factKeysToShow: string[];
  onDelete: (id: number) => void | Promise<void>;
  onSelect: () => void;
};

export function FeedItemCard({
  item,
  factKeysToShow,
  onDelete,
  onSelect,
}: FeedItemCardProps) {
  const facts = parseItemFacts(item);
  const title = getItemTitle(item);
  const isProcessingItem =
    item.category.trim().toUpperCase() === 'PROCESSING' ||
    item.sub_category.trim().toUpperCase() === 'PROCESSING' ||
    facts?._source === 'feed_add';
  const categoryLabel = `${item.category}${item.sub_category ? ` > ${item.sub_category}` : ''}`;
  const visibleFacts = facts
    ? Object.entries(facts).filter(
        ([key]) => key.toLowerCase() !== 'title' && factKeysToShow.includes(key.toLowerCase())
      )
    : [];

  return (
    <motion.div
      layout
      onClick={onSelect}
      className="group relative flex h-full flex-col overflow-hidden rounded-3xl border border-black/5 bg-white transition-all duration-300 cursor-pointer hover:-translate-y-1 hover:shadow-2xl"
    >
      <div className="relative aspect-[4/4.6] overflow-hidden bg-gray-100">
        <img
          src={item.image_url?.startsWith('http') || item.image_url?.startsWith('data:') || item.image_url?.startsWith('//') ? item.image_url : item.image_url ? `/api/images/${item.image_url}` : 'https://via.placeholder.com/400x500?text=No+Image'}
          alt={item.category}
          className="h-full w-full object-cover transform transition-transform duration-700 group-hover:scale-105"
          referrerPolicy="no-referrer"
          onError={(e) => {
            (e.target as HTMLImageElement).src = 'https://via.placeholder.com/400x500?text=POSE+Not+Found';
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
      </div>
      <div className="flex flex-1 flex-col p-4">
        <div className="flex items-center justify-between">
          {isProcessingItem ? (
            <span aria-hidden="true" />
          ) : (
            <span className="text-[9px] font-black uppercase tracking-widest text-blue-600 bg-blue-50 px-2 py-1 rounded-md">
              {categoryLabel}
            </span>
          )}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete(item.id);
            }}
            className="opacity-0 group-hover:opacity-100 p-1.5 bg-red-50 text-red-500 rounded-full hover:bg-red-100 transition-all"
            aria-label="Delete item"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
        <p className="mt-2 translate-y-2 text-sm font-bold leading-tight line-clamp-2 text-black">{title}</p>

        <div className="mt-3 min-h-[104px] translate-y-2 border-t border-gray-100 pt-3">
          {visibleFacts.length > 0 ? (
            <div className="space-y-1.5">
              {visibleFacts.map(([key, value]) => (
                <div key={key} className="flex flex-col gap-0.5">
                  <span className="text-[8px] font-black text-gray-400 uppercase tracking-widest">{key.replace(/_/g, ' ')}</span>
                  <p className="text-[11px] text-gray-600 line-clamp-1 font-medium">
                    {Array.isArray(value) ? value.join(', ') : String(value)}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex h-full items-center">
              <p className="text-[11px] font-medium text-gray-300">No extracted details</p>
            </div>
          )}
        </div>

        <div className="mt-auto pt-3 flex items-center gap-2">
          {item.url && item.url.startsWith('http') ? (
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="text-[10px] font-bold text-gray-400 hover:text-black flex items-center gap-1 transition-colors"
            >
              <Instagram className="w-3 h-3" /> View Source
            </a>
          ) : (
            <span className="text-[10px] font-bold text-gray-400 flex items-center gap-1">
              <Sparkles className="w-3 h-3" /> AI Curated
            </span>
          )}
        </div>
      </div>
    </motion.div>
  );
}
