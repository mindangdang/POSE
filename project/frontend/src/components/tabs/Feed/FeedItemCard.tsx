import { motion } from 'framer-motion';
import { Instagram, Sparkles, Trash2, Search, ThumbsUp, ThumbsDown } from 'lucide-react';
import { useState } from 'react';

import { getItemTitle, parseItemInforms } from '../../../lib/iteminform';
import type { SavedItem } from '../../../types/item';

type FeedItemCardProps = {
  item: SavedItem;
  onDelete: (id: number) => void | Promise<void>;
  onSelect: () => void;
  onSearchSecondhand?: (title: string) => void;
  onLike?: (item: SavedItem) => void;
  onDislike?: (item: SavedItem) => void;
};

export function FeedItemCard({
  item,
  onDelete,
  onSelect,
  onSearchSecondhand,
  onLike,
  onDislike,
}: FeedItemCardProps) {
  const informs = parseItemInforms(item);
  const informsList = Object.entries(informs).filter(
    ([key, value]) =>
      value != null &&
      value !== '' &&
      !['item_id', 'title', 'category', 'source_url', '_source'].includes(key)
  );
  const title = getItemTitle(item);
  const isProcessingItem = item.category.trim().toUpperCase() === 'PROCESSING' || informs._source === 'feed_add';
  const categoryLabel = `${item.category}${item.category ? ` / ${item.category}` : ''}`;
  const aspectRatio = 'aspect-[2/3]';
  const [liked, setLiked] = useState(false);
  const [disliked, setDisliked] = useState(false);
  const fallbackImage = 'https://placehold.co/400x400?text=No+Image';

  /// TODO: hooks로 옮기기
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
      layout
      onClick={onSelect}
      className="group cursor-pointer"
      whileHover={{ y: -4 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
    >
      {/* Image Container */}
      <div className={`relative ${aspectRatio} overflow-hidden rounded-2xl sm:rounded-3xl bg-muted`}>
        <img
          src={item.image_url?.startsWith('http') || item.image_url?.startsWith('data:') || item.image_url?.startsWith('//') ? item.image_url : item.image_url ? `/api/images/${item.image_url}` : 'https://via.placeholder.com/400x400?text=No+Image'}
          alt={item.category}
          className="h-full w-full object-cover transition-transform duration-700 ease-out group-hover:scale-[1.02]"
          referrerPolicy="no-referrer"
          onError={(e) => {
            const target = e.target as HTMLImageElement;
            const localUrl = item?.image_url as string | undefined;
            if (localUrl && !target.src.includes(localUrl)) {
              target.src = `/api/images/${localUrl}`;
            } else {
              target.src = 'https://via.placeholder.com/400x400?text=PoSe';
            }
          }}
        />
        
        {/* Gradient Overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/50 via-black/0 to-black/0 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        
        {/* Delete Button - Top Right */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete(item.item_id);
          }}
          className="absolute top-2 sm:top-3 right-2 sm:right-3 w-8 h-8 sm:w-9 sm:h-9 flex items-center justify-center bg-white rounded-full opacity-0 group-hover:opacity-100 transition-all duration-200 shadow-lg hover:scale-105"
          aria-label="Delete item"
        >
          <Trash2 className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-red-500" />
        </button>

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
      <div className="mt-2 sm:mt-3 space-y-1 sm:space-y-1.5 px-1">
        {/* Category */}
        {!isProcessingItem && (
          <span className="text-[9px] sm:text-[10px] font-semibold text-black uppercase tracking-widest">
            {categoryLabel}
          </span>
        )}
        
        {/* Title */}
        <h3 className="text-xs sm:text-sm font-medium text-foreground line-clamp-2 leading-snug">
          {title}
        </h3>

        {/* Informs */}
        {informsList.length > 0 && (
          <div className="pt-1 space-y-0.5 sm:space-y-1">
            {informsList.slice(0, 2).map(([key, value]) => (
              <p key={key} className="text-[10px] sm:text-xs text-muted-foreground line-clamp-1">
                {Array.isArray(value) ? value.join(', ') : String(value)}
              </p>
            ))}
          </div>
        )}

        {/* Source */}
        <div className="pt-1 sm:pt-2 flex flex-col gap-1 sm:gap-1.5">
          {item.source_url && item.source_url.startsWith('http') && (
            <a
              href={item.source_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="inline-flex items-center gap-1 sm:gap-1.5 text-[10px] sm:text-xs text-muted-foreground hover:text-black transition-colors"
            >
              <Instagram className="w-2.5 h-2.5 sm:w-3 sm:h-3" /> View Source
            </a>
          )}

          <button
            onClick={(e) => {
              e.stopPropagation();
              onSearchSecondhand?.(title);
            }}
            className="inline-flex items-center gap-1 sm:gap-1.5 text-[10px] sm:text-xs text-muted-foreground hover:text-black transition-colors w-fit"
          >
            <Search className="w-2.5 h-2.5 sm:w-3 sm:h-3" /> Search Secondhand
          </button>
        </div>
      </div>
    </motion.div>
  );
}
