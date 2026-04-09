import { motion } from 'framer-motion';
import { Trash2, Instagram, Sparkles } from 'lucide-react';

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
  return (
    <motion.div
      layout
      onClick={onSelect}
      className="break-inside-avoid group relative bg-white rounded-3xl overflow-hidden border border-black/5 hover:shadow-2xl hover:-translate-y-1 transition-all duration-300 cursor-pointer"
    >
      <div className="relative overflow-hidden">
        <img
          src={item.image_url?.startsWith('http') || item.image_url?.startsWith('data:') || item.image_url?.startsWith('//') ? item.image_url : item.image_url ? `/api/images/${item.image_url}` : 'https://via.placeholder.com/400x500?text=No+Image'}
          alt={item.category}
          className="w-full h-auto object-cover transform group-hover:scale-105 transition-transform duration-700"
          referrerPolicy="no-referrer"
          onError={(e) => {
            (e.target as HTMLImageElement).src = 'https://via.placeholder.com/400x500?text=POSE+Not+Found';
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
      </div>
      <div className="p-4 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[9px] font-black uppercase tracking-widest text-blue-600 bg-blue-50 px-2 py-1 rounded-md">
            {item.category}
          </span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete(item.id);
            }}
            className="opacity-0 group-hover:opacity-100 p-1.5 bg-red-50 text-red-500 rounded-full hover:bg-red-100 transition-all"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
        <p className="text-sm font-bold leading-tight line-clamp-2 text-black">{item.vibe}</p>

        {item.facts && typeof item.facts === 'object' && (
          <>
            {Object.entries(item.facts).filter(([key]) => factKeysToShow.includes(key.toLowerCase())).length > 0 && (
              <div className="space-y-1.5 mt-3 border-t border-gray-100 pt-3">
                {Object.entries(item.facts)
                  .filter(([key]) => factKeysToShow.includes(key.toLowerCase()))
                  .map(([key, value]) => (
                    <div key={key} className="flex flex-col gap-0.5">
                      <span className="text-[8px] font-black text-gray-400 uppercase tracking-widest">{key.replace(/_/g, ' ')}</span>
                      <p className="text-[11px] text-gray-600 line-clamp-1 font-medium">
                        {Array.isArray(value) ? value.join(', ') : String(value)}
                      </p>
                    </div>
                  ))}
              </div>
            )}
          </>
        )}

        <div className="pt-3 flex items-center gap-2">
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
