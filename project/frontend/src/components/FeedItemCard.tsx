import { motion } from 'framer-motion';
import { Instagram, Sparkles, Trash2, Search } from 'lucide-react';

import { getItemTitle, parseItemFacts } from '../lib/itemFacts';
import type { SavedItem } from '../types/item';

type FeedItemCardProps = {
  item: SavedItem;
  factKeysToShow: string[];
  onDelete: (id: number) => void | Promise<void>;
  onSelect: () => void;
  onSearchSecondhand?: (title: string) => void;
};

// Generate random aspect ratios for masonry-style grid
const aspectRatios = [
  'aspect-[3/4]',
  'aspect-[4/5]',
  'aspect-square',
  'aspect-[2/3]',
];

function getAspectRatio(id: number): string {
  return aspectRatios[id % aspectRatios.length];
}

export function FeedItemCard({
  item,
  factKeysToShow,
  onDelete,
  onSelect,
  onSearchSecondhand,
}: FeedItemCardProps) {
  const facts = parseItemFacts(item);
  const title = getItemTitle(item);
  const isProcessingItem =
    item.category.trim().toUpperCase() === 'PROCESSING' ||
    item.sub_category.trim().toUpperCase() === 'PROCESSING' ||
    facts?._source === 'feed_add';
  const categoryLabel = `${item.category}${item.sub_category ? ` / ${item.sub_category}` : ''}`;
  const visibleFacts = facts
    ? Object.entries(facts).filter(
        ([key]) => key.toLowerCase() !== 'title' && factKeysToShow.includes(key.toLowerCase())
      )
    : [];

  const aspectRatio = getAspectRatio(item.id);

  return (
    <motion.div
      layout
      onClick={onSelect}
      className="group cursor-pointer"
      whileHover={{ y: -4 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
    >
      {/* Image Container */}
      <div className={`relative ${aspectRatio} overflow-hidden rounded-2xl bg-muted`}>
        <img
          src={item.image_url?.startsWith('http') || item.image_url?.startsWith('data:') || item.image_url?.startsWith('//') ? item.image_url : item.image_url ? `/api/images/${item.image_url}` : 'https://via.placeholder.com/400x400?text=No+Image'}
          alt={item.category}
          className="h-full w-full object-cover transition-transform duration-700 ease-out group-hover:scale-[1.02]"
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
        
        {/* Gradient Overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/50 via-black/0 to-black/0 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        
        {/* Delete Button */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete(item.id);
          }}
          className="absolute top-3 right-3 w-9 h-9 flex items-center justify-center bg-white rounded-full opacity-0 group-hover:opacity-100 transition-all duration-200 shadow-lg hover:scale-105"
          aria-label="Delete item"
        >
          <Trash2 className="w-4 h-4 text-red-500" />
        </button>

        {/* Secondhand Search Button */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onSearchSecondhand?.(title);
          }}
          className="absolute bottom-3 left-3 right-3 h-9 flex items-center justify-center gap-2 bg-white/90 backdrop-blur-sm rounded-full opacity-0 group-hover:opacity-100 transition-all duration-200 shadow-md text-xs font-medium text-foreground hover:bg-white"
        >
          <Search className="w-3.5 h-3.5" />
          Find Secondhand
        </button>
      </div>

      {/* Content */}
      <div className="mt-3 space-y-1.5 px-1">
        {/* Category */}
        {!isProcessingItem && (
          <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
            {categoryLabel}
          </span>
        )}
        
        {/* Title */}
        <h3 className="text-sm font-medium text-foreground line-clamp-2 leading-snug">
          {title}
        </h3>

        {/* Facts */}
        {visibleFacts.length > 0 && (
          <div className="pt-1 space-y-1">
            {visibleFacts.slice(0, 2).map(([key, value]) => (
              <p key={key} className="text-xs text-muted-foreground line-clamp-1">
                {Array.isArray(value) ? value.join(', ') : String(value)}
              </p>
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
              className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <Instagram className="w-3 h-3" /> View Source
            </a>
          ) : (
            <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
              <Sparkles className="w-3 h-3" /> AI Curated
            </span>
          )}
        </div>
      </div>
    </motion.div>
  );
}
