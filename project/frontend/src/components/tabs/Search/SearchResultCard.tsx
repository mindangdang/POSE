import { motion } from 'framer-motion';
import { Plus, ThumbsUp, ThumbsDown, Search, ExternalLink } from 'lucide-react';
import { useState } from 'react';

import { getItemTitle, parseItemInforms } from '../../../lib/iteminform';
import type { SavedItem } from '../../../types/item';

type SearchResultCardProps = {
  item: SavedItem;
  delay: number;
  onClick: () => void;
  onSave: (e: React.MouseEvent<HTMLButtonElement>, item: SavedItem) => void | Promise<void>;
  onSearchSecondhand?: (title: string) => void;
  onLike?: (item: SavedItem) => void;
  onDislike?: (item: SavedItem) => void;
};

export function SearchResultCard({
  item,
  delay,
  onClick,
  onSave,
  onSearchSecondhand,
  onLike,
  onDislike,
}: SearchResultCardProps) {
  const title = getItemTitle(item);
  const facts = parseItemInforms(item);
  const aspectRatio = 'aspect-[2/3]';
  const [liked, setLiked] = useState(false);
  const [disliked, setDisliked] = useState(false);

  const handleLike = (e: React.MouseEvent) => {
    e.stopPropagation();
    setLiked(!liked);
    if (disliked) setDisliked(false);
    onLike?.(item);
  };

  const handleDislike = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDisliked(!disliked);
    if (liked) setLiked(false);
    onDislike?.(item);
  };

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
      <div className={`relative w-full ${aspectRatio} bg-muted rounded-2xl sm:rounded-3xl overflow-hidden`}>
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
              } else if (!target.src.includes('placehold.co')) {
                target.src = 'https://placehold.co/400x600?text=No+Image';
              } else {
                target.src = ''; // 더 이상 시도하지 않음
              }
            }}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-muted-foreground text-xs font-bold">
            No Image
          </div>
        )}
        
        {/* Gradient Overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/0 to-black/0 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        
        {/* Save Button - Top Right */}
        <div className="absolute top-2 sm:top-3 right-2 sm:right-3 flex gap-2 opacity-0 group-hover:opacity-100 transition-all duration-200">
          <button
            onClick={(e) => onSave(e, item)}
            className="w-8 h-8 sm:w-9 sm:h-9 flex items-center justify-center bg-white rounded-full shadow-lg hover:scale-105 transition-transform"
            aria-label="Save to feed"
          >
            <Plus className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-foreground" />
          </button>
        </div>

        {/* Like/Dislike and Search - Bottom */}
        <div className="absolute bottom-2 sm:bottom-3 left-2 sm:left-3 right-2 sm:right-3 flex items-center justify-between opacity-0 group-hover:opacity-100 transition-all duration-200">
          <button
            onClick={handleLike}
            className={`w-8 h-8 sm:w-9 sm:h-9 flex items-center justify-center rounded-full shadow-md transition-all ${
              liked 
                ? 'bg-black text-white scale-110' 
                : 'bg-white/90 backdrop-blur-sm text-foreground hover:bg-white'
            }`}
            aria-label="Like item"
          >
            <ThumbsUp className={`w-3.5 h-3.5 sm:w-4 sm:h-4 ${liked ? 'fill-current' : ''}`} />
          </button>
          <button
            onClick={handleDislike}
            className={`w-8 h-8 sm:w-9 sm:h-9 flex items-center justify-center rounded-full shadow-md transition-all ${
              disliked 
                ? 'bg-red-500 text-white scale-110' 
                : 'bg-white/90 backdrop-blur-sm text-foreground hover:bg-white'
            }`}
            aria-label="Dislike item"
          >
            <ThumbsDown className={`w-3.5 h-3.5 sm:w-4 sm:h-4 ${disliked ? 'fill-current' : ''}`} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="mt-2 sm:mt-3 space-y-0.5 sm:space-y-1 px-1">
        {item.category && (
          <span className="text-[9px] sm:text-[10px] font-semibold text-black uppercase tracking-wider">
            {item.category}
          </span>
        )}
        <h3 className="text-xs sm:text-sm font-bold text-foreground line-clamp-2 leading-snug">
          {title}
        </h3>

        {/* Source and Secondhand */}
        <div className="pt-1 flex flex-col gap-1 sm:gap-1.5">
          {item.image_url && item.image_url.startsWith('http') && (
            <a
              href={item.image_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="inline-flex items-center gap-1 sm:gap-1.5 text-[10px] sm:text-xs text-muted-foreground hover:text-black transition-colors w-fit"
            >
              <ExternalLink className="w-2.5 h-2.5 sm:w-3 sm:h-3" /> View Source
            </a>
          )}

          <button
            onClick={(e) => {
              e.stopPropagation();
              onSearchSecondhand?.(title);
            }}
            className="inline-flex items-center gap-1 sm:gap-1.5 text-[10px] sm:text-xs text-muted-foreground hover:text-black transition-colors w-fit uppercase tracking-tight font-bold"
          >
            <Search className="w-2.5 h-2.5 sm:w-3 sm:h-3" /> Search Secondhand
          </button>
        </div>
      </div>
    </motion.div>
  );
}
