import { AnimatePresence, motion } from 'framer-motion';
import { X } from 'lucide-react';
import React, { useState } from 'react';

type Shop = {
  name: string;
  url: string;
  desc: string;
};

type AddShopModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onAddShop: (newShop: Shop) => void;
};

export function AddShopModal({ isOpen, onClose, onAddShop }: AddShopModalProps) {
  const [newShopData, setNewShopData] = useState({ name: "", url: "", desc: "" });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newShopData.name || !newShopData.url) return;

    const formattedUrl = newShopData.url.startsWith('http')
      ? newShopData.url
      : `https://${newShopData.url}`;
    const newShop = { ...newShopData, url: formattedUrl };
    onAddShop(newShop);
    setNewShopData({ name: "", url: "", desc: "" });
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="fixed left-1/2 top-1/2 z-[101] w-full max-w-md -translate-x-1/2 -translate-y-1/2 p-4"
          >
            <div className="rounded-3xl border border-border bg-background p-6 shadow-2xl sm:p-8">
              <div className="mb-6 flex items-center justify-between">
                <h3 className="text-xl font-bold tracking-tight text-foreground">새 사이트 추가</h3>
                <button onClick={onClose} className="rounded-full p-2 hover:bg-muted transition-colors">
                  <X className="h-5 w-5 text-muted-foreground" />
                </button>
              </div>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">사이트명</label>
                  <input
                    required
                    type="text"
                    placeholder="예: POSE SELECT"
                    value={newShopData.name}
                    onChange={(e) => setNewShopData(prev => ({ ...prev, name: e.target.value }))}
                    className="w-full rounded-xl border border-border bg-muted/50 px-4 py-3 text-sm font-medium focus:border-black focus:outline-none transition-colors"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">URL</label>
                  <input
                    required
                    type="text"
                    placeholder="https://..."
                    value={newShopData.url}
                    onChange={(e) => setNewShopData(prev => ({ ...prev, url: e.target.value }))}
                    className="w-full rounded-xl border border-border bg-muted/50 px-4 py-3 text-sm font-medium focus:border-black focus:outline-none transition-colors"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">설명 (선택)</label>
                  <input
                    type="text"
                    placeholder="간단한 사이트 설명을 적어주세요"
                    value={newShopData.desc}
                    onChange={(e) => setNewShopData(prev => ({ ...prev, desc: e.target.value }))}
                    className="w-full rounded-xl border border-border bg-muted/50 px-4 py-3 text-sm font-medium focus:border-black focus:outline-none transition-colors"
                  />
                </div>
                <button
                  type="submit"
                  className="mt-4 w-full rounded-full bg-black py-4 text-sm font-bold tracking-widest text-white transition-opacity hover:opacity-90 uppercase"
                >
                  추가 완료
                </button>
              </form>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}