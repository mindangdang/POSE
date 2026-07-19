import { motion, AnimatePresence } from 'framer-motion';
import { useEffect, useState, useCallback } from 'react';

import type { SavedItem } from '../../../types/item';
import { useInfiniteScroll } from '../../../hooks/useInfiniteScroll';
import { useSearch } from '../../../hooks/useSearch';
import { useQuotaCountdown } from '../../../hooks/useQuotaCountdown';
import { usePasteImage } from '../../../hooks/usePasteImage';
import { SearchState } from '../../../hooks/searchUtils';
import { useAuth } from '../../../hooks/useAuth';
import { ItemDetailDialog } from '../../common';
import { useWebSocketSearch } from '../../../hooks/useWebSocketSearch';
import { AddShopModal } from './AddShopModal';
import { ShopSelector } from './ShopSelector';
import { SearchHeader } from './SearchHeader';
import { SearchResults } from './SearchResults';
import {
  DEFAULT_DETAILED_SEARCH_QUERY,
  getInitialShops,
  getRandomSuggestions,
  saveShops,
  type DetailedSearchQuery,
  type SearchMode,
  type Shop,
} from './searchConfig';
import { saveItemToFeed } from '../../../hooks/itemService';

type SearchTabContentProps = {
  onItemsChange: React.Dispatch<React.SetStateAction<SavedItem[]>>;
  refreshItems: () => Promise<void>;
  searchSecondhandQuery?: string;
  searchSecondhandTrigger?: number;
};

export function SearchTabContent({
  onItemsChange,
  refreshItems,
  searchSecondhandQuery,
  searchSecondhandTrigger,
}: SearchTabContentProps) {
  const { user } = useAuth();
  const [shops, setShops] = useState<Shop[]>(getInitialShops);

  const [searchMode, setSearchMode] = useState<SearchMode>("digging");
  const [searchQuery, setSearchQuery] = useState("");
  const [isDetailedSearch, setIsDetailedSearch] = useState(false);
  const [detailedSearchQuery, setDetailedSearchQuery] = useState<DetailedSearchQuery>(DEFAULT_DETAILED_SEARCH_QUERY);

  const [isAddShopModalOpen, setIsAddShopModalOpen] = useState(false);
  const [selectedShopNames, setSelectedShopNames] = useState<Set<string>>(new Set());
  const [selectedItem, setSelectedItem] = useState<SavedItem | null>(null);
  const [randomSuggestions] = useState(getRandomSuggestions);
  
  const { quotaCountdown, startCountdown } = useQuotaCountdown();
  const handleImagePasted = useCallback((base64: string) => {
    setSearchQuery(base64);
    setSearchMode("ai");
  }, []);
  const { pastedFile, previewUrl, handlePaste, clearImage } = usePasteImage(handleImagePasted);

  const searchState = useSearch({
    searchMode,
    selectedShopNames,
    shops,
    pastedFile,
    startQuotaCountdown: startCountdown, // Pass startCountdown to useSearch
  });

  const {
    searchResults, status, isLoadingMore, hasMore, generatedImage,
    search, loadMore, handleWebSocketSearchSuccess, handleWebSocketSearchFinished, handleWebSocketSearchError
  } = searchState;

  const displayActivity =
    status !== SearchState.IDLE || searchResults.length > 0 || quotaCountdown !== null;

  useEffect(() => {
    saveShops(shops);
  }, [shops]);

  useWebSocketSearch({
    onSearchSuccess: handleWebSocketSearchSuccess,
    onSearchFinished: handleWebSocketSearchFinished,
    onSearchError: handleWebSocketSearchError,
  });

  const bottomRef = useInfiniteScroll({
    enabled: hasMore,
    loading: isLoadingMore || status === SearchState.LOADING,
    onLoadMore: useCallback(() => loadMore(searchQuery), [loadMore, searchQuery]),
  });

  const setBottomRef = useCallback((node: HTMLDivElement | null) => {
    bottomRef.current = node;
  }, [bottomRef]);

  const handleSecondhandSearch = useCallback(async (title: string) => {
    setSearchMode("digging");
    setIsDetailedSearch(false);
    setSearchQuery(title);
    await search(title);
  }, [search]);

  useEffect(() => {
    if (!searchSecondhandQuery || searchSecondhandTrigger === undefined || !handleSecondhandSearch) return;
    void handleSecondhandSearch(searchSecondhandQuery);
  }, [searchSecondhandQuery, searchSecondhandTrigger, handleSecondhandSearch]);

  const handleSearchSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!user) return;
    let finalQuery = searchQuery;
    if (searchMode === "digging" && isDetailedSearch) {
      finalQuery = Object.values(detailedSearchQuery).filter(Boolean).join(" ");
      if (!finalQuery.trim()) return;
      setSearchQuery(finalQuery);
    } else {
      if (!searchQuery.trim() && !pastedFile) return;
    }
    await search(finalQuery);
  };

  const handleRemoveSelectedShop = useCallback((name: string) => {
    setSelectedShopNames(prev => {
      const next = new Set(prev);
      next.delete(name);
      return next;
    });
  }, []);

  const handleClearSelectedShops = useCallback(() => {
    setSelectedShopNames(new Set());
  }, []);

  const handleSaveToFeed = async (e: React.MouseEvent, item: SavedItem) => {
    e.stopPropagation();
    if (!user) return;
    await saveItemToFeed(user, item, onItemsChange, refreshItems);
  };

  const handleAddShop = (newShop: Shop) => {
    setShops(prev => [newShop, ...prev]);
    setIsAddShopModalOpen(false);
  };

  return (
    <>
      <motion.div
        key="search"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -20 }}
        className="relative mx-auto flex w-full flex-col px-4"
        style={{
          maxWidth: '1400px',
          paddingTop: displayActivity ? '2rem' : '15vh',
          paddingBottom: displayActivity ? '10rem' : '25vh',
          transition: 'padding 0.45s cubic-bezier(0.16, 1, 0.3, 1)'

        }}
      >
        {/* Subtle Background Image Layer for Window Tab */}
        {!displayActivity && (
          <div className="fixed inset-x-0 top-0 h-screen pointer-events-none -z-10 overflow-hidden">
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.5 }}
              transition={{ duration: 1.2 }}
              className="w-full h-full"
              style={{ 
                backgroundImage: 'url("/image.png")',
                backgroundSize: 'cover',
                backgroundPosition: 'center',
                maskImage: 'linear-gradient(to bottom, black 0%, black 30%, transparent 55%)',
                WebkitMaskImage: 'linear-gradient(to bottom, black 0%, black 30%, transparent 55%)'
              }}
            />
          </div>
        )}

        <SearchHeader
          query={{
            mode: searchMode,
            setMode: setSearchMode,
            value: searchQuery,
            setValue: setSearchQuery,
            isDetailed: isDetailedSearch,
            setIsDetailed: setIsDetailedSearch,
            details: detailedSearchQuery,
            setDetails: setDetailedSearchQuery,
          }}
          image={{
            previewUrl,
            onPaste: handlePaste,
            onClear: clearImage,
          }}
          searchStatus={{
            status,
            quotaCountdown,
            displayActivity,
            onSubmit: handleSearchSubmit,
          }}
          shopBadges={{
            selectedNames: selectedShopNames,
            onRemoveSelected: handleRemoveSelectedShop,
            onClearSelected: handleClearSelectedShops,
          }}
          suggestions={{
            items: randomSuggestions,
          }}
        />
        <ShopSelector
          shops={shops}
          selectedShopNames={selectedShopNames}
          setSelectedShopNames={setSelectedShopNames}
          onOpenAddShopModal={() => setIsAddShopModalOpen(true)}
          displayActivity={displayActivity}
        />

        {quotaCountdown !== null && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center p-4 bg-red-50 text-red-600 rounded-xl border border-red-100 text-sm font-bold max-w-3xl mx-auto"
          >
            토큰이 부족합니다. {quotaCountdown}초 뒤에 다시 시도하세요.
          </motion.div>
        )}
        <SearchResults
          displayActivity={displayActivity}
          searchMode={searchMode}
          searchResults={searchResults}
          status={status}
          isLoadingMore={isLoadingMore}
          hasMore={hasMore}
          generatedImage={generatedImage}
          quotaCountdown={quotaCountdown}
          loadMore={loadMore}
          searchQuery={searchQuery}
          bottomRef={setBottomRef}
          onSelectItem={setSelectedItem}
          onSaveItem={handleSaveToFeed}
          onSearchSecondhand={handleSecondhandSearch}
        />
      </motion.div>

      <ItemDetailDialog
        item={selectedItem}
        onOpenChange={(open) => !open && setSelectedItem(null)}
      />

      {/* Add Shop Modal */}
      <AddShopModal
        isOpen={isAddShopModalOpen}
        onClose={() => setIsAddShopModalOpen(false)}
        onAddShop={handleAddShop}
      />
    </>
  );
}
