import { motion, AnimatePresence } from 'framer-motion';
import { Plus, ExternalLink, X } from 'lucide-react';
import React from 'react';

type Shop = {
  name: string;
  url: string;
  desc: string;
};

type ShopSelectorProps = {
  shops: Shop[];
  selectedShopNames: Set<string>;
  setSelectedShopNames: React.Dispatch<React.SetStateAction<Set<string>>>;
  onOpenAddShopModal: () => void;
  displayActivity: boolean;
};

export function ShopSelector({
  shops,
  selectedShopNames,
  setSelectedShopNames,
  onOpenAddShopModal,
  displayActivity,
}: ShopSelectorProps) {
  if (displayActivity) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      className="w-full max-w-3xl mx-auto space-y-4 pt-8"
    >
      <div className="flex items-center gap-2 px-1">
        <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground/60">Curated Shop Guide</span>
        <button
          onClick={onOpenAddShopModal}
          className="ml-2 flex items-center gap-1 px-2 py-0.5 rounded-full border border-border bg-white text-[9px] font-bold uppercase tracking-wider text-muted-foreground hover:text-black hover:border-black transition-all"
        >
          <Plus className="w-2.5 h-2.5" />
          Add Shop
        </button>
        <div className="h-px flex-1 bg-border/50" />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
        {shops.map((shop: Shop) => (
          <div
            key={`${shop.name}-${shop.url}`}
            className="flex items-center justify-between p-3.5 rounded-xl border border-border/60 bg-white/40 backdrop-blur-sm hover:bg-white transition-all group shadow-sm"
          >
            <div className="flex flex-col gap-0.5 min-w-0">
              <span className="text-[11px] font-bold text-foreground">{shop.name}</span>
              <span className="text-[9px] text-muted-foreground truncate">{shop.desc}</span>
            </div>
            <div className="flex items-center gap-3 ml-2 shrink-0">
              <label className="flex items-center gap-2 cursor-pointer group/cb">
                <input
                  type="checkbox"
                  checked={selectedShopNames.has(shop.name)}
                  onChange={() => {
                    setSelectedShopNames(prev => {
                      const next = new Set(prev);
                      if (next.has(shop.name)) next.delete(shop.name);
                      else next.add(shop.name);
                      return next;
                    });
                  }}
                  className="w-4 h-4 rounded border-border text-black focus:ring-black cursor-pointer"
                />
                <span className="text-[10px] font-bold text-muted-foreground group-hover/cb:text-black transition-colors uppercase tracking-tight">선택</span>
              </label>
              <a
                href={shop.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center w-7 h-7 rounded-full bg-muted group-hover:bg-black group-hover:text-white transition-colors"
                title={`${shop.name} 이동하기`}
              >
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>
        ))}
      </div>
    </motion.div>
  );
}