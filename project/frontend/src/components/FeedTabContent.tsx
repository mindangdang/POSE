import { useMutation } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'framer-motion';
import { Plus, Loader2, Zap, Folder, ArrowLeft, Grid3X3, Clock3, Package } from 'lucide-react';
import { useEffect, useMemo, useRef, useState, type FormEvent, type WheelEvent } from 'react';

import { parseItemFacts } from '../lib/itemFacts';
import type { SavedItem } from '../types/item';
import type { AppUser } from '../types/user';
import { FeedItemCard } from './FeedItemCard';

type FeedTabContentProps = {
  items: SavedItem[];
  onItemsChange: React.Dispatch<React.SetStateAction<SavedItem[]>>;
  onSelectItem: (item: SavedItem) => void;
  refreshItems: () => Promise<void>;
  refreshTaste: () => Promise<void>;
  user: AppUser | null;
};

const feedQuotes = [
  '"Buy less, choose well, make it last."',
  '"You can find inspiration in everything If you can\'t, then you\'re not looking properly"',
  '"Fashion should be a from of escapism, and not a from of imprisonment."',
  '"I always find beauty in things that are odd and imperfect, they are much more interesting."',
  '"To be noticed without striving to be noticed, this is what elegance is about."',
  '"Simplicity is the ultimate sophistication."',
  '"Don\'t be afraid to fail. Be afraid not to try."',
];

export function FeedTabContent({
  items,
  onItemsChange,
  onSelectItem,
  refreshItems,
  refreshTaste,
  user,
}: FeedTabContentProps) {
  const [newUrl, setNewUrl] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [currentFolder, setCurrentFolder] = useState<string | null>(null);
  const [isAddPanelOpen, setIsAddPanelOpen] = useState(false);
  const [quoteIndex, setQuoteIndex] = useState(0);
  const menuWheelDelta = useRef(0);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setQuoteIndex((currentIndex) => (currentIndex + 1) % feedQuotes.length);
    }, 10000);

    return () => window.clearInterval(intervalId);
  }, []);

  const factKeysToShow = ['title', 'price_info', 'location_text', 'time_info', 'key_details'];
  const isFeedAddItem = (item: SavedItem) => parseItemFacts(item)?._source === 'feed_add';
  const menuItems = useMemo(() => items.filter((item) => !isFeedAddItem(item)), [items]);
  const categories = useMemo(
    () => {
      const itemCategories = Array.from(new Set(menuItems.map((item) => item.category))).filter(Boolean);
      const visibleCategories = itemCategories.filter((category) => category.trim().toUpperCase() !== 'PROCESSING');

      return ['All', ...visibleCategories, 'PROCESSING'];
    },
    [menuItems]
  );
  const filteredItems = useMemo(
    () => (
      selectedCategory === 'All'
        ? items
        : menuItems.filter((item) => item.category === selectedCategory)
    ),
    [items, menuItems, selectedCategory]
  );
  const shouldGroupItems = selectedCategory.toUpperCase() === 'PRODUCT';

  const folders = useMemo(() => {
    if (!shouldGroupItems) return [];

    const subs = new Set<string>();
    filteredItems.forEach((item) => {
      if (item.sub_category) subs.add(item.sub_category);
    });
    return Array.from(subs);
  }, [filteredItems, shouldGroupItems]);

  const itemsToDisplay = useMemo(() => {
    if (!shouldGroupItems) return filteredItems;
    if (currentFolder) return filteredItems.filter((item) => item.sub_category === currentFolder);
    return filteredItems.filter((item) => !item.sub_category);
  }, [filteredItems, currentFolder, shouldGroupItems]);

  const addItemMutation = useMutation({
    mutationFn: async ({ nextUrl, nextSessionId, userId }: { nextUrl: string; nextSessionId: string; userId: number }) => {
      const res = await fetch('/api/extract-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: nextUrl, session_id: nextSessionId, user_id: userId })
      });

      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || "Failed to analyze URL");
      }

      return {
        nextUrl,
        data: await res.json(),
      };
    },
    onSuccess: ({ nextUrl, data }) => {
      if (data.success && data.status === 'processing') {
        alert(`✨ ${data.message}`);
      } else if (data.success && data.data && Array.isArray(data.data)) {
        const newItems = data.data.map((item: any, index: number) => ({
          id: Date.now() + index,
          url: nextUrl,
          category: item.category || 'General',
          sub_category: item.sub_category || '',
          facts: { ...(typeof item.facts === 'object' && item.facts ? item.facts : {}), _source: 'feed_add' },
          recommend: item.recommend || 'Extracted',
          image_url: item.image_url || '',
          created_at: new Date().toISOString(),
          summary_text: item.summary_text || ''
        }));
        onItemsChange((prev) => [...newItems, ...prev]);
      }

      setNewUrl("");
      setSessionId("");

      window.setTimeout(() => {
        void refreshItems();
        void refreshTaste();
      }, 3000);
    },
    onError: (error: Error) => {
      console.error(error);
      alert(`분석 요청 중 오류가 발생했습니다: ${error.message}`);
    },
  });

  const deleteItemMutation = useMutation({
    mutationFn: async ({ id, userId }: { id: number; userId: number }) => {
      const res = await fetch(`/api/items/${id}?user_id=${userId}`, { method: 'DELETE' });

      if (!res.ok) {
        throw new Error('Failed to delete item');
      }

      return id;
    },
    onMutate: async ({ id }) => {
      const previousItems = items;
      onItemsChange((currentItems) => currentItems.filter((item) => item.id !== id));
      return { previousItems };
    },
    onError: (error, _variables, context) => {
      console.error('Delete failed:', error);
      if (context?.previousItems) {
        onItemsChange(context.previousItems);
      }
      alert('삭제 중 오류가 발생했습니다.');
    },
  });

  const handleAddItem = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!newUrl || !user) return;
    await addItemMutation.mutateAsync({
      nextSessionId: sessionId,
      nextUrl: newUrl,
      userId: user.id,
    });
  };

  const handleDelete = async (id: number) => {
    if (!user) return;
    const shouldDelete = window.confirm('정말로 삭제하시겠습니까?');
    if (!shouldDelete) return;
    await deleteItemMutation.mutateAsync({ id, userId: user.id });
  };

  const getCategoryIcon = (category: string) => {
    const normalizedCategory = category.toUpperCase();
    if (normalizedCategory === 'ALL') return Grid3X3;
    if (normalizedCategory === 'PROCESSING') return Clock3;
    if (normalizedCategory === 'PRODUCT') return Folder;
    return Folder;
  };

  const getCategoryLabel = (category: string) => {
    if (category.toUpperCase() === 'ALL') return 'All';
    return category.charAt(0).toUpperCase() + category.slice(1).toLowerCase();
  };

  const handleCategoryWheel = (event: WheelEvent<HTMLElement>) => {
    if (categories.length < 2) return;

    event.preventDefault();

    menuWheelDelta.current += event.deltaY;

    const wheelStep = 80;
    const steps = Math.trunc(Math.abs(menuWheelDelta.current) / wheelStep);
    if (steps === 0) return;

    const currentIndex = Math.max(0, categories.indexOf(selectedCategory));
    const direction = menuWheelDelta.current > 0 ? 1 : -1;
    const nextIndex = Math.max(0, Math.min(categories.length - 1, currentIndex + direction * steps));

    menuWheelDelta.current = nextIndex === 0 || nextIndex === categories.length - 1
      ? 0
      : menuWheelDelta.current % wheelStep;
    setSelectedCategory(categories[nextIndex]);
    setCurrentFolder(null);
  };

  return (
    <motion.div
      key="feed"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex h-full min-h-0 flex-col"
    >
      <header className="shrink-0">
        <div>
          <h2 className="text-4xl justify-center flex font-black tracking-tighter"><Zap fill='black'></Zap></h2>
          <AnimatePresence mode="wait">
            <motion.p
              key={quoteIndex}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.35, ease: 'easeOut' }}
              className="mx-auto mt-1 flex max-w-3xl justify-center text-center text-gray-500 font-medium"
            >
              {feedQuotes[quoteIndex]}
            </motion.p>
          </AnimatePresence>
        </div>
      </header>

      <div className="feed-scroll-area mt-8 min-h-0 flex-1 overflow-y-auto overflow-x-hidden pr-10">
        <AnimatePresence mode="wait">
          <motion.div
            key={`${selectedCategory}-${currentFolder ?? 'root'}`}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
            className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4 items-stretch"
          >
            {shouldGroupItems && currentFolder && (
              <div className="col-span-full mb-2 flex items-center gap-4">
                <button
                  onClick={() => setCurrentFolder(null)}
                  className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-full text-xs font-black uppercase tracking-widest transition-colors"
                >
                  <ArrowLeft className="w-4 h-4" /> Back
                </button>
                <h3 className="text-xl font-black uppercase tracking-tight text-gray-800">{currentFolder}</h3>
              </div>
            )}

            {shouldGroupItems && !currentFolder &&
              folders.map((folder) => (
                <motion.div
                  layout
                  key={`folder-${folder}`}
                  onClick={() => setCurrentFolder(folder)}
                  className="group relative flex aspect-[4/4.6] flex-col items-center justify-center overflow-hidden rounded-3xl border border-black/5 bg-gray-50 transition-all duration-300 cursor-pointer hover:-translate-y-1 hover:shadow-xl"
                >
                  <Folder className="w-12 h-12 text-gray-300 group-hover:text-black transition-colors mb-3" fill="currentColor" />
                  <h3 className="text-sm font-black text-gray-600 group-hover:text-black uppercase tracking-widest text-center px-4 line-clamp-2">
                    {folder}
                  </h3>
                  <p className="text-[10px] font-bold text-gray-400 mt-2 bg-white px-3 py-1 rounded-full shadow-sm">
                    {filteredItems.filter((i) => i.sub_category === folder).length} ITEMS
                  </p>
                </motion.div>
              ))}

            {itemsToDisplay.map((item) => (
              <FeedItemCard
                key={item.id}
                factKeysToShow={factKeysToShow}
                item={item}
                onDelete={handleDelete}
                onSelect={() => onSelectItem(item)}
              />
            ))}
          </motion.div>
        </AnimatePresence>

        {items.length === 0 && !addItemMutation.isPending && (
          <div className="text-center py-32 bg-gray-50 rounded-[3rem] border-2 border-dashed border-gray-200">
            <div className="w-20 h-20 bg-white rounded-full flex items-center justify-center mx-auto mb-6 shadow-sm">
              <Zap className="w-10 h-10 text-yellow-400" fill="currentColor" />
            </div>
            <h3 className="text-2xl font-black tracking-tight mb-2">Strike your first POSE!</h3>
            <p className="text-gray-500 font-medium">인스타그램 링크를 넣고 나만의 바이브를 수집하세요.</p>
          </div>
        )}
      </div>

      {items.length > 0 && (
        <nav
          className="fixed right-40 bottom-70 md:right-48 top-1/2 z-30 flex -translate-y-1/2 flex-col items-stretch gap-18"
          aria-label="Feed category filters"
          onWheel={handleCategoryWheel}
        >
          {categories.map((category) => {
            const Icon = getCategoryIcon(category);
            const label = getCategoryLabel(category);
            const isSelected = selectedCategory === category;

            return (
              <button
                key={category}
                type="button"
                title={category}
                aria-label={`Show ${category} feed items`}
                aria-pressed={isSelected}
                onClick={() => {
                  setSelectedCategory(category);
                  setCurrentFolder(null);
                }}
                className={[
                  "flex h-10 min-w-28 items-center gap-2 px-3 text-sm font-bold normal-case transition-colors",
                  isSelected
                    ? "text-black"
                    : "text-gray-300 hover:text-gray-600",
                ].join(' ')}
              >
                <Icon className="h-6 w-6" />
                <span>{label}</span>
              </button>
            );
          })}
          <button
            type="button"
            aria-label="Open add form"
            aria-expanded={isAddPanelOpen}
            onClick={() => setIsAddPanelOpen(true)}
            className="mt-35 ml-3.5 left-10 flex p-2 w-25 cursor-pointer rounded-4xl justify-center items-center gap-2 px-3 text-sm font-bg-gray-700 transition-colors hover:text-gray-400"
          >
            <Plus className="h-10 w-10" strokeWidth={1}/>
          </button>
        </nav>
      )}

      <AnimatePresence>
        {isAddPanelOpen && (
          <>
            <motion.div
              key="add-overlay"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 bg-black/40"
              onClick={() => setIsAddPanelOpen(false)}
            />
            <motion.div
              key="add-popup"
              initial={{ opacity: 0, scale: 0.96, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 12 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
              className="fixed inset-0 z-50 flex items-center justify-center p-4"
            >
              <div className="w-[min(calc(100vw-3rem),24rem)] rounded-[1.75rem] border border-gray-100 bg-white px-4 pb-4 pt-2 shadow-xl">
                <div className="flex h-8 items-center justify-end">
                  <button
                    type="button"
                    aria-label="Close add form"
                    onClick={() => setIsAddPanelOpen(false)}
                    className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-full text-gray-500 transition-colors hover:text-black"
                  >
                    <Plus className="h-4.5 w-4.5 rotate-45" />
                  </button>
                </div>

                <form onSubmit={handleAddItem} className="mt-1 space-y-3">
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-medium uppercase tracking-widest text-gray-400">URL 또는 제품명</label>
                    <input
                      type="url"
                      placeholder="URL"
                      value={newUrl}
                      onChange={(e) => setNewUrl(e.target.value)}
                      className="w-full rounded-2xl border-none outline-none bg-gray-50 px-4 py-2.5 text-sm font-medium transition-all"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-medium uppercase tracking-widest text-gray-400">세션 ID</label>
                    <input
                      type="password"
                      placeholder="Session ID"
                      value={sessionId}
                      onChange={(e) => setSessionId(e.target.value)}
                      className="w-full rounded-2xl border-none outline-none bg-gray-50 px-4 py-2.5 text-sm font-medium transition-all"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={addItemMutation.isPending || !newUrl}
                    className="flex h-11 w-full items-center justify-center gap-2 rounded-2xl bg-black px-6 text-sm font-black tracking-widest text-white transition-all hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {addItemMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                    ADD
                  </button>
                </form>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
