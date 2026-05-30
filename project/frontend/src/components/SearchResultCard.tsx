import { motion } from 'framer-motion';
import { Plus, ThumbsUp, ThumbsDown, Search } from 'lucide-react';

import { getItemTitle, parseItemFacts } from '../lib/itemFacts';
import type { SavedItem } from '../types/item';

type SearchResultCardProps = {
  item: SavedItem;
  delay: number;
  onClick: () => void;
  onSave: (e: React.MouseEvent<HTMLButtonElement>, item: SavedItem) => void | Promise<void>;
  onSearchSecondhand?: (title: string) => void;
};

// Generate random aspect ratios for Pinterest-style masonry
const aspectRatios = [
  'aspect-[3/4]',
  'aspect-[4/5]',
  'aspect-square',
  'aspect-[2/3]',
  'aspect-[5/6]',
];

function getAspectRatio(id: string | number): string {
  const hash = String(id).split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  return aspectRatios[hash % aspectRatios.length];
}

export function SearchResultCard({
  item,
  delay,
  onClick,
  onSave,
  onSearchSecondhand,
}: SearchResultCardProps) {
  const title = getItemTitle(item);
  const facts = parseItemFacts(item);
  const aspectRatio = getAspectRatio(item.id);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 10 }}
      transition={{ delay, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      onClick={onClick}
      className="masonry-item group cursor-pointer"
    >
      {/* Image Container */}
      <div className={`relative w-full ${aspectRatio} bg-muted rounded-2xl overflow-hidden`}>
        {item.image_url ? (
          <img
            src={item.image_url}
            alt={title}
            className="w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-700 ease-out"
            referrerPolicy="no-referrer"
            onError={(e) => {
              const target = e.target as HTMLImageElement;
              const localUrl = facts?.local_image_url as string | undefined;
              if (localUrl && !target.src.includes(localUrl)) {
                target.src = `/api/images/${localUrl}`;
              } else {
                target.src = 'https://via.placeholder.com/400x400?text=No+Image';
              }
            }}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-muted-foreground text-xs font-medium">
            No Image
          </div>
        )}
        
        {/* Gradient Overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/0 to-black/0 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        
        {/* Action Buttons - Top */}
        <div className="absolute top-3 right-3 flex gap-2 opacity-0 group-hover:opacity-100 transition-all duration-200">
          <button
            onClick={(e) => onSave(e, item)}
            className="w-9 h-9 flex items-center justify-center bg-white rounded-full shadow-lg hover:scale-105 transition-transform"
            aria-label="Save to feed"
          >
            <Plus className="w-4 h-4 text-foreground" />
          </button>
        </div>

        {/* Action Buttons - Bottom */}
        <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between opacity-0 group-hover:opacity-100 transition-all duration-200">
          <div className="flex gap-2">
            <button
              onClick={(e) => e.stopPropagation()}
              className="w-8 h-8 flex items-center justify-center bg-white/90 backdrop-blur-sm rounded-full shadow-md hover:bg-white transition-colors"
              aria-label="Like item"
            >
              <ThumbsUp className="w-3.5 h-3.5 text-foreground" />
            </button>
            <button
              onClick={(e) => e.stopPropagation()}
              className="w-8 h-8 flex items-center justify-center bg-white/90 backdrop-blur-sm rounded-full shadow-md hover:bg-white transition-colors"
              aria-label="Dislike item"
            >
              <ThumbsDown className="w-3.5 h-3.5 text-foreground" />
            </button>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onSearchSecondhand?.(title);
            }}
            className="h-8 px-3 flex items-center gap-1.5 bg-white/90 backdrop-blur-sm rounded-full shadow-md text-xs font-medium text-foreground hover:bg-white transition-colors"
            aria-label="Search secondhand"
          >
            <Search className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">중고</span>
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="mt-3 space-y-1 px-1">
        {item.category && (
          <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
            {item.category}
          </span>
        )}
        <h3 className="text-sm font-medium text-foreground line-clamp-2 leading-snug">
          {title}
        </h3>
      </div>
    </motion.div>
  );
}
