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
        const summary = (item.summary_text || '').toLowerCase();
        const recommend = (item.recommend || '').toLowerCase();
        const factValues = Object.values(facts).map(v => String(v).toLowerCase()).join(' ');

        return title.includes(query) || category.includes(query) || subCategory.includes(query) || summary.includes(query) || recommend.includes(query) || factValues.includes(query);
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
      <header className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <span className="text-accent text-xs font-bold tracking-widest uppercase">MY COLLECTION</span>
            <h1 className="text-2xl md:text-3xl font-bold text-foreground mt-1">내 피드</h1>
          </div>
          <button
            onClick={() => setIsAddPanelOpen(true)}
            className="flex items-center gap-2 h-10 px-4 bg-primary text-primary-foreground rounded-full text-sm font-medium hover:opacity-90 transition-opacity"
          >
            <Plus className="w-4 h-4" />
            아이템 추가
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
            className="text-muted-foreground font-medium italic"
          >
            {feedQuotes[quoteIndex]}
          </motion.p>
        </AnimatePresence>
      </header>

      {/* Category Tabs and Search */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <nav className="flex items-center gap-2 overflow-x-auto pb-2 md:pb-0 category-nav">
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
                className={`flex items-center gap-2 h-9 px-4 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${
                  isSelected
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground hover:text-foreground'
                }`}
              >
                <Icon className="w-4 h-4" />
                {label}
              </button>
            );
          })}
        </nav>

        <div className="relative w-full md:w-64 shrink-0">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="피드 내 아이템 검색..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full h-9 pl-9 pr-4 rounded-full bg-muted text-sm font-medium focus:outline-none focus:ring-2 focus:ring-primary/20 transition-shadow"
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
              />
            ))}
          </motion.div>
        </AnimatePresence>

        {/* Empty State */}
        {items.length === 0 && !addItemMutation.isPending && (
          <div className="flex flex-col items-center justify-center py-20 bg-muted rounded-2xl border-2 border-dashed border-border">
            <h3 className="text-xl font-bold text-foreground mb-2">POSE</h3>
            <p className="text-muted-foreground font-medium mb-4">
              아이템 링크를 넣고 나만의 바이브를 수집하세요.
            </p>
            <button
              onClick={() => setIsAddPanelOpen(true)}
              className="flex items-center gap-2 h-10 px-4 bg-primary text-primary-foreground rounded-full text-sm font-medium hover:opacity-90 transition-opacity"
            >
              <Plus className="w-4 h-4" />
              첫 아이템 추가하기
            </button>
          </div>
        )}

        {/* Empty State for Search */}
        {items.length > 0 && itemsToDisplay.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 bg-muted rounded-2xl border-2 border-dashed border-border">
            <h3 className="text-xl font-bold text-foreground mb-2">검색 결과 없음</h3>
            <p className="text-muted-foreground font-medium mb-4">
              조건에 맞는 아이템을 찾을 수 없습니다.
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
              className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
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
              <div className="w-full max-w-md rounded-2xl bg-background p-6 shadow-2xl border border-border">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="text-lg font-bold text-foreground">새 아이템 추가하기</h3>
                  <button
                    onClick={() => setIsAddPanelOpen(false)}
                    className="w-8 h-8 flex items-center justify-center rounded-full text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <form onSubmit={handleAddItem} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-1.5">
                      URL 또는 제품명
                    </label>
                    <input
                      type="url"
                      placeholder="https://..."
                      value={newUrl}
                      onChange={(e) => setNewUrl(e.target.value)}
                      className="w-full h-11 px-4 bg-muted rounded-lg text-sm font-medium placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-foreground/10"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-1.5">
                      Session ID (선택)
                    </label>
                    <input
                      type="password"
                      placeholder="Session ID"
                      value={sessionId}
                      onChange={(e) => setSessionId(e.target.value)}
                      className="w-full h-11 px-4 bg-muted rounded-lg text-sm font-medium placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-foreground/10"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={addItemMutation.isPending || (!newUrl && !isAddButtonSuccess)}
                    className={`w-full h-11 flex items-center justify-center rounded-lg text-sm font-bold transition-colors ${
                      isAddButtonSuccess
                        ? 'bg-green-500 text-primary-foreground'
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
                            추가 중...
                          </>
                        ) : isAddButtonSuccess ? (
                          <>
                            <Check className="w-4 h-4" />
                            추가 완료!
                          </>
                        ) : (
                          <>
                            <Plus className="w-4 h-4" />
                            추가하기
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
