import * as Dialog from '@radix-ui/react-dialog';
import { AnimatePresence, motion } from 'framer-motion';
import { Instagram, X, Zap } from 'lucide-react';

import type { SavedItem } from '../types/item';

type ItemDetailDialogProps = {
  item: SavedItem | null;
  onOpenChange: (open: boolean) => void;
};

function parseFacts(item: SavedItem) {
  if (!item.facts) return null;
  if (typeof item.facts === 'string') {
    try {
      return JSON.parse(item.facts);
    } catch {
      return null;
    }
  }
  return item.facts;
}

export function ItemDetailDialog({ item, onOpenChange }: ItemDetailDialogProps) {
  if (!item) {
    return null;
  }

  const facts = parseFacts(item);
  const modalTitle =
    (facts && typeof facts === 'object' && 'title' in facts && typeof facts.title === 'string' && facts.title) ||
    (facts && typeof facts === 'object' && 'Title' in facts && typeof facts.Title === 'string' && facts.Title) ||
    item.summary_text ||
    item.recommend;
  const factEntries =
    facts && typeof facts === 'object'
      ? Object.entries(facts).filter(([key]) => key.toLowerCase() !== 'title')
      : [];

  return (
    <Dialog.Root open onOpenChange={onOpenChange}>
      <AnimatePresence>
        <Dialog.Portal forceMount>
          <Dialog.Overlay asChild>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md"
            />
          </Dialog.Overlay>

          <Dialog.Content asChild>
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="fixed inset-0 z-50 flex items-center justify-center p-4 outline-none"
            >
              <div className="bg-white w-full max-w-4xl rounded-[3rem] overflow-hidden shadow-2xl flex flex-col md:flex-row max-h-[90vh] border border-white/20">
                <div className="md:w-1/2 bg-gray-50 flex items-center justify-center overflow-hidden p-8">
                  <img
                    src={
                      item.image_url?.startsWith('http') || 
                      item.image_url?.startsWith('data:') || 
                      item.image_url?.startsWith('//')
                        ? item.image_url
                        : item.image_url
                          ? `/api/images/${item.image_url}`
                          : 'https://via.placeholder.com/600x600?text=No+Image'
                    }
                    alt={item.category}
                    className="w-full h-full object-contain rounded-2xl shadow-sm"
                    referrerPolicy="no-referrer"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src = 'https://via.placeholder.com/600x600?text=No+Image';
                    }}
                  />
                </div>

                <div className="md:w-1/2 p-8 md:p-10 flex flex-col bg-white">
                  <div className="flex items-start justify-between mb-8 gap-4 border-b border-gray-100 pb-6 shrink-0">
                    <div className="space-y-3">
                      <span className="inline-block text-[10px] font-black uppercase tracking-widest text-white bg-black px-3 py-1.5 rounded-lg">
                        {item.category}
                      </span>
                      <h2 className="text-2xl md:text-3xl font-black text-black tracking-tight leading-tight break-keep">
                        {modalTitle}
                      </h2>
                    </div>
                    <Dialog.Close asChild>
                      <button className="p-2 hover:bg-gray-100 rounded-full transition-colors shrink-0">
                        <X className="w-6 h-6" />
                      </button>
                    </Dialog.Close>
                  </div>

                  <div className="flex-1 overflow-y-auto space-y-8 pr-4 custom-scrollbar">
                    <section>
                      <h3 className="text-xs font-black text-gray-400 uppercase tracking-widest mb-3 flex items-center gap-2">
                        <Zap className="w-4 h-4 text-yellow-400" fill="currentColor" /> Vibe Analysis
                      </h3>
                      <p className="text-lg font-bold leading-relaxed text-black tracking-tight">{item.recommend}</p>
                    </section>

                    <section>
                      <h3 className="text-xs font-black text-gray-400 uppercase tracking-widest mb-4">Extracted Information</h3>
                      <div className="grid grid-cols-1 gap-4">
                        {factEntries.length > 0 ? (
                          factEntries.map(([key, value]) => (
                            <div key={key} className="group/fact bg-gray-50 p-4 rounded-2xl border border-gray-100">
                              <dt className="text-[9px] font-black text-gray-400 uppercase tracking-widest mb-2">
                                {key.replace(/_/g, ' ')}
                              </dt>
                              <dd className="text-sm font-medium text-black">
                                {Array.isArray(value) ? (
                                  <div className="flex flex-wrap gap-2">
                                    {value.map((val, index) => (
                                      <span key={index} className="px-3 py-1 bg-white border border-gray-200 rounded-lg text-xs font-bold shadow-sm">
                                        {String(val)}
                                      </span>
                                    ))}
                                  </div>
                                ) : (
                                  <span>{String(value)}</span>
                                )}
                              </dd>
                            </div>
                          ))
                        ) : (
                          <p className="text-sm text-gray-400 font-medium">No detailed facts available.</p>
                        )}
                      </div>
                    </section>

                    {item.url && (
                      <section className="pt-4">
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center justify-center gap-2 w-full py-4 bg-gray-100 hover:bg-gray-200 text-black rounded-2xl text-xs font-black uppercase tracking-widest transition-colors"
                        >
                          <Instagram className="w-4 h-4" />
                          Open Original Post
                        </a>
                      </section>
                    )}
                  </div>
                </div>
              </div>
            </motion.div>
          </Dialog.Content>
        </Dialog.Portal>
      </AnimatePresence>
    </Dialog.Root>
  );
}
