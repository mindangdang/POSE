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
      className="group cursor-pointer"
      whileHover={{ y: -4 }}
      transition={{ duration: 0.2 }}
    >
      {/* Image Container */}
      <div className="relative aspect-square overflow-hidden rounded-xl bg-muted mb-3">
        <img
          src={item.image_url?.startsWith('http') || item.image_url?.startsWith('data:') || item.image_url?.startsWith('//') ? item.image_url : item.image_url ? `/api/images/${item.image_url}` : 'https://via.placeholder.com/400x400?text=No+Image'}
          alt={item.category}
          className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
          referrerPolicy="no-referrer"
          onError={(e) => {
            const target = e.target as HTMLImageElement;
            const localUrl = facts?.local_image_url as string | undefined;
            if (localUrl && !target.src.includes(localUrl)) {
              target.src = `/api/images/${localUrl}`;
            } else {
              target.src = 'https://via.placeholder.com/400x400?text=POSE';
            }
          }}
        />
        
        {/* Hover Overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        
        {/* Delete Button */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete(item.id);
          }}
          className="absolute top-2 right-2 w-8 h-8 flex items-center justify-center bg-background/90 rounded-full opacity-0 group-hover:opacity-100 transition-all duration-200 hover:bg-red-50 shadow-sm"
          aria-label="Delete item"
        >
          <Trash2 className="w-4 h-4 text-red-500" />
        </button>
      </div>

      {/* Content */}
      <div className="space-y-1.5">
        {/* Category */}
        {!isProcessingItem && (
          <span className="text-xs font-medium text-accent uppercase tracking-wide">
            {categoryLabel}
          </span>
        )}
        
        {/* Title */}
        <h3 className="text-sm font-medium text-foreground line-clamp-2 leading-snug">
          {title}
        </h3>

        {/* Facts */}
        {visibleFacts.length > 0 && (
          <div className="pt-2 space-y-1">
            {visibleFacts.slice(0, 2).map(([key, value]) => (
              <div key={key} className="flex flex-col">
                <span className="text-xs text-muted-foreground uppercase tracking-wide">
                  {key.replace(/_/g, ' ')}
                </span>
                <p className="text-xs font-medium text-foreground line-clamp-1">
                  {Array.isArray(value) ? value.join(', ') : String(value)}
                </p>
              </div>
            ))}
          </div>
        )}

        {/* Source */}
        <div className="pt-2">
          {item.url && item.url.startsWith('http') ? (
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <Instagram className="w-3 h-3" /> View Source
            </a>
          ) : (
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <Sparkles className="w-3 h-3" /> AI Curated
            </span>
          )}
        </div>
      </div>
    </motion.div>
  );
}
