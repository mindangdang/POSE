import { useEffect, useState, useRef } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { AnimatePresence, motion } from 'framer-motion';
import { ExternalLink, X, Sparkles, Loader2 } from 'lucide-react';

import { getItemTitle, parseItemFacts } from '../lib/itemFacts';
import type { SavedItem } from '../types/item';

type ItemDetailDialogProps = {
  item: SavedItem | null;
  onOpenChange: (open: boolean) => void;
};

export function ItemDetailDialog({ item, onOpenChange }: ItemDetailDialogProps) {
  const [viewedItem, setViewedItem] = useState<SavedItem | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [similarItems, setSimilarItems] = useState<any[]>([]);
  const [isLoadingSimilar, setIsLoadingSimilar] = useState(false);

  useEffect(() => {
    setViewedItem(item);
  }, [item]);

  const displayItem = viewedItem || item;

  useEffect(() => {
    if (displayItem) {
      let isMounted = true;
      setIsLoadingSimilar(true);
      setSimilarItems([]);
      
      if (scrollRef.current) {
        scrollRef.current.scrollTop = 0;
      }
      
      const token = localStorage.getItem('access_token');
      const facts = parseItemFacts(displayItem) as any;

      const fetchSimilarItems = async () => {
        try {
          let targetUrl = displayItem.image_url?.startsWith('http') || displayItem.image_url?.startsWith('data:') || displayItem.image_url?.startsWith('//') 
            ? displayItem.image_url 
            : facts?.local_image_url 
              ? `/api/images/${facts.local_image_url}`
              : displayItem.image_url 
                ? `/api/images/${displayItem.image_url}` 
                : '';
          
          if (targetUrl.startsWith('//')) {
            targetUrl = `https:${targetUrl}`;
          }

          const formData = new FormData();
          
          if (targetUrl.startsWith('/api/') || targetUrl.startsWith('data:')) {
            const response = await fetch(targetUrl);
            const blob = await response.blob();
            formData.append('image', blob, 'image.jpg');
          } else if (targetUrl) {
            formData.append('image_url', targetUrl);
          } else {
            const blob = new Blob([''], { type: 'image/jpeg' });
            formData.append('image', blob, 'image.jpg');
          }

          const res = await fetch('/api/multimodal', {
            method: 'POST',
            headers: { 
              ...(token ? { 'Authorization': `Bearer ${token}` } : {})
            },
            body: formData,
          });
          const data = await res.json();
          if (isMounted && data.success && data.results) {
            setSimilarItems(data.results);
          }
        } catch (err) {
          console.error('Failed to fetch similar items', err);
        } finally {
          if (isMounted) {
            setIsLoadingSimilar(false);
          }
        }
      };

      fetchSimilarItems();

      return () => {
        isMounted = false;
      };
    } else {
      setSimilarItems([]);
      setIsLoadingSimilar(false);
    }
  }, [displayItem]);

  if (!displayItem) {
    return null;
  }

  const facts = parseItemFacts(displayItem);
  const modalTitle = getItemTitle(displayItem);
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
                      displayItem.image_url?.startsWith('http') || 
                      displayItem.image_url?.startsWith('data:') || 
                      displayItem.image_url?.startsWith('//')
                        ? displayItem.image_url
                        : displayItem.image_url
                          ? `/api/images/${displayItem.image_url}`
                          : 'https://via.placeholder.com/600x600?text=No+Image'
                    }
                    alt={displayItem.category}
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
                        {displayItem.category}
                      </span>
                      <Dialog.Title asChild>
                        <h2 className="text-xl md:text-2xl font-bold text-foreground leading-tight">
                          {modalTitle}
                        </h2>
                      </Dialog.Title>
                      <Dialog.Description className="sr-only">
                        상세 정보
                      </Dialog.Description>
                    </div>
                    <Dialog.Close asChild>
                      <button className="p-2 hover:bg-muted rounded-full transition-colors shrink-0 text-muted-foreground hover:text-foreground">
                        <X className="w-5 h-5" />
                      </button>
                    </Dialog.Close>
                  </div>

                  <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-6 pr-2">
                    {/* Vibe Analysis */}
                    <section>
                      <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 flex items-center gap-2">
                        <Sparkles className="w-4 h-4 text-accent" /> Vibe Analysis
                      </h3>
                      <p className="text-sm font-medium leading-relaxed text-foreground">
                        {displayItem.recommend}
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
                    {displayItem.url && (
                      <section className="pt-2">
                        <a
                          href={displayItem.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center justify-center gap-2 w-full h-11 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
                        >
                          <ExternalLink className="w-4 h-4" />
                          원본 보기
                        </a>
                      </section>
                    )}

                    {/* Similar Items */}
                    <section className="pt-4 border-t border-border mt-6">
                      <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3 flex items-center gap-2">
                        <Sparkles className="w-4 h-4 text-accent" /> Similar Items
                      </h3>
                      {isLoadingSimilar ? (
                        <div className="flex justify-center py-8">
                          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                        </div>
                      ) : similarItems.length > 0 ? (
                        <div className="columns-2 gap-2 space-y-2">
                          {similarItems.map((similarItem, idx) => (
                            <div 
                              key={idx} 
                              className="break-inside-avoid relative group/similar rounded-lg overflow-hidden bg-muted cursor-pointer"
                              onClick={() => setViewedItem(similarItem as unknown as SavedItem)}
                            >
                              <img 
                                src={similarItem.image_url} 
                                className="w-full h-auto object-cover"
                                onError={(e) => {
                                  (e.target as HTMLImageElement).src = 'https://via.placeholder.com/150?text=No+Image';
                                }}
                              />
                              <div className="absolute inset-0 bg-black/40 opacity-0 group-hover/similar:opacity-100 transition-opacity p-2 flex flex-col justify-end">
                                <p className="text-[10px] text-white/80 mt-0.5">
                                  {typeof similarItem.facts?.Price === 'object'
                                    ? similarItem.facts.Price?.value || ''
                                    : similarItem.facts?.Price}
                                </p>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground">비슷한 아이템이 없습니다.</p>
                      )}
                    </section>
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
