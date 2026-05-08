import * as Dialog from '@radix-ui/react-dialog';
import { AnimatePresence, motion } from 'framer-motion';
import { ExternalLink, X, Sparkles } from 'lucide-react';

import { getItemTitle, parseItemFacts } from '../lib/itemFacts';
import type { SavedItem } from '../types/item';

type ItemDetailDialogProps = {
  item: SavedItem | null;
  onOpenChange: (open: boolean) => void;
};

export function ItemDetailDialog({ item, onOpenChange }: ItemDetailDialogProps) {
  if (!item) {
    return null;
  }

  const facts = parseItemFacts(item);
  const modalTitle = getItemTitle(item);
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
              className="fixed inset-0 z-50 bg-foreground/60 backdrop-blur-sm"
            />
          </Dialog.Overlay>

          <Dialog.Content asChild>
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="fixed inset-0 z-50 flex items-center justify-center p-4 outline-none"
            >
              <div className="bg-background w-full max-w-3xl rounded-2xl overflow-hidden shadow-2xl flex flex-col md:flex-row max-h-[90vh] border border-border">
                {/* Image Section */}
                <div className="md:w-1/2 bg-muted flex items-center justify-center overflow-hidden p-6">
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
                    className="w-full h-full object-contain rounded-xl"
                    referrerPolicy="no-referrer"
                    onError={(e) => {
                      const target = e.target as HTMLImageElement;
                      const localUrl = (facts as Record<string, any>)?.local_image_url as string | undefined;
                      if (localUrl && !target.src.includes(localUrl)) {
                        target.src = `/api/images/${localUrl}`;
                      } else {
                        target.src = 'https://via.placeholder.com/600x600?text=No+Image';
                      }
                    }}
                  />
                </div>

                {/* Content Section */}
                <div className="md:w-1/2 p-6 md:p-8 flex flex-col bg-background">
                  <div className="flex items-start justify-between mb-6 gap-4 border-b border-border pb-4 shrink-0">
                    <div className="space-y-2">
                      <span className="inline-block text-xs font-medium uppercase tracking-wide text-accent">
                        {item.category}
                      </span>
                      <h2 className="text-xl md:text-2xl font-bold text-foreground leading-tight">
                        {modalTitle}
                      </h2>
                    </div>
                    <Dialog.Close asChild>
                      <button className="p-2 hover:bg-muted rounded-full transition-colors shrink-0 text-muted-foreground hover:text-foreground">
                        <X className="w-5 h-5" />
                      </button>
                    </Dialog.Close>
                  </div>

                  <div className="flex-1 overflow-y-auto space-y-6 pr-2">
                    {/* Vibe Analysis */}
                    <section>
                      <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 flex items-center gap-2">
                        <Sparkles className="w-4 h-4 text-accent" /> Vibe Analysis
                      </h3>
                      <p className="text-sm font-medium leading-relaxed text-foreground">
                        {item.recommend}
                      </p>
                    </section>

                    {/* Extracted Information */}
                    <section>
                      <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">
                        Extracted Information
                      </h3>
                      <div className="grid grid-cols-1 gap-3">
                        {factEntries.length > 0 ? (
                          factEntries.map(([key, value]) => (
                            <div key={key} className="bg-muted p-3 rounded-xl">
                              <dt className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">
                                {key.replace(/_/g, ' ')}
                              </dt>
                              <dd className="text-sm font-medium text-foreground">
                                {Array.isArray(value) ? (
                                  <div className="flex flex-wrap gap-1.5">
                                    {value.map((val, index) => (
                                      <span key={index} className="px-2 py-0.5 bg-background border border-border rounded text-xs font-medium">
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
                          <p className="text-sm text-muted-foreground">No detailed facts available.</p>
                        )}
                      </div>
                    </section>

                    {/* Source Link */}
                    {item.url && (
                      <section className="pt-2">
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center justify-center gap-2 w-full h-11 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
                        >
                          <ExternalLink className="w-4 h-4" />
                          원본 보기
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
