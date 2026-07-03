import { useMutation } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'framer-motion';
import { Plus, Loader2, X, Check, Search, Shirt, Box, Wind, Footprints, Gem, Columns2 } from 'lucide-react';
import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';

import { apiFetch, apiJson } from '../../../lib/api';
import { parseItemInforms } from '../../../lib/iteminform';
import type { SavedItem } from '../../../types/item';
import { useAuth } from '../../../hooks/useAuth';
import { FeedItemCard } from './FeedItemCard';

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
  const [selectedCategory, setSelectedCategory] = useState<string>('FOLDER');
  const [currentFolder, setCurrentFolder] = useState<string | null>(null);
  const [isAddPanelOpen, setIsAddPanelOpen] = useState(false);
  const [isAddButtonSuccess, setIsAddButtonSuccess] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const addSuccessTimeout = useRef<number | null>(null);

  // 컴포넌트 언마운트 시 타이머 클리어
  useEffect(() => {
    return () => {
      if (addSuccessTimeout.current) {
        window.clearTimeout(addSuccessTimeout.current);
      }
    };
  }, []);

  const isFeedAddItem = (item: SavedItem) => parseItemInforms(item)?._source === 'feed_add';

  const categories = useMemo(() => ['FOLDER', 'All'], []);

  const filteredItems = useMemo(
    () => (
      selectedCategory === 'All' || selectedCategory === 'FOLDER'
        ? items
        : items.filter((item) => item.category === selectedCategory)
    ),
    [items, selectedCategory]
  );

  // 🌟 [버그 수정] 옷장 UI 조건식 매칭을 위해 폴더 카테고리명을 애초에 소문자로 포맷팅하여 수집합니다.
  const folders = useMemo(() => {
    const subs = new Set<string>();
    filteredItems.forEach((item) => {
      if (item.category && item.category.toUpperCase() !== 'PROCESSING') {
        subs.add(item.category.toLowerCase());
      }
    });
    return Array.from(subs);
  }, [filteredItems]);

  // 검색 및 노출 아이템 필터링 로직
  const itemsToDisplay = useMemo(() => {
    let baseItems: SavedItem[] = [];
    if (selectedCategory === 'All') {
      baseItems = filteredItems;
    } else if (selectedCategory === 'FOLDER') {
      // 🌟 [안전장치] 폴더 검사 시 소문자 비교 처리로 버그 예방
      baseItems = currentFolder ? filteredItems.filter((item) => item.category?.toLowerCase() === currentFolder) : [];
    } else {
      baseItems = filteredItems.filter((item) => item.category === selectedCategory);
    }

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      return baseItems.filter((item) => {
        const informs = parseItemInforms(item) || {};
        const title = typeof informs.title === 'string' ? informs.title.toLowerCase() : '';
        const category = (item.category || '').toLowerCase();

        const matchesInforms = Object.values(informs).some((v) => {
          if (typeof v === 'string') return v.toLowerCase().includes(query);
          if (Array.isArray(v)) return v.some(subV => typeof subV === 'string' && subV.toLowerCase().includes(query));
          return false;
        });

        return title.includes(query) || category.includes(query) || matchesInforms;
      });
    }

    return baseItems;
  }, [filteredItems, currentFolder, selectedCategory, searchQuery]);

  // 🌟 [삭제 완료] 무한 루프 및 강제 리다이렉션을 유발하던 selectedCategory 추적 이펙트를 제거했습니다.
  // 탭 전환 시 상위나 다른 경로에서 상태를 관리하도록 핸들러에서 직접 리셋하는 편이 안전합니다.

  // 웹소켓 이펙트
  useEffect(() => {
    if (!user) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws/${user.id}`;
    const wsRef = { current: null as WebSocket | null };
    let reconnectTimeout: number | null = null;
    let isUnmounted = false;

    const connectWebSocket = () => {
      if (isUnmounted) return;

      try {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;
        ws.onopen = () => console.info('웹소켓 연결이 설정되었습니다.');

        ws.onmessage = async (event) => {
          try {
            const data = JSON.parse(event.data);
            const removePlaceholder = (prevItems: SavedItem[]) => 
              prevItems.filter(item => Number(item.item_id) !== Number(data.placeholder_id));

            if (data.type === 'CRAWL_SUCCESS') {
              onItemsChange((prev) => [...(data.items || []), ...removePlaceholder(prev)]);
              
              await Promise.allSettled([
                refreshItems?.(),
                refreshTaste?.()
              ]);

            } else if (data.type === 'CRAWL_ERROR') {
              alert(data.message || '데이터를 가져오는 데 실패했습니다.');
              onItemsChange(removePlaceholder);
            }
          } catch (err) {
            console.error('웹소켓 메시지 파싱 오류:', err);
          }
        };

        ws.onerror = (event) => console.error('웹소켓 연결 오류:', event);
        ws.onclose = (event) => {
          if (isUnmounted) return;
          console.warn(`웹소켓 연결 종료 (code=${event.code}). 3초 후 재연결합니다.`);
          
          if (reconnectTimeout) window.clearTimeout(reconnectTimeout);
          reconnectTimeout = window.setTimeout(() => connectWebSocket(), 3000);
        };
        
      } catch (err) {
        console.error('웹소켓 설정 오류:', err);
        if (!isUnmounted) {
          reconnectTimeout = window.setTimeout(() => connectWebSocket(), 3000);
        }
      }
    };

    connectWebSocket();

    return () => {
      isUnmounted = true;
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (reconnectTimeout) {
        window.clearTimeout(reconnectTimeout);
      }
    };
    // 🌟 [의존성 수정] 빠져있던 refreshItems 함수를 채워주어 동기화 버그를 원천 차단합니다.
  }, [user, onItemsChange, refreshItems, refreshTaste]);

  // 아이템 추가 Mutation
  const addItemMutation = useMutation({
    mutationFn: async ({ nextUrl, userId }: { nextUrl: string; userId: string | number }) => {
      const data = await apiJson<any>('/api/crawl_product', {
        method: 'POST',
        body: JSON.stringify({ url: nextUrl, user_id: userId })
      });
      return { nextUrl, data };
    },
    onSuccess: ({ data }) => {
      if (data.success && Array.isArray(data.data) && data.data.length > 0) {
        onItemsChange((prev) => [...data.data, ...prev]);
      }
      setNewUrl("");
      
      setIsAddButtonSuccess(true);
      addSuccessTimeout.current = window.setTimeout(() => {
        setIsAddButtonSuccess(false);
        setIsAddPanelOpen(false);
      }, 1500);
    },
    onError: (error: Error) => {
      console.error(error);
      alert(`분석 요청 중 오류가 발생했습니다: ${error.message}`);
    },
  });

  // 아이템 삭제 Mutation
  const deleteItemMutation = useMutation({
    mutationFn: async ({ id, userId }: { id: number; userId: string | number }) => {
      const res = await apiFetch(`/api/items/${id}?user_id=${userId}`, { 
        method: 'DELETE',
      });
      if (!res.ok) throw new Error('Failed to delete item');
      return id;
    },
    onMutate: async ({ id }) => {
      const previousItems = items;
      onItemsChange((currentItems) => currentItems.filter((item) => item.item_id !== id));
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
        nextUrl: newUrl,
        userId: user.id,
      });
    } catch (err) {
      // 오류는 Mutation onError에서 처리됨
    }
  };

  const handleDelete = async (id: number) => {
    if (!user) return;
    const shouldDelete = window.confirm('정말로 삭제하시겠습니까?');
    if (!shouldDelete) return;
    try {
      await deleteItemMutation.mutateAsync({ id, userId: user.id });
    } catch (err) {
      // 오류는 Mutation onError에서 처리됨
    }
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
      className="flex flex-col min-h-[calc(100vh-200px)] pb-40"
    >
      {/* Page Title */}
      <div className="mb-2 sm:mb-3">
        <h1 className="editorial-heading text-2xl sm:text-3xl md:text-4xl lg:text-5xl text-foreground">
          Find What you Loves.
        </h1>
      </div>

      {/* Add Item Button */}
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

      {/* Category Tabs and Search */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 sm:gap-4 mb-6 sm:mb-8 pb-4 sm:pb-6 border-b border-border">
        <nav className="flex items-center gap-1.5 sm:gap-2 overflow-x-auto pb-2 md:pb-0 category-nav">
          {categories.map((category) => {
            const label = getCategoryLabel(category);
            const isSelected = selectedCategory === category;

            return (
              <button
                key={category}
                onClick={() => {
                  setSelectedCategory(category);
                  setCurrentFolder(null);
                }}
                className={`flex items-center pb-2 px-1 text-xs sm:text-sm font-bold uppercase tracking-widest whitespace-nowrap transition-all border-b-2 ${
                  isSelected
                    ? 'border-black text-black'
                    : 'border-transparent text-muted-foreground hover:text-black hover:border-black/20'
                }`}
              >
                {label}
              </button>
            );
          })}
        </nav>

        <div className="relative w-full md:w-64 lg:w-72 shrink-0">
          <Search className="absolute left-0 top-1/2 -translate-y-1/2 w-3.5 h-3.5 sm:w-4 sm:h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="제목"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full h-9 sm:h-10 pl-7 pr-2 bg-transparent border-b-2 border-black rounded-none text-xs sm:text-sm font-bold focus:outline-none placeholder:text-muted-foreground"
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
                <h3 className="text-lg font-bold text-foreground uppercase tracking-wider">{currentFolder}</h3>
                <button
                  onClick={() => setCurrentFolder(null)}
                  className="ml-auto flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                >
                  <X className="w-4 h-4" />
                  닫기
                </button>
              </div>
            )}

            {/* Folder Cards Closet Layout */}
            {!currentFolder && selectedCategory !== 'All' && (
              <div className="col-span-full grid grid-cols-1 lg:grid-cols-4 gap-6 bg-zinc-50/50 p-6 sm:p-10 rounded-[3rem] border border-zinc-200 shadow-sm relative overflow-hidden">
                <div className="absolute top-0 right-0 w-64 h-64 bg-zinc-200/20 rounded-full -translate-y-1/2 translate-x-1/2 blur-3xl pointer-events-none" />
                
                {/* Left Column: Hanging Area and Bottom Drawer */}
                <div className="lg:col-span-3 space-y-6">
                  {/* Hanging Area */}
                  <div className="relative min-h-[320px] bg-white border border-zinc-200 rounded-[2.5rem] p-8 overflow-hidden group/hanging shadow-sm">
                    <div className="absolute top-10 left-8 right-8 h-1 bg-zinc-200 rounded-full shadow-inner" />
                    <div className="absolute top-4 left-8 text-[10px] font-bold text-zinc-400 uppercase tracking-[0.2em] flex items-center gap-2">
                      <Shirt className="w-3 h-3" /> Hanging Section
                    </div>
                    <div className="flex flex-wrap gap-6 pt-12">
                      {folders.filter(f => ['outer', 'top'].includes(f)).map((folder) => (
                        <motion.div
                          layout
                          key={`folder-${folder}`}
                          onClick={() => setCurrentFolder(folder)}
                          className="group/item relative flex w-32 sm:w-40 aspect-[3/4] flex-col items-center justify-center p-4 bg-white border border-zinc-100 rounded-xl shadow-sm transition-all duration-500 cursor-pointer hover:shadow-xl hover:-translate-y-2 hover:border-black"
                        >
                          <div className="absolute top-3 right-3 text-[10px] font-bold opacity-30 group-hover/item:opacity-100">
                            {filteredItems.filter((i) => i.category?.toLowerCase() === folder).length}
                          </div>
                          <div className="w-8 h-8 rounded-full bg-zinc-50 flex items-center justify-center mb-4 group-hover/item:bg-black group-hover/item:text-white transition-colors">
                            {['outer', 'outerwear'].includes(folder) ? (
                              <Wind className="w-4 h-4" />
                            ) : (
                              <Shirt className="w-4 h-4" />
                            )}
                          </div>
                          <h3 className="text-[11px] font-bold text-foreground uppercase tracking-widest text-center px-2">{folder}</h3>
                        </motion.div>
                      ))}
                    </div>
                  </div>

                  {/* Bottom Drawer */}
                  <div className="relative min-h-[180px] bg-zinc-100 border border-zinc-200 rounded-[2.5rem] p-8 shadow-inner overflow-hidden">
                    <div className="absolute top-4 left-8 text-[10px] font-bold text-zinc-400 uppercase tracking-[0.2em]">Lower Drawer</div>
                    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 w-12 h-1 bg-white rounded-full shadow-sm" />
                    <div className="flex flex-wrap gap-6 justify-center">
                      {folders.filter(f => ['bottom'].includes(f)).map((folder) => (
                        <motion.div
                          layout
                          key={`folder-${folder}`}
                          onClick={() => setCurrentFolder(folder)}
                          className="group/item relative flex w-32 sm:w-40 aspect-square flex-col items-center justify-center p-4 bg-white border border-zinc-100 rounded-xl shadow-sm transition-all duration-500 cursor-pointer hover:shadow-xl hover:-translate-y-1 hover:border-black"
                        >
                          <div className="absolute top-3 right-3 text-[10px] font-bold opacity-30 group-hover/item:opacity-100">
                            {filteredItems.filter((i) => i.category?.toLowerCase() === folder).length}
                          </div>
                          <div className="w-8 h-8 rounded-full bg-zinc-50 flex items-center justify-center mb-4 group-hover/item:bg-black group-hover/item:text-white transition-colors">
                            <Columns2 className="w-4 h-4" />
                          </div>
                          <h3 className="text-[11px] font-bold text-foreground uppercase tracking-widest text-center px-2">{folder}</h3>
                        </motion.div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Right Column: Side Storage */}
                <div className="lg:col-span-1 relative bg-zinc-200/40 border border-zinc-200 rounded-[2.5rem] p-8 flex flex-col gap-6 shadow-sm overflow-hidden">
                  <div className="absolute top-4 left-8 text-[10px] font-bold text-zinc-400 uppercase tracking-[0.2em] flex items-center gap-2">
                    <Box className="w-3 h-3" /> Side Storage
                  </div>
                  <div className="flex flex-col gap-6 pt-8 items-center">
                    {folders.filter(f => ['shoes', 'accessories', 'jewelry'].includes(f)).map((folder) => (
                      <motion.div
                        layout
                        key={`folder-${folder}`}
                        onClick={() => setCurrentFolder(folder)}
                        className="group/item relative flex w-full max-w-[160px] aspect-square flex-col items-center justify-center p-4 bg-white border border-zinc-100 rounded-xl shadow-sm transition-all duration-500 cursor-pointer hover:shadow-xl hover:scale-105 hover:border-black"
                      >
                        <div className="absolute top-3 right-3 text-[10px] font-bold opacity-30 group-hover/item:opacity-100">
                          {filteredItems.filter((i) => i.category?.toLowerCase() === folder).length}
                        </div>
                        <div className="w-8 h-8 rounded-full bg-zinc-50 flex items-center justify-center mb-4 group-hover/item:bg-black group-hover/item:text-white transition-colors">
                          {['shoes'].includes(folder) ? (
                            <Footprints className="w-4 h-4" />
                          ) : (
                            <Gem className="w-4 h-4" />
                          )}
                        </div>
                        <h3 className="text-[11px] font-bold text-foreground uppercase tracking-widest text-center px-2">{folder}</h3>
                      </motion.div>
                    ))}
                  </div>
                </div>

                {/* Miscellaneous Section */}
                {folders.filter(f => !['outer', 'top', 'bottom', 'shoes', 'accessories', 'jewelry'].includes(f)).length > 0 && (
                  <div className="col-span-full pt-8 border-t border-zinc-200/50 mt-4">
                    <h4 className="text-[10px] font-bold text-zinc-400 uppercase tracking-[0.2em] mb-6 px-2">Other Collections</h4>
                    <div className="flex flex-wrap gap-4">
                      {folders.filter(f => !['outer', 'top', 'bottom', 'shoes', 'accessories', 'jewelry'].includes(f)).map((folder) => (
                        <motion.div
                          layout
                          key={`folder-${folder}`}
                          onClick={() => setCurrentFolder(folder)}
                          className="group/item relative flex px-6 py-3 items-center justify-center bg-white border border-zinc-200 rounded-full shadow-sm transition-all duration-300 cursor-pointer hover:bg-black hover:text-white hover:border-black"
                        >
                          <span className="text-[10px] font-bold uppercase tracking-widest">{folder}</span>
                        </motion.div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Item Cards */}
            {itemsToDisplay.map((item) => (
              <FeedItemCard
                key={item.item_id}
                item={item}
                onDelete={handleDelete}
                onSelect={() => onSelectItem(item)}
                onSearchSecondhand={onSearchSecondhand}
              />
            ))}
          </motion.div>
        </AnimatePresence>

        {/* Empty State for All tab */}
        {selectedCategory === 'All' && items.length === 0 && !addItemMutation.isPending && (
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
                  <h3 className="editorial-heading text-xl sm:text-2xl text-foreground">추가하기</h3>
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
                      URL 혹은 상품이름
                    </label>
                    <input
                      type="text"
                      placeholder="https://... 또는 상품명 입력"
                      value={newUrl}
                      onChange={(e) => setNewUrl(e.target.value)}
                      className="w-full h-10 sm:h-12 px-3 sm:px-4 bg-muted rounded-xl text-xs sm:text-sm font-medium placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-black/20"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={addItemMutation.isPending || (!newUrl && !isAddButtonSuccess)}
                    className={`w-full h-10 sm:h-12 flex items-center justify-center rounded-full text-xs sm:text-sm font-semibold transition-all ${
                      isAddButtonSuccess
                        ? 'bg-green-600 text-white'
                        : 'bg-black text-white hover:opacity-90 disabled:opacity-50'
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