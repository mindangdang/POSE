import { motion, AnimatePresence } from 'framer-motion';
import { Search, Loader2, Sparkles } from 'lucide-react';
import { useEffect, useState } from 'react';

import type { SavedItem } from '../types/item';
import type { AppUser } from '../types/user';
import { ItemDetailDialog } from './ItemDetailDialog'; 
import { SearchResultCard } from './SearchResultCard';

type SearchTabContentProps = {
  onItemsChange: React.Dispatch<React.SetStateAction<SavedItem[]>>;
  refreshTaste: () => Promise<void>;
  user: AppUser | null;
};

export function SearchTabContent({
  onItemsChange,
  refreshTaste,
  user,
}: SearchTabContentProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [quotaCountdown, setQuotaCountdown] = useState<number | null>(null);
  const [searchResults, setSearchResults] = useState<SavedItem[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  // 모달 제어 상태
  const [selectedItem, setSelectedItem] = useState<SavedItem | null>(null);

  useEffect(() => {
    if (quotaCountdown !== null && quotaCountdown > 0) {
      const timer = setTimeout(() => setQuotaCountdown(quotaCountdown - 1), 1000);
      return () => clearTimeout(timer);
    }
    if (quotaCountdown === 0) {
      setQuotaCountdown(null);
    }
  }, [quotaCountdown]);

  const fetchResults = async (page: number, isAppend: boolean) => {
    setLoading(true);
    try {
      const res = await fetch('/api/pse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: searchQuery, page: page }) // 백엔드에 page 번호도 같이 보냄!
      });

      if (res.status === 429) {
        setQuotaCountdown(60);
        return;
      }

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Search failed");
      }

      const data = await res.json();
      
      if (isAppend) {
        // 더 보기: 기존 결과 뒤에 새 결과를 배열로 이어 붙임
        setSearchResults(prev => [...prev, ...(data.results || [])]);
      } else {
        // 새 검색: 기존 결과를 싹 지우고 새 결과만 보여줌
        setSearchResults(data.results || []);
      }
    } catch (error: any) {
      console.error(error);
      alert(error.message);
    } finally {
      setLoading(false);
    }
  };

  // 1. 엔터 쳐서 '새롭게 검색'할 때
  const handleSearch = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!searchQuery || !user) return;
    
    setCurrentPage(1);       // 1페이지로 리셋
    setSearchResults([]);    // 기존 화면 싹 지우기
    await fetchResults(1, false); // 1페이지 데이터 가져와서 덮어쓰기
  };

  // 2. '더 보기' 버튼을 눌렀을 때
  const handleLoadMore = async () => {
    const nextPage = currentPage + 1;
    setCurrentPage(nextPage);      // 페이지 번호 1 증가
    await fetchResults(nextPage, true); // 다음 페이지 데이터 가져와서 이어 붙이기
  };

  // 개별 카드를 내 피드에 저장하는 함수
  const handleSaveToFeed = async (e: React.MouseEvent, item: SavedItem) => {
    e.stopPropagation(); // 카드 클릭(모달 열기) 이벤트 막기
    if (!user) return;

    try {
      const res = await fetch('/api/items/manual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: user.id,
          category: "WEB SEARCH",
          vibe: item.vibe,
          facts: item.facts,
          url: item.url,
          image_url: item.image_url
        })
      });

      if (!res.ok) throw new Error("Failed to save result");

      // 내 피드(상위 컴포넌트 상태) 업데이트
      const newItem: SavedItem = {
        ...item,
        id: Date.now(), // 고유 ID 재할당
        created_at: new Date().toISOString(),
      };
      onItemsChange((prev) => [newItem, ...prev]);
      
      alert("피드에 저장되었습니다!");
      await refreshTaste();
    } catch (error: any) {
      console.error(error);
      alert(error.message);
    }
  };

  return (
    <>
      <motion.div
        key="search"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -20 }}
        className="max-w-4xl mx-auto space-y-12 py-12"
      >
        <div className="text-center space-y-4">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-tr from-blue-500 via-yellow-300 to-purple-500 p-[2px] mb-4">
            <div className="w-full h-full bg-black rounded-[14px] flex items-center justify-center">
              <Search className="w-8 h-8 text-white" />
            </div>
          </div>
          <h2 className="text-4xl font-black tracking-tighter uppercase">POSE! Search</h2>
          <p className="text-gray-500 font-medium">당신의 취향을 기반으로 구글에서 새로운 영감을 찾아냅니다.</p>
        </div>

        <form onSubmit={handleSearch} className="relative group max-w-3xl mx-auto">
          <Search className="absolute left-6 top-1/2 -translate-y-1/2 text-gray-400 w-6 h-6 transition-colors group-focus-within:text-black" />
          <input
            type="text"
            placeholder="What are you looking for? (e.g., 빈티지한 조명)"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-16 pr-32 py-5 bg-white border-2 border-gray-100 rounded-[2rem] shadow-lg shadow-gray-100 focus:outline-none focus:border-black transition-all text-lg font-medium"
          />
          <button
            disabled={loading || quotaCountdown !== null}
            className="absolute right-3 top-1/2 -translate-y-1/2 px-8 py-3 bg-black text-white rounded-full hover:bg-gray-800 disabled:opacity-50 transition-all font-black tracking-widest uppercase text-xs"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : quotaCountdown !== null ? `${quotaCountdown}s` : "Search"}
          </button>
        </form>

        {quotaCountdown !== null && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center p-4 bg-red-50 text-red-600 rounded-2xl border border-red-100 text-sm font-bold tracking-tight max-w-3xl mx-auto"
          >
            토큰이 부족합니다. {quotaCountdown}초 뒤에 다시 시도하세요.
          </motion.div>
        )}

        {/* 검색 결과 영역 */}
        {(loading || searchResults.length > 0) && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-gray-50/50 p-6 md:p-8 rounded-[3rem] border border-black/5"
          >
            <div className="flex items-center gap-3 mb-8 pb-6 border-b border-gray-200">
              <div className="flex items-center gap-3 text-xs font-black uppercase tracking-widest text-black">
                <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-500 via-yellow-300 to-purple-500 p-[2px]">
                  <div className="w-full h-full bg-black rounded-full flex items-center justify-center">
                    <Sparkles className="w-4 h-4 text-white" />
                  </div>
                </div>
                Search Results
              </div>
            </div>

            {loading && searchResults.length === 0 ? (
              <div className="flex justify-center py-12">
                <p className="text-sm font-medium text-gray-400 animate-pulse flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" /> 구글에서 검색하는 중...
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
                <AnimatePresence>
                  {searchResults.map((item, index) => {
                    return (
                      <SearchResultCard
                        key={item.id}
                        delay={index * 0.1}
                        item={item}
                        onClick={() => setSelectedItem(item)}
                        onSave={handleSaveToFeed}
                      />
                    );
                  })}
                </AnimatePresence>
              </div>
            )}
            {searchResults.length > 0 && (
              <div className="flex justify-center pt-10">
                <button
                  onClick={handleLoadMore}
                  disabled={loading}
                  className="px-10 py-3 bg-white border-2 border-black text-black rounded-full text-xs font-black uppercase tracking-widest hover:bg-black hover:text-white transition-all shadow-md disabled:opacity-50 flex items-center gap-2"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                  Load More Inspiration
                </button>
              </div>
            )}
          </motion.div>
        )}
      </motion.div>

      {/* 모달 렌더링 (카드를 클릭했을 때만 띄움) */}
      <ItemDetailDialog
        item={selectedItem}
        onOpenChange={(open) => !open && setSelectedItem(null)}
      />
    </>
  );
}
