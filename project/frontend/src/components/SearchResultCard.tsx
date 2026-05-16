import { motion } from 'framer-motion';
import { Plus, ThumbsUp, ThumbsDown } from 'lucide-react';

import { getItemTitle, parseItemFacts } from '../lib/itemFacts';
import type { SavedItem } from '../types/item';

type SearchResultCardProps = {
  item: SavedItem;
  delay: number;
  onClick: () => void;
  onSave: (e: React.MouseEvent<HTMLButtonElement>, item: SavedItem) => void | Promise<void>;
};

export function SearchResultCard({
  item,
  delay,
  onClick,
  onSave,
}: SearchResultCardProps) {
  const title = getItemTitle(item);
  const facts = parseItemFacts(item);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95, y: 10 }}
      transition={{ delay, duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      onClick={onClick}
      className="group cursor-pointer"
      whileHover={{ y: -4 }}
    >
      {/* Image Container */}
      <div className="relative aspect-square w-full bg-muted rounded-xl overflow-hidden mb-3">
        {item.image_url ? (
          <img
            src={item.image_url}
            alt={title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
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
          <div className="w-full h-full flex items-center justify-center text-muted-foreground text-xs font-bold">
            No Image
          </div>
        )}
        
        {/* Hover Overlay */}
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors duration-300" />
        
        {/* Save Button */}
        <button
          onClick={(e) => onSave(e, item)}
          className="absolute top-2 right-2 w-8 h-8 flex items-center justify-center bg-background/90 rounded-full opacity-0 group-hover:opacity-100 transition-all duration-200 hover:bg-primary hover:text-primary-foreground shadow-sm"
          aria-label="Save to feed"
        >
          <Plus className="w-4 h-4" />
        </button>

        {/* Like Button */}
        <button
          onClick={(e) => e.stopPropagation()}
          className="absolute bottom-2 left-2 w-8 h-8 flex items-center justify-center bg-background/90 rounded-full opacity-0 group-hover:opacity-100 transition-all duration-200 hover:bg-blue-50 hover:text-blue-600 shadow-sm"
          aria-label="Like item"
        >
          <ThumbsUp className="w-4 h-4" />
        </button>

        {/* Dislike Button */}
        <button
          onClick={(e) => e.stopPropagation()}
          className="absolute bottom-2 left-11 w-8 h-8 flex items-center justify-center bg-background/90 rounded-full opacity-0 group-hover:opacity-100 transition-all duration-200 hover:bg-red-50 hover:text-red-600 shadow-sm"
          aria-label="Dislike item"
        >
          <ThumbsDown className="w-4 h-4" />
        </button>
      </div>

      {/* Content */}
      <div className="space-y-1">
        {item.category && (
          <span className="text-xs font-medium text-accent uppercase tracking-wide">
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
