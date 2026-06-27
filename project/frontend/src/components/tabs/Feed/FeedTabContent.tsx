import { useMutation } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'framer-motion';
import { Plus, X } from 'lucide-react';
import { useEffect, useMemo, useState, type FormEvent } from 'react';

import { apiFetch, apiJson } from '../../../lib/api';
import { parseItemFacts } from '../../../lib/itemFacts';
import type { SavedItem } from '../../../types/item';
import { useAuth } from '../../../hooks/useAuth';
import { FeedAddItemModal } from './FeedAddItemModal';
import { FeedClosetFolders } from './FeedClosetFolders';
import { FeedItemCard } from './FeedItemCard';
import { FeedToolbar } from './FeedToolbar';

type FeedTabContentProps = {
  items: SavedItem[];
  onItemsChange: React.Dispatch<React.SetStateAction<SavedItem[]>>;
  onSelectItem: (item: SavedItem) => void;
  onSearchSecondhand?: (title: string) => void;
  refreshItems: () => Promise<void>;
  refreshTaste: () => Promise<void>;
};

export function FeedTabContent({
  items,
  onItemsChange,
  onSelectItem,
  onSearchSecondhand,
  refreshItems,
  refreshTaste,
}: FeedTabContentProps) {
  const { user } = useAuth();
  const [newUrl, setNewUrl] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>('PRODUCT');
  const [currentFolder, setCurrentFolder] = useState<string | null>(null);
  const [isAddPanelOpen, setIsAddPanelOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

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
      const data = await apiJson<any>('/api/extract-url', {
        method: 'POST',
        body: JSON.stringify({ url: nextUrl, session_id: nextSessionId, user_id: userId })
      });

      return {
        nextUrl,
        data,
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
      const res = await apiFetch(`/api/items/${id}?user_id=${userId}`, { 
        method: 'DELETE',
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
    try {
      await addItemMutation.mutateAsync({
        nextSessionId: sessionId,
        nextUrl: newUrl,
        userId: user.id,
      });
    } catch (err) {
      // Error is already handled by addItemMutation.onError
    }
  };

  const handleDelete = async (id: number) => {
    if (!user) return;
    const shouldDelete = window.confirm('정말로 삭제하시겠습니까?');
    if (!shouldDelete) return;
    try {
      await deleteItemMutation.mutateAsync({ id, userId: user.id });
    } catch (err) {
      // Error is already handled by deleteItemMutation.onError
    }
  };

  const handleSelectCategory = (category: string) => {
    setSelectedCategory(category);
    setCurrentFolder(null);
  };

  return (
    <motion.div
      key="feed"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex flex-col min-h-[calc(100vh-200px)] pb-40"
    >
      {/* Page Title */}
      <div className="mb-2 sm:mb-3">
        <h1 className="editorial-heading text-2xl sm:text-3xl md:text-4xl lg:text-5xl text-foreground">
          Find What you Loves.
        </h1>
      </div>

      {/* Add Item Button Position - Directly above search toolbar */}
      <div className="flex justify-end mb-1 sm:mb-2">
        <button
          onClick={() => setIsAddPanelOpen(true)}
          className="flex items-center gap-1.5 sm:gap-2 pb-1 px-1 border-b-2 border-black text-black text-xs sm:text-sm font-bold uppercase tracking-widest hover:opacity-70 transition-opacity"
        >
          <Plus className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
          <span className="hidden sm:inline">추가하기</span>
          <span className="sm:hidden">Add</span>
        </button>
      </div>

      <FeedToolbar
        categories={categories}
        selectedCategory={selectedCategory}
        searchQuery={searchQuery}
        onSelectCategory={handleSelectCategory}
        onSearchQueryChange={setSearchQuery}
      />

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

            {!currentFolder && selectedCategory !== 'All' && (
              <FeedClosetFolders
                folders={folders}
                items={filteredItems}
                onSelectFolder={setCurrentFolder}
              />
            )}

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
            <button
              onClick={() => setIsAddPanelOpen(true)}
              className="flex items-center gap-2 pb-1 px-1 border-b-2 border-black text-black text-xs sm:text-sm font-bold uppercase tracking-wider hover:opacity-70 transition-opacity"
            >
              <Plus className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              첫 아이템 넣기
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

      <FeedAddItemModal
        isOpen={isAddPanelOpen}
        isPending={addItemMutation.isPending}
        newUrl={newUrl}
        sessionId={sessionId}
        onClose={() => setIsAddPanelOpen(false)}
        onSubmit={handleAddItem}
        onNewUrlChange={setNewUrl}
        onSessionIdChange={setSessionId}
      />
    </motion.div>
  );
}
