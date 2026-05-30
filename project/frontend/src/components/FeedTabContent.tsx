import { useMutation } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'framer-motion';
import { Plus, Loader2, Folder, Grid3X3, Clock3, X, Check, Search } from 'lucide-react';
import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';

import { parseItemFacts } from '../lib/itemFacts';
import type { SavedItem } from '../types/item';
import type { AppUser } from '../types/user';
import { FeedItemCard } from './FeedItemCard';

type FeedTabContentProps = {
  items: SavedItem[];
  onItemsChange: React.Dispatch<React.SetStateAction<SavedItem[]>>;
  onSelectItem: (item: SavedItem) => void;
  onSearchSecondhand?: (title: string) => void;
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
  onSearchSecondhand,
  refreshItems,
  refreshTaste,
  user,
}: FeedTabContentProps) {
  const [newUrl, setNewUrl] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>('PRODUCT');
  const [currentFolder, setCurrentFolder] = useState<string | null>(null);
  const [isAddPanelOpen, setIsAddPanelOpen] = useState(false);
  const [isAddButtonSuccess, setIsAddButtonSuccess] = useState(false);
  const [quoteIndex, setQuoteIndex] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const addSuccessTimeout = useRef<number | null>(null);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setQuoteIndex((currentIndex) => (currentIndex + 1) % feedQuotes.length);
    }, 10000);

    return () => window.clearInterval(intervalId);
  }, []);

  useEffect(() => {
    return () => {
      if (addSuccessTimeout.current) {
        window.clearTimeout(addSuccessTimeout.current);
      }
    };
  }, []);

  const factKeysToShow = ['title', 'price_info', 'time_info', 'key_details'];
  const isFeedAddItem = (item: SavedItem) => parseItemFacts(item)?._source === 'feed_add';
  const menuItems = useMemo(() => items.filter((item) => !isFeedAddItem(item)), [items]);
  const categories = useMemo(() => {
    const dynamicCategories = Array.from(new Set(menuItems.map((item) => item.category))).filter(Boolean) as string[];
    const others = dynamicCategories.filter(c => c.toUpperCase() !== 'PRODUCT' && c.toUpperCase() !== 'ALL');
    return ['PRODUCT', 'All', ...others];
  }, [menuItems]);
  const filteredItems = useMemo(
    () => (
      selectedCategory === 'All'
        ? items
        : items.filter((item) => item.category === selectedCategory)
    ),
    [items, selectedCategory]
  );

  const folders = useMemo(() => {
    const subs = new Set<string>();
    filteredItems.forEach((item) => {
      if (item.sub_category) subs.add(item.sub_category);
    });
    return Array.from(subs);
  }, [filteredItems]);

  const itemsToDisplay = useMemo(() => {
    let baseItems = [];
    if (selectedCategory === 'All') {
      baseItems = filteredItems;
    } else if (currentFolder) {
      baseItems = filteredItems.filter((item) => item.sub_category === currentFolder);
    } else {
      baseItems = filteredItems.filter((item) => !item.sub_category);
    }

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      return baseItems.filter((item) => {
        const facts = parseItemFacts(item) || {};
        const title = typeof facts.title === 'string' ? facts.title.toLowerCase() : '';
        const category = (item.category || '').toLowerCase();
        const subCategory = (item.sub_category || '').toLowerCase();
        const recommend = (item.recommend || '').toLowerCase();
        const factValues = Object.values(facts).map(v => String(v).toLowerCase()).join(' ');

        return title.includes(query) || category.includes(query) || subCategory.includes(query) || recommend.includes(query) || factValues.includes(query);
      });
    }

    return baseItems;
  }, [filteredItems, currentFolder, selectedCategory, searchQuery]);

  useEffect(() => {
    if (!categories.includes(selectedCategory) && categories.length > 0) {
      setSelectedCategory('PRODUCT');
      setCurrentFolder(null);
    }
  }, [categories, selectedCategory]);

  useEffect(() => {
    if (!user) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws/${user.id}`;
    let ws: WebSocket;

    try {
      ws = new WebSocket(wsUrl);

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === "CRAWL_SUCCESS") {
            onItemsChange((prev) => {
              const filtered = prev.filter(item => item.id !== data.placeholder_id);
              return [...(data.items || []), ...filtered];
            });
            setCurrentFolder((prev) => prev === 'PROCESSING' ? null : prev);
            void refreshTaste();
          } else if (data.type === "CRAWL_ERROR") {
            alert(data.message || "데이터를 가져오는 데 실패했습니다. 잠시 후 다시 시도해주세요.");
            onItemsChange((prev) => prev.filter(item => item.id !== data.placeholder_id));
          }
        } catch (err) {
          console.error("웹소켓 메시지 파싱 오류:", err);
        }
      };
    } catch (err) {
      console.error("웹소켓 연결 에러:", err);
    }

    return () => {
      if (ws) ws.close();
    };
  }, [user, onItemsChange, refreshTaste]);

  const addItemMutation = useMutation({
    mutationFn: async ({ nextUrl, nextSessionId, userId }: { nextUrl: string; nextSessionId: string; userId: string | number }) => {
      const token = localStorage.getItem('access_token');
      const res = await fetch('/api/extract-url', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
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
    onSuccess: ({ data }) => {
      if (data.success && Array.isArray(data.data) && data.data.length > 0) {
        onItemsChange((prev) => [...data.data, ...prev]);
      }
      setNewUrl("");
      setSessionId("");
    },
    onError: (error: Error) => {
      console.error(error);
      alert(`분석 요청 중 오류가 발생했습니다: ${error.message}`);
    },
  });

  const deleteItemMutation = useMutation({
    mutationFn: async ({ id, userId }: { id: number; userId: string | number }) => {
      const token = localStorage.getItem('access_token');
      const res = await fetch(`/api/items/${id}?user_id=${userId}`, { 
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });

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
    return Folder;
  };

  const getCategoryLabel = (category: string) => {
    if (category.toUpperCase() === 'ALL') return 'All';
    return category.charAt(0).toUpperCase() + category.slice(1).toLowerCase();
  };

  return (
    <motion.div
      key="feed"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex flex-col min-h-[calc(100vh-200px)]"
    >
      {/* Header Section */}
      <header className="mb-6 sm:mb-10">
        <div className="flex items-start justify-between mb-4 sm:mb-6">
          <div>
            <span className="text-[9px] sm:text-[10px] font-semibold text-primary tracking-[0.15em] sm:tracking-[0.2em] uppercase">my collection</span>
            <h1 className="editorial-heading text-2xl sm:text-3xl md:text-4xl lg:text-5xl text-foreground mt-1 sm:mt-2">
              your
              <br />
              <span className="text-primary">feed</span>
            </h1>
          </div>
          <button
            onClick={() => setIsAddPanelOpen(true)}
            className="flex items-center gap-1.5 sm:gap-2 h-9 sm:h-11 px-4 sm:px-5 bg-primary text-primary-foreground rounded-full text-xs sm:text-sm font-medium hover:opacity-90 transition-opacity"
          >
            <Plus className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
            <span className="hidden sm:inline">Add Item</span>
            <span className="sm:hidden">Add</span>
          </button>
        </div>

        {/* Quote */}
        <AnimatePresence mode="wait">
          <motion.p
            key={quoteIndex}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.35, ease: 'easeOut' }}
            className="text-xs sm:text-sm text-muted-foreground font-medium italic max-w-lg"
          >
            {feedQuotes[quoteIndex]}
          </motion.p>
        </AnimatePresence>
      </header>

      {/* Category Tabs and Search */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 sm:gap-4 mb-6 sm:mb-8 pb-4 sm:pb-6 border-b border-border">
        <nav className="flex items-center gap-1.5 sm:gap-2 overflow-x-auto pb-2 md:pb-0 category-nav">
          {categories.map((category) => {
            const Icon = getCategoryIcon(category);
            const label = getCategoryLabel(category);
            const isSelected = selectedCategory === category;

            return (
              <button
                key={category}
                onClick={() => {
                  setSelectedCategory(category);
                  setCurrentFolder(null);
                }}
                className={`flex items-center gap-1.5 sm:gap-2 h-8 sm:h-10 px-3 sm:px-5 rounded-full text-xs sm:text-sm font-medium whitespace-nowrap transition-all ${
                  isSelected
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-transparent text-muted-foreground hover:text-foreground border border-border hover:border-primary/30'
                }`}
              >
                <Icon className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                {label}
              </button>
            );
          })}
        </nav>

        <div className="relative w-full md:w-64 lg:w-72 shrink-0">
          <Search className="absolute left-3 sm:left-4 top-1/2 -translate-y-1/2 w-3.5 h-3.5 sm:w-4 sm:h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search in feed..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full h-9 sm:h-10 pl-9 sm:pl-11 pr-4 rounded-full bg-muted text-xs sm:text-sm font-medium focus:outline-none focus:ring-2 focus:ring-primary/20 transition-shadow placeholder:text-muted-foreground"
          />
        </div>
      </div>

      {/* Items Grid */}
      <div className="flex-1">
        <AnimatePresence mode="wait">
          <motion.div
            key={`${selectedCategory}-${currentFolder ?? 'root'}`}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
            className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4"
          >
            {/* Current Folder Header */}
            {currentFolder && (
              <div className="col-span-full mb-4 flex items-center gap-4 border-b border-border pb-3">
                <h3 className="text-lg font-bold text-foreground">{currentFolder}</h3>
                <button
                  onClick={() => setCurrentFolder(null)}
                  className="ml-auto flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                >
                  <X className="w-4 h-4" />
                  닫기
                </button>
              </div>
            )}

            {/* Folder Cards */}
            {!currentFolder && selectedCategory !== 'All' &&
              folders.map((folder) => (
                <motion.div
                  layout
                  key={`folder-${folder}`}
                  onClick={() => setCurrentFolder(folder)}
                  className="group relative flex aspect-square flex-col items-start justify-end p-4 overflow-hidden rounded-xl border border-border bg-muted transition-all duration-300 cursor-pointer hover:border-foreground/20 hover:shadow-lg"
                >
                  <Folder className="absolute top-4 right-4 w-6 h-6 text-muted-foreground" />
                  <h3 className="text-sm font-bold text-foreground line-clamp-2">
                    {folder}
                  </h3>
                  <p className="text-xs text-muted-foreground mt-1">
                    {filteredItems.filter((i) => i.sub_category === folder).length} items
                  </p>
                </motion.div>
              ))}

            {/* Item Cards */}
            {itemsToDisplay.map((item) => (
              <FeedItemCard
                key={item.id}
                factKeysToShow={factKeysToShow}
                item={item}
                onDelete={handleDelete}
                onSelect={() => onSelectItem(item)}
                onSearchSecondhand={onSearchSecondhand}
              />
            ))}
          </motion.div>
        </AnimatePresence>

        {/* Empty State */}
        {items.length === 0 && !addItemMutation.isPending && (
          <div className="flex flex-col items-center justify-center py-16 sm:py-24 text-center px-4">
            <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-full bg-muted flex items-center justify-center mb-4 sm:mb-6">
              <Plus className="w-6 h-6 sm:w-8 sm:h-8 text-muted-foreground" />
            </div>
            <h3 className="editorial-heading text-xl sm:text-2xl md:text-3xl text-foreground mb-2 sm:mb-3">start your collection</h3>
            <p className="text-muted-foreground font-medium mb-6 sm:mb-8 max-w-sm text-xs sm:text-sm">
              Add items to build your personal mood board.
              <br />
              Curate your unique aesthetic.
            </p>
            <button
              onClick={() => setIsAddPanelOpen(true)}
              className="flex items-center gap-2 h-10 sm:h-12 px-5 sm:px-6 bg-primary text-primary-foreground rounded-full text-xs sm:text-sm font-medium hover:opacity-90 transition-opacity"
            >
              <Plus className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              Add First Item
            </button>
          </div>
        )}

        {/* Empty State for Search */}
        {items.length > 0 && itemsToDisplay.length === 0 && searchQuery.trim() !== '' && (
          <div className="flex flex-col items-center justify-center py-16 sm:py-24 text-center">
            <h3 className="editorial-heading text-xl sm:text-2xl text-foreground mb-2 sm:mb-3">no results</h3>
            <p className="text-muted-foreground font-medium text-xs sm:text-sm">
              No items match your search criteria.
            </p>
          </div>
        )}
      </div>

      {/* Add Item Modal */}
      <AnimatePresence>
        {isAddPanelOpen && (
          <>
            <motion.div
              key="add-overlay"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
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
              <div className="w-full max-w-md rounded-2xl sm:rounded-3xl bg-background p-6 sm:p-8 shadow-2xl border border-border">
                <div className="flex items-center justify-between mb-6 sm:mb-8">
                  <h3 className="editorial-heading text-xl sm:text-2xl text-foreground">add item</h3>
                  <button
                    onClick={() => setIsAddPanelOpen(false)}
                    className="w-8 h-8 sm:w-9 sm:h-9 flex items-center justify-center rounded-full text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                  >
                    <X className="w-4 h-4 sm:w-5 sm:h-5" />
                  </button>
                </div>

                <form onSubmit={handleAddItem} className="space-y-4 sm:space-y-5">
                  <div>
                    <label className="block text-[10px] sm:text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5 sm:mb-2">
                      URL or Product Name
                    </label>
                    <input
                      type="url"
                      placeholder="https://..."
                      value={newUrl}
                      onChange={(e) => setNewUrl(e.target.value)}
                      className="w-full h-10 sm:h-12 px-3 sm:px-4 bg-muted rounded-xl text-xs sm:text-sm font-medium placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] sm:text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5 sm:mb-2">
                      Session ID (Optional)
                    </label>
                    <input
                      type="password"
                      placeholder="Session ID"
                      value={sessionId}
                      onChange={(e) => setSessionId(e.target.value)}
                      className="w-full h-10 sm:h-12 px-3 sm:px-4 bg-muted rounded-xl text-xs sm:text-sm font-medium placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={addItemMutation.isPending || (!newUrl && !isAddButtonSuccess)}
                    className={`w-full h-10 sm:h-12 flex items-center justify-center rounded-full text-xs sm:text-sm font-semibold transition-all ${
                      isAddButtonSuccess
                        ? 'bg-green-600 text-white'
                        : 'bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50'
                    }`}
                  >
                    <AnimatePresence mode="wait" initial={false}>
                      <motion.span
                        key={addItemMutation.isPending ? 'pending' : isAddButtonSuccess ? 'success' : 'idle'}
                        initial={{ opacity: 0, y: 3 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -3 }}
                        transition={{ duration: 0.12, ease: 'easeOut' }}
                        className="flex items-center gap-2"
                      >
                        {addItemMutation.isPending ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Adding...
                          </>
                        ) : isAddButtonSuccess ? (
                          <>
                            <Check className="w-4 h-4" />
                            Added!
                          </>
                        ) : (
                          <>
                            <Plus className="w-4 h-4" />
                            Add Item
                          </>
                        )}
                      </motion.span>
                    </AnimatePresence>
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
