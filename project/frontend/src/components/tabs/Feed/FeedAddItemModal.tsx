import { AnimatePresence, motion } from 'framer-motion';
import { Check, Loader2, Plus, Search, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';

import { apiJson } from '../../../lib/api';
import { getDisplayImageUrl, getFallbackImageUrl } from '../../../lib/imageUrl';
import type { SavedItem } from '../../../types/item';

type FeedAddItemModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onSelectItem: (item: SavedItem) => void | Promise<void>;
  onRequestCrawl: (url: string) => void | Promise<void>;
};

export function FeedAddItemModal({
  isOpen,
  onClose,
  onSelectItem,
  onRequestCrawl,
}: FeedAddItemModalProps) {
  const [titleQuery, setTitleQuery] = useState('');
  const [requestUrl, setRequestUrl] = useState('');
  const [searchResults, setSearchResults] = useState<SavedItem[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [showRequestForm, setShowRequestForm] = useState(false);
  const [isRequesting, setIsRequesting] = useState(false);
  const searchTimerRef = useRef<number | null>(null);

  const trimmedQuery = useMemo(() => titleQuery.trim(), [titleQuery]);

  useEffect(() => {
    if (!isOpen) {
      setTitleQuery('');
      setRequestUrl('');
      setSearchResults([]);
      setSearchError(null);
      setShowRequestForm(false);
      setIsSearching(false);
      setIsRequesting(false);
      if (searchTimerRef.current) {
        window.clearTimeout(searchTimerRef.current);
      }
      return;
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;

    if (searchTimerRef.current) {
      window.clearTimeout(searchTimerRef.current);
    }

    if (!trimmedQuery) {
      setSearchResults([]);
      setSearchError(null);
      setShowRequestForm(false);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    setSearchError(null);
    searchTimerRef.current = window.setTimeout(() => {
      void (async () => {
        try {
          const response = await apiJson<{ success: boolean; results: SavedItem[]; count?: number }>(
            `/api/product_db/search?query=${encodeURIComponent(trimmedQuery)}&limit=12`,
          );
          setSearchResults(Array.isArray(response.results) ? response.results : []);
          setShowRequestForm(false);
        } catch (error) {
          console.error('product_db search failed:', error);
          setSearchResults([]);
          setSearchError('상품 검색에 실패했습니다.');
        } finally {
          setIsSearching(false);
        }
      })();
    }, 300);

    return () => {
      if (searchTimerRef.current) {
        window.clearTimeout(searchTimerRef.current);
      }
    };
  }, [isOpen, trimmedQuery]);

  const handleSelectItem = async (item: SavedItem) => {
    await onSelectItem(item);
    onClose();
  };

  const handleRequestSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!requestUrl.trim()) return;

    setIsRequesting(true);
    try {
      await onRequestCrawl(requestUrl.trim());
      onClose();
    } finally {
      setIsRequesting(false);
    }
  };

  const hasNoResults = trimmedQuery.length > 0 && !isSearching && searchResults.length === 0 && !searchError;

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            key="add-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
            onClick={onClose}
          />
          <motion.div
            key="add-popup"
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 12 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
          >
              <div className="w-full max-w-2xl rounded-2xl sm:rounded-3xl bg-background p-5 sm:p-7 shadow-2xl border border-border max-h-[90vh] overflow-hidden flex flex-col">
                <div className="flex items-center justify-between gap-4 mb-5 sm:mb-6">
                  <div className="space-y-1">
                    <h3 className="editorial-heading text-xl sm:text-2xl text-foreground">추가하기</h3>
                    <p className="text-xs sm:text-sm text-muted-foreground font-medium">
                      원하는 상품명을 입력하면 비슷한 상품을 먼저 찾아줍니다.
                    </p>
                  </div>
                  <button
                    onClick={onClose}
                    className="w-8 h-8 sm:w-9 sm:h-9 flex items-center justify-center rounded-full text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                  >
                    <X className="w-4 h-4 sm:w-5 sm:h-5" />
                  </button>
                </div>

                <div className="space-y-4 flex-1 overflow-y-auto pr-1">
                  <div className="space-y-2">
                    <label className="block text-[10px] sm:text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      상품명 검색
                    </label>
                    <div className="relative">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                      <input
                        type="text"
                        placeholder="예: 아디다스 삼바"
                        value={titleQuery}
                        onChange={(e) => setTitleQuery(e.target.value)}
                        className="w-full h-11 sm:h-12 pl-10 pr-4 bg-muted rounded-xl text-xs sm:text-sm font-medium placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-black/20"
                      />
                    </div>
                  </div>

                  {searchError && (
                    <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-600">
                      {searchError}
                    </div>
                  )}

                  {isSearching && (
                    <div className="flex items-center gap-2 rounded-2xl border border-border bg-muted/50 px-4 py-3 text-sm font-semibold text-muted-foreground">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      상품을 찾는 중...
                    </div>
                  )}

                  {searchResults.length > 0 && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                          검색 결과 {searchResults.length}개
                        </p>
                      </div>

                      <div className="grid gap-3">
                        {searchResults.map((item) => {
                          const title = item.title || 'Untitled';
                          const imageUrl = getDisplayImageUrl(item.image_url, undefined, getFallbackImageUrl('No+Image'));

                          return (
                            <motion.button
                              key={item.product_id}
                              type="button"
                              whileHover={{ y: -1 }}
                              onClick={() => void handleSelectItem(item)}
                              className="flex items-center gap-3 rounded-2xl border border-border bg-background p-3 text-left transition-colors hover:border-black/20 hover:bg-muted/40"
                            >
                              <div className="h-16 w-16 shrink-0 overflow-hidden rounded-xl bg-muted">
                                <img
                                  src={imageUrl}
                                  alt={title}
                                  className="h-full w-full object-cover"
                                  referrerPolicy="no-referrer"
                                />
                              </div>
                              <div className="min-w-0 flex-1">
                                <div className="flex items-start justify-between gap-3">
                                  <div className="min-w-0">
                                    <p className="truncate text-sm font-semibold text-foreground">{title}</p>
                                    <p className="truncate text-xs text-muted-foreground">
                                      {item.brand || 'Unknown brand'} · {item.shop || 'Unknown shop'}
                                    </p>
                                  </div>
                                  <span className="inline-flex items-center gap-1 rounded-full border border-black/10 bg-white px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-black">
                                    <Check className="w-3 h-3" />
                                    선택
                                  </span>
                                </div>
                                <p className="mt-2 text-xs font-medium text-muted-foreground line-clamp-2">
                                  {item.price == null
                                    ? '가격 정보 없음'
                                    : new Intl.NumberFormat('ko-KR', {
                                        style: 'currency',
                                        currency: item.currency || 'KRW',
                                      }).format(item.price)}
                                </p>
                              </div>
                            </motion.button>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {hasNoResults && !showRequestForm && (
                    <div className="rounded-3xl border border-dashed border-border bg-muted/30 p-5 text-center space-y-3">
                      <p className="text-sm font-semibold text-foreground">검색된 아이템이 없습니다.</p>
                      <p className="text-xs sm:text-sm text-muted-foreground">
                        원하는 상품의 URL을 입력해서 새 아이템 추가를 요청할 수 있습니다.
                      </p>
                      <button
                        type="button"
                        onClick={() => setShowRequestForm(true)}
                        className="inline-flex items-center justify-center gap-2 rounded-full bg-black px-4 py-2.5 text-xs sm:text-sm font-semibold text-white transition-opacity hover:opacity-90"
                      >
                        <Plus className="w-4 h-4" />
                        아이템 추가 요청하기
                      </button>
                    </div>
                  )}

                  {showRequestForm && (
                    <form onSubmit={handleRequestSubmit} className="space-y-3 rounded-3xl border border-border bg-muted/20 p-4 sm:p-5">
                      <div className="space-y-2">
                        <label className="block text-[10px] sm:text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                          상품 URL 입력
                        </label>
                        <input
                          type="url"
                          placeholder="https://..."
                          value={requestUrl}
                          onChange={(e) => setRequestUrl(e.target.value)}
                          className="w-full h-11 sm:h-12 px-4 bg-background rounded-xl text-xs sm:text-sm font-medium placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-black/20"
                        />
                      </div>
                      <button
                        type="submit"
                        disabled={isRequesting || !requestUrl.trim()}
                        className="w-full h-11 sm:h-12 flex items-center justify-center rounded-full bg-black text-white text-xs sm:text-sm font-semibold transition-all hover:opacity-90 disabled:opacity-50"
                      >
                        <AnimatePresence mode="wait" initial={false}>
                          <motion.span
                            key={isRequesting ? 'pending' : 'idle'}
                            initial={{ opacity: 0, y: 3 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -3 }}
                            transition={{ duration: 0.12, ease: 'easeOut' }}
                            className="flex items-center gap-2"
                          >
                            {isRequesting ? (
                              <>
                                <Loader2 className="w-4 h-4 animate-spin" />
                                요청 중...
                              </>
                            ) : (
                              <>
                                <Plus className="w-4 h-4" />
                                추가 요청하기
                              </>
                            )}
                          </motion.span>
                        </AnimatePresence>
                      </button>
                    </form>
                  )}
                </div>
              </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
