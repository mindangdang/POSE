import { motion } from 'framer-motion';

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
  const factsObj = typeof item.facts === 'string' ? JSON.parse(item.facts) : item.facts;
  const title = factsObj?.title || item.summary_text || '제목 없음';

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.3 }}
      onClick={onClick}
      className="group bg-white rounded-3xl overflow-hidden shadow-sm hover:shadow-xl transition-all duration-300 cursor-pointer border border-gray-100 flex flex-col h-full"
    >
      <div className="aspect-square w-full bg-gray-100 overflow-hidden relative">
        {item.image_url ? (
          <img
            src={item.image_url}
            alt={title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
            referrerPolicy="no-referrer"
            onError={(e) => {
              (e.target as HTMLImageElement).src = 'https://via.placeholder.com/400x400?text=No+Image';
            }}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-gray-400 text-xs font-bold bg-gray-50">
            No Image
          </div>
        )}
        <div className="absolute top-3 left-3">
          <span className="inline-block text-[10px] font-black uppercase tracking-widest text-white bg-black/80 backdrop-blur-md px-2.5 py-1 rounded-lg">
            {item.category}
          </span>
        </div>
      </div>

      <div className="p-5 flex flex-col flex-1">
        <h3 className="font-bold text-black text-sm line-clamp-2 mb-2 leading-snug">
          {title}
        </h3>
        <p className="text-xs text-gray-500 line-clamp-2 mb-4">
          {item.summary_text}
        </p>
        <div className="mt-auto">
          <button
            onClick={(e) => onSave(e, item)}
            className="w-full py-2.5 bg-gray-50 hover:bg-black hover:text-white text-black rounded-xl text-xs font-black uppercase tracking-widest transition-colors flex items-center justify-center gap-2"
          >
            + 피드에 저장
          </button>
        </div>
      </div>
    </motion.div>
  );
}
