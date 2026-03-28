import { motion, AnimatePresence } from 'framer-motion';
import { Search, Loader2, Sparkles } from 'lucide-react';
import { useEffect, useState } from 'react';

import type { SavedItem } from '../types/item';
import { ItemDetailDialog } from './ItemDetailDialog'; 

type SearchTabContentProps = {
  onItemsChange: React.Dispatch<React.SetStateAction<SavedItem[]>>;
  refreshTaste: () => Promise<void>;
  user: { id: number; username: string } | null;
};

export function SearchTabContent({
  onItemsChange,
  refreshTaste,
  user,
}: SearchTabContentProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [quotaCountdown, setQuotaCountdown] = useState<number | null>(null);
  
  // 상태 변경: 문자열에서 SavedItem 배열로!
  const [searchResults, setSearchResults] = useState<SavedItem[]>([]);
  
  // 모달 제어 상태
  const [selectedItem, setSelectedItem] = useState<SavedItem | null>(null);

  // 이 컴포넌트에서는 전체 피드백 로직(Like/Dislike 버튼 뭉치)을 제거했어. 
  // 카드가 여러 개 나오기 때문에, 검색 결과 전체에 대한 피드백보다는 개별 카드를 피드에 저장하는 게 자연스럽기 때문이야.

  useEffect(() => {
    if (quotaCountdown !== null && quotaCountdown > 0) {
      const timer = setTimeout(() => setQuotaCountdown(quotaCountdown - 1), 1000);
      return () => clearTimeout(timer);
    }
    if (quotaCountdown === 0) {
      setQuotaCountdown(null);
    }
  }, [quotaCountdown]);

  const handleSearch = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!searchQuery || !user) return;
    setLoading(true);
    setSearchResults([]); // 검색 시작 시 결과 초기화

    try {
      const res = await fetch('/api/pse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: searchQuery })
      });

      if (res.status === 429) {
        setQuotaCountdown(60);
        setLoading(false);
        return;
      }

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Search failed");
      }

      // 백엔드에서 조립해준 카드 배열 JSON을 받음
      const data = await res.json();
      setSearchResults(data.results || []);
      setLoading(false);

    } catch (error: any) {
      console.error(error);
      alert(error.message);
      setLoading(false);
    }
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

            {loading ? (
              <div className="flex justify-center py-12">
                <p className="text-sm font-medium text-gray-400 animate-pulse flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" /> 구글에서 이미지를 찾아오는 중...
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
                <AnimatePresence>
                  {searchResults.map((item, index) => {
                    // 카드가 순차적으로 뜨도록 delay 설정
                    const delay = index * 0.1;
                    const factsObj = typeof item.facts === 'string' ? JSON.parse(item.facts) : item.facts;
                    const title = factsObj?.title || item.summary_text || "제목 없음";

                    return (
                      <motion.div
                        key={item.id}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay, duration: 0.3 }}
                        onClick={() => setSelectedItem(item)}
                        className="group bg-white rounded-3xl overflow-hidden shadow-sm hover:shadow-xl transition-all duration-300 cursor-pointer border border-gray-100 flex flex-col h-full"
                      >
                        {/* 썸네일 영역 */}
                        <div className="aspect-square w-full bg-gray-100 overflow-hidden relative">
                          {item.image_url ? (
                            <img
                              src={item.image_url}
                              alt={title}
                              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                              referrerPolicy="no-referrer"
                              onError={(e) => {
                                (e.target as HTMLImageElement).src = 'https://via.placeholder.com/400x400?text=No+Image';
                              }}
                            />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center text-gray-400 text-xs font-bold bg-gray-50">
                              No Image
                            </div>
                          )}
                          <div className="absolute top-3 left-3">
                            <span className="inline-block text-[10px] font-black uppercase tracking-widest text-white bg-black/80 backdrop-blur-md px-2.5 py-1 rounded-lg">
                              {item.category}
                            </span>
                          </div>
                        </div>

                        {/* 텍스트 정보 영역 */}
                        <div className="p-5 flex flex-col flex-1">
                          <h3 className="font-bold text-black text-sm line-clamp-2 mb-2 leading-snug">
                            {title}
                          </h3>
                          <p className="text-xs text-gray-500 line-clamp-2 mb-4">
                            {item.summary_text}
                          </p>
                          <div className="mt-auto">
                            <button
                              onClick={(e) => handleSaveToFeed(e, item)}
                              className="w-full py-2.5 bg-gray-50 hover:bg-black hover:text-white text-black rounded-xl text-xs font-black uppercase tracking-widest transition-colors flex items-center justify-center gap-2"
                            >
                              + 피드에 저장
                            </button>
                          </div>
                        </div>
                      </motion.div>
                    );
                  })}
                </AnimatePresence>
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