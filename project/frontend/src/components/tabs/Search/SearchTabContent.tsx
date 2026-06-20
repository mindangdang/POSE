import { motion, AnimatePresence } from 'framer-motion';
import { useEffect, useState, useCallback, useMemo } from 'react';

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
import { saveItemToFeed } from '../../../hooks/itemService';

type SearchTabContentProps = {
  onItemsChange: React.Dispatch<React.SetStateAction<SavedItem[]>>;
  refreshItems: () => Promise<void>;
  refreshTaste: () => Promise<void>;
  searchSecondhandQuery?: string;
  searchSecondhandTrigger?: number;
};

// Define a type for shop objects
type Shop = {
  name: string;
  url: string;
  desc: string;
};

const SUGGESTION_POOL = [
  "빈티지 리바이스",
  "폴로 카라티",
  "아르마니 익스체인지",
  "슬림핏 반팔",
  "유니폼",
  "아크테릭스 바람막이",
  "와이드 팬츠",
  "디스트로이드 데님",
  "빈티지 돌체 앤 가바나",
  "테크웨어",
  "웨스턴 셔츠",
  "그런지 팬츠",
  "올드머니 룩",
  "가죽 자켓",
  "포엣코어",
  "Y2K",
  "버버리 트렌치 코트",
  "헤비 스웨트셔츠",
  "팀버랜드 부츠",
  "펜던트 목걸이"
];

const SELECT_SHOPS = [
  { name: "FRUITS FAMILY", desc: "감도높은 빈티지/세컨핸드 매물 거래용", url: "https://fruitsfamily.com" },
  { name: "FETCHING", desc: "전 세계 럭셔리 편집샵 아이템 비교 직구", url: "https://fetching.co.kr" },
  { name: "EMPTY", desc: "무신사가 제안하는 실험적 디자이너 브랜드", url: "https://empty.seoul.kr" },
  { name: "WORKSOUT", desc: "하이엔드 스트릿웨어와 라이프스타일 셀렉샵", url: "https://worksout.co.kr" },
  { name: "8DIVISION", desc: "남성 헤리티지 및 컨템포러리 셀렉샵", url: "https://8division.com" },
  { name: "IAMSHOP", desc: "고감도 컨템포러리 브랜드 및 워크웨어 큐레이션", url: "https://iamshop-online.com" },
  { name: "THE BOUNCE", desc: "국내외 인기 스트릿 브랜드를 모은 멀티샵", url: "https://thebounce.co.kr" },
  { name: "THE X SHOP", desc: "스트릿 컬처와 스케이트보드 편집 매장", url: "https://thexshop.co.kr" },
  { name: "COLLECTIV", desc: "세컨핸드 패션의 새로운 가치를 제안하는 플랫폼", url: "https://collectiv.kr" },
  { name: "KREAM", desc: "한정판 스니커즈와 럭셔리 아이템 거래 플랫폼", url: "https://kream.co.kr" },
  { name: "MUSINSA", desc: "국내 최대 패션 스토어 및 트렌드 큐레이션", url: "https://musinsa.com" },
  { name: "EQL", desc: "한섬에서 제안하는 감각적인 라이프스타일 셀렉샵", url: "https://eqlstore.com" },
  { name: "29CM", desc: "감도깊은 취향 셀렉트샵", url: "https://29cm.co.kr" },
  { name: "Bunjang", desc: "브랜드 중고거래 플랫폼", url: "https://bunjang.co.kr" },
  { name: "Danggeun Market", desc: "지역 기반 중고거래 플랫폼", url: "https://www.daangn.com" },
  { name: "Joonggonara", desc: "중고나라 커뮤니티 기반 중고거래 플랫폼", url: "https://www.joongna.com" },
  { name: "ZARA", desc: "글로벌 패션 브랜드, 트렌디한 아이템 다수 보유", url: "https://www.zara.com" }
];

export function SearchTabContent({ // Renamed to avoid conflict with `generatedImage` from useSearch
  onItemsChange,
  refreshItems,
  refreshTaste,
  searchSecondhandQuery,
  searchSecondhandTrigger,
}: SearchTabContentProps) {
  const { user } = useAuth();
  const [shops, setShops] = useState<Shop[]>(SELECT_SHOPS);

  useEffect(() => {
    const saved = localStorage.getItem('user_shops');
    if (saved) {
      setShops(JSON.parse(saved));
    }
  }, []);

  const [searchMode, setSearchMode] = useState<"digging" | "ai">("digging");
  const [searchQuery, setSearchQuery] = useState("");
  const [isDetailedSearch, setIsDetailedSearch] = useState(false);
  const [detailedSearchQuery, setDetailedSearchQuery] = useState({ mood: "", color: "", fit: "", category: "" , brand: "" });

  const [isAddShopModalOpen, setIsAddShopModalOpen] = useState(false); // Keep this, it controls the modal's visibility
  const [selectedShopNames, setSelectedShopNames] = useState<Set<string>>(new Set()); // Keep here, needed for useSearch
  
  const { quotaCountdown, startCountdown } = useQuotaCountdown();
  const { pastedFile, previewUrl, handlePaste, clearImage } = usePasteImage((base64) => {
    setSearchQuery(base64);
    setSearchMode("ai");
  });

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

  const [selectedItem, setSelectedItem] = useState<SavedItem | null>(null);

  const [randomSuggestions, setRandomSuggestions] = useState<string[]>([]); // Keep randomSuggestions here

  useEffect(() => {
    // 20개 중 6개 랜덤 선택
    const shuffled = [...SUGGESTION_POOL].sort(() => 0.5 - Math.random());
    setRandomSuggestions(shuffled.slice(0, 6));
  }, []);
  useEffect(() => {
    localStorage.setItem('user_shops', JSON.stringify(shops));
  }, [shops]);

  // WebSocket hook
  useWebSocketSearch({ // This hook is assumed to be defined elsewhere or needs to be implemented.
    onSearchSuccess: handleWebSocketSearchSuccess,
    onSearchFinished: handleWebSocketSearchFinished,
    onSearchError: handleWebSocketSearchError,
  });

  const bottomRef = useInfiniteScroll({ enabled: hasMore, loading: isLoadingMore || status === SearchState.LOADING, onLoadMore: useCallback(() => loadMore(searchQuery), [loadMore, searchQuery]) });

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

  const handleSaveToFeed = async (e: React.MouseEvent, item: SavedItem) => {
    e.stopPropagation(); // Prevent card click (modal opening) event
    if (!user) return;
    await saveItemToFeed(user, item, onItemsChange, refreshItems, refreshTaste);
  };

  const handleAddShop = (newShop: Shop) => {
    setShops(prev => [newShop, ...prev]); // Add new shop to the list
    // No need to reset newShopData here, it's managed internally by AddShopModal
    // and will be reset when the modal closes and re-opens.
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
          searchMode={searchMode}
          setSearchMode={setSearchMode}
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          isDetailedSearch={isDetailedSearch}
          setIsDetailedSearch={setIsDetailedSearch}
          detailedSearchQuery={detailedSearchQuery}
          setDetailedSearchQuery={setDetailedSearchQuery}
          pastedFile={pastedFile}
          previewUrl={previewUrl}
          handlePaste={handlePaste}
          clearImage={clearImage}
          status={status}
          quotaCountdown={quotaCountdown}
          generatedImage={generatedImage}
          displayActivity={displayActivity}
          handleSearch={handleSearchSubmit}
          selectedShopNames={selectedShopNames}
          setSelectedShopNames={setSelectedShopNames}
          randomSuggestions={randomSuggestions} // Pass randomSuggestions to SearchHeader
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
          bottomRef={(node: HTMLDivElement | null) => {
            if (!bottomRef) return;
            if (typeof bottomRef === 'function') {
              try { (bottomRef as (node: HTMLDivElement | null) => void)(node); } catch {}
            } else {
              try { (bottomRef as { current: HTMLDivElement | null }).current = node; } catch {}
            }
          }}
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
