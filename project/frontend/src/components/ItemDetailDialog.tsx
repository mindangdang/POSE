import * as Dialog from '@radix-ui/react-dialog';
import { AnimatePresence, motion } from 'framer-motion';
import { Instagram, X, Zap } from 'lucide-react';

import type { SavedItem } from '../App';

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
  return (
    <Dialog.Root open={!!item} onOpenChange={onOpenChange}>
      <AnimatePresence>
        {item && (
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
                        item.image_url?.startsWith('http')
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
                    <div className="flex items-center justify-between mb-8">
                      <span className="text-[10px] font-black uppercase tracking-widest text-white bg-black px-3 py-1.5 rounded-lg">
                        {item.category}
                      </span>
                      <Dialog.Close asChild>
                        <button className="p-2 hover:bg-gray-100 rounded-full transition-colors">
                          <X className="w-6 h-6" />
                        </button>
                      </Dialog.Close>
                    </div>

                    <div className="flex-1 overflow-y-auto space-y-8 pr-4 custom-scrollbar">
                      <section>
                        <h3 className="text-xs font-black text-gray-400 uppercase tracking-widest mb-3 flex items-center gap-2">
                          <Zap className="w-4 h-4 text-yellow-400" fill="currentColor" /> Vibe Analysis
                        </h3>
                        <p className="text-lg font-bold leading-relaxed text-black tracking-tight">{item.vibe}</p>
                      </section>

                      <section>
                        <h3 className="text-xs font-black text-gray-400 uppercase tracking-widest mb-4">Extracted Information</h3>
                        <div className="grid grid-cols-1 gap-4">
                          {(() => {
                            const facts = parseFacts(item);

                            return facts && typeof facts === 'object' ? (
                              Object.entries(facts).map(([key, value]) => (
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
                            );
                          })()}
                        </div>
                      </section>

                      <section className="border-t border-gray-100 pt-8">
                        <h3 className="text-xs font-black text-gray-400 uppercase tracking-widest mb-4">Review Insights</h3>
                        {(() => {
                          const facts = parseFacts(item);
                          const reviewData = item.reviews || facts;

                          return (reviewData?.star_review || reviewData?.core_summary || reviewData?.review) ? (
                            <div className="bg-gradient-to-tr from-yellow-50 to-orange-50 p-6 rounded-3xl border border-yellow-100/50">
                              <div className="flex items-center gap-2 mb-3">
                                <span className="text-sm font-black text-yellow-600 uppercase tracking-tight">
                                  {reviewData.star_review || "Recommended"}
                                </span>
                                <div className="flex text-yellow-400">
                                  {"★".repeat(Math.min(5, Math.floor(parseFloat(reviewData.star_review) || 5)))}
                                </div>
                              </div>
                              <p className="text-sm font-bold leading-relaxed text-gray-800 tracking-tight">
                                "{reviewData.core_summary || reviewData.review || "No summary available"}"
                              </p>
                            </div>
                          ) : (
                            <p className="text-sm text-gray-400 font-medium">No review data extracted for this item.</p>
                          );
                        })()}
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
        )}
      </AnimatePresence>
    </Dialog.Root>
  );
}
