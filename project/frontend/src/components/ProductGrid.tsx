import { motion } from 'framer-motion';
import { Heart, Plus } from 'lucide-react';
import { getItemTitle, parseItemFacts } from '../lib/itemFacts';
import type { SavedItem } from '../types/item';

type ProductGridProps = {
  title: string;
  label?: string;
  items: SavedItem[];
  onSelectItem: (item: SavedItem) => void;
  onSaveItem?: (item: SavedItem) => void;
  onDeleteItem?: (id: number) => void;
  showSaveButton?: boolean;
};

export function ProductGrid({
  title,
  label,
  items,
  onSelectItem,
  onSaveItem,
  onDeleteItem,
  showSaveButton = false,
}: ProductGridProps) {
  if (items.length === 0) {
    return null;
  }

  return (
    <section className="py-8 md:py-12">
      <div className="max-w-[1400px] mx-auto px-4 lg:px-8">
        {/* Section Header */}
        <div className="mb-6">
          {label && (
            <span className="text-accent text-xs font-bold tracking-widest uppercase">
              {label}
            </span>
          )}
          <h2 className="text-2xl md:text-3xl font-bold text-foreground mt-1">
            {title}
          </h2>
        </div>

        {/* Product Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {items.map((item) => (
            <ProductCard
              key={item.id}
              item={item}
              onSelect={() => onSelectItem(item)}
              onSave={onSaveItem ? () => onSaveItem(item) : undefined}
              onDelete={onDeleteItem ? () => onDeleteItem(item.id) : undefined}
              showSaveButton={showSaveButton}
            />
          ))}
        </div>
      </div>
    </section>
  );
}

type ProductCardProps = {
  item: SavedItem;
  onSelect: () => void;
  onSave?: () => void;
  onDelete?: () => void;
  showSaveButton?: boolean;
};

function ProductCard({ item, onSelect, onSave, onDelete, showSaveButton }: ProductCardProps) {
  const title = getItemTitle(item);
  const facts = parseItemFacts(item);
  const priceInfo = facts?.price_info;
  const priceText =
    typeof priceInfo === 'string' || typeof priceInfo === 'number'
      ? String(priceInfo)
      : undefined;

  const handleSave = (e: React.MouseEvent) => {
    e.stopPropagation();
    onSave?.();
  };

  return (
    <motion.div
      layout
      onClick={onSelect}
      className="group cursor-pointer"
      whileHover={{ y: -4 }}
      transition={{ duration: 0.2 }}
    >
      {/* Image Container */}
      <div className="relative aspect-square bg-muted rounded-lg overflow-hidden mb-3">
        <img
          src={
            item.image_url?.startsWith('http') ||
            item.image_url?.startsWith('data:') ||
            item.image_url?.startsWith('//')
              ? item.image_url
              : item.image_url
              ? `/api/images/${item.image_url}`
              : 'https://via.placeholder.com/400x400?text=No+Image'
          }
          alt={title || item.category}
          className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
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
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors duration-300" />

        {/* Action Buttons */}
        {showSaveButton && onSave && (
          <button
            onClick={handleSave}
            className="absolute top-2 right-2 w-8 h-8 flex items-center justify-center bg-background/90 rounded-full opacity-0 group-hover:opacity-100 transition-all duration-200 hover:bg-background shadow-sm"
            aria-label="Save to feed"
          >
            <Plus className="w-4 h-4 text-foreground" />
          </button>
        )}

        {onDelete && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            className="absolute top-2 right-2 w-8 h-8 flex items-center justify-center bg-background/90 rounded-full opacity-0 group-hover:opacity-100 transition-all duration-200 hover:bg-red-50 shadow-sm"
            aria-label="Remove item"
          >
            <Heart className="w-4 h-4 text-red-500" fill="currentColor" />
          </button>
        )}
      </div>

      {/* Product Info */}
      <div className="space-y-1">
        {item.category && (
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            {item.category}
          </span>
        )}
        <h3 className="text-sm font-medium text-foreground line-clamp-2 leading-snug">
          {title || 'Untitled Item'}
        </h3>
        {priceText && (
          <p className="text-sm font-bold text-foreground">
            {priceText}
          </p>
        )}
      </div>
    </motion.div>
  );
}
