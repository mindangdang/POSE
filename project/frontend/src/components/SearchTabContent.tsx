import { motion, AnimatePresence } from 'framer-motion';
import { Search, Loader2, Sparkles, BrainCircuit, Zap, Image as ImageIcon, X } from 'lucide-react';
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
  const [searchMode, setSearchMode] = useState<"digging" | "ai" | "multimodal">("digging");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [generatedImage, setGeneratedImage] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [isDetailedSearch, setIsDetailedSearch] = useState(false);
  const [detailedSearchQuery, setDetailedSearchQuery] = useState({ mood: "", color: "", fit: "", category: "" });
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

  const fetchResults = async (page: number, isAppend: boolean, queryOverride?: string) => {
    setLoading(true);
    try {
      let res;
      const currentQuery = queryOverride !== undefined ? queryOverride : searchQuery;

      if (searchMode === "multimodal") {
        if (!imageFile) {
          throw new Error("멀티모달 검색을 위해 이미지를 붙여넣어주세요. (Ctrl+V / Cmd+V)");
        }
        const formData = new FormData();
        formData.append('image', imageFile);
        formData.append('user_text', currentQuery || '비슷한 상품 찾아줘');

        res = await fetch('/api/multimodal', {
          method: 'POST',
          body: formData
        });
      } else {
        const endpoint = searchMode === "digging" ? '/api/pse' : '/api/lens';
        res = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: currentQuery, page: page }) // 백엔드에 page 번호도 같이 보냄!
        });
      }

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
        if (searchMode === "ai" && data.generated_vibe_image_url) {
          setGeneratedImage(data.generated_vibe_image_url);
        } else {
          setGeneratedImage(null);
        }
      }
    } catch (error: any) {
      console.error(error);
      alert(error.message);
    } finally {
      setLoading(false);
    }
  };

  // 이미지 붙여넣기 핸들러
  const handlePaste = (event: React.ClipboardEvent<HTMLInputElement>) => {
    const items = event.clipboardData.items;
    let file: File | null = null;
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.indexOf('image') !== -1) {
        file = items[i].getAsFile();
        break;
      }
    }
    if (!file) return;

    setSearchMode("multimodal");
    setImageFile(file);
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
  };

  // 1. 엔터 쳐서 '새롭게 검색'할 때
  const handleSearch = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!user) return;
    
    let finalQuery = searchQuery;
    if (searchMode === "digging" && isDetailedSearch) {
      finalQuery = [
        detailedSearchQuery.mood,
        detailedSearchQuery.color,
        detailedSearchQuery.fit,
        detailedSearchQuery.category
      ].filter(Boolean).join(" ");
      if (!finalQuery.trim()) return;
      setSearchQuery(finalQuery); // 더 보기(Pagination) 기능을 위해 통합된 쿼리로 업데이트
    } else {
      if (searchMode !== "multimodal" && !searchQuery) return;
    }

    if (searchMode === "multimodal" && !imageFile) {
      alert("멀티모달 검색을 위해 이미지를 붙여넣어주세요. (Ctrl+V / Cmd+V)");
      return;
    }
    
    setCurrentPage(1);       // 1페이지로 리셋
    setSearchResults([]);    // 기존 화면 싹 지우기
    setGeneratedImage(null);
    await fetchResults(1, false, finalQuery); // 1페이지 데이터 가져와서 덮어쓰기
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
          category: item.category || "WEB SEARCH",
          sub_category: item.sub_category || "WEB SEARCH",
          recommend: item.recommend,
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
        <div className="flex justify-center mb-8">
          <div className="bg-gray-100 p-1 rounded-full grid grid-cols-3 relative shadow-inner w-full max-w-xl">
            <button
              type="button"
              onClick={() => setSearchMode("digging")}
              className={`relative z-10 flex items-center justify-center gap-2 px-4 py-2.5 rounded-full text-sm font-bold transition-colors ${
                searchMode === "digging" ? "text-white" : "text-gray-500 hover:text-gray-900"
              }`}
            >
              <Zap className="w-4 h-4" /> 디깅 모드
            </button>
            <button
              type="button"
              onClick={() => setSearchMode("ai")}
              className={`relative z-10 flex items-center justify-center gap-2 px-4 py-2.5 rounded-full text-sm font-bold transition-colors ${
                searchMode === "ai" ? "text-white" : "text-gray-500 hover:text-gray-900"
              }`}
            >
              <BrainCircuit className="w-4 h-4" /> AI 검색 모드
            </button>
            <button
              type="button"
              onClick={() => setSearchMode("multimodal")}
              className={`relative z-10 flex items-center justify-center gap-2 px-4 py-2.5 rounded-full text-sm font-bold transition-colors ${
                searchMode === "multimodal" ? "text-white" : "text-gray-500 hover:text-gray-900"
              }`}
            >
              <ImageIcon className="w-4 h-4" /> 멀티모달 모드
            </button>
            
            {/* 토글 배경 애니메이션 */}
            <motion.div
              className={`absolute top-1 bottom-1 w-[calc(33.33%-2.66px)] rounded-full ${
                searchMode === "digging" ? "bg-black" : searchMode === "ai" ? "bg-purple-600" : "bg-blue-600"
              }`}
              initial={false}
              animate={{
                x: searchMode === "digging" ? "4px" : searchMode === "ai" ? "calc(100% + 2px)" : "calc(200% + 0px)",
              }}
              transition={{ type: "spring", stiffness: 300, damping: 30 }}
            />
          </div>
        </div>
        <form onSubmit={handleSearch} className="relative group max-w-3xl mx-auto w-full flex flex-col gap-4">
          <AnimatePresence>
            {previewUrl && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.9 }} className="relative w-32 h-32 mx-auto">
                <img src={previewUrl} alt="preview" className="w-full h-full object-cover rounded-2xl shadow-md border-4 border-white" />
                <button
                  type="button"
                  onClick={() => { setPreviewUrl(null); setImageFile(null); }}
                  className="absolute -top-3 -right-3 bg-black text-white rounded-full p-1.5 shadow-lg hover:bg-gray-800 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          {/* 상세 검색어 토글 버튼 */}
          {searchMode === "digging" && (
            <div className="flex justify-end px-4 -mb-2">
              <label className="flex items-center gap-2 cursor-pointer text-sm font-bold text-gray-600 hover:text-black transition-colors">
                <input 
                  type="checkbox" 
                  checked={isDetailedSearch}
                  onChange={(e) => setIsDetailedSearch(e.target.checked)}
                  className="w-4 h-4 rounded border-gray-300 text-black focus:ring-black accent-black"
                />
                상세 검색어
              </label>
            </div>
          )}

          <div className="relative w-full">
            <Search className="absolute left-6 top-1/2 -translate-y-1/2 text-gray-400 w-6 h-6 transition-colors group-focus-within:text-black z-10 pointer-events-none" />
            
            {searchMode === "digging" && isDetailedSearch ? (
              <div className="w-full pl-16 pr-32 py-5 bg-white border-2 border-gray-100 rounded-[2rem] shadow-lg shadow-gray-100 focus-within:border-black transition-all flex items-center gap-1 md:gap-2">
                <input
                  type="text"
                  placeholder="무드(ex:빈티지)"
                  value={detailedSearchQuery.mood}
                  onChange={(e) => setDetailedSearchQuery(prev => ({ ...prev, mood: e.target.value }))}
                  className="w-1/4 bg-transparent focus:outline-none text-center placeholder:text-gray-400 text-xs md:text-base font-medium border-r border-gray-200"
                />
                <input
                  type="text"
                  placeholder="색상(ex:연청)"
                  value={detailedSearchQuery.color}
                  onChange={(e) => setDetailedSearchQuery(prev => ({ ...prev, color: e.target.value }))}
                  className="w-1/4 bg-transparent focus:outline-none text-center placeholder:text-gray-400 text-xs md:text-base font-medium border-r border-gray-200"
                />
                <input
                  type="text"
                  placeholder="핏(ex:플레어)"
                  value={detailedSearchQuery.fit}
                  onChange={(e) => setDetailedSearchQuery(prev => ({ ...prev, fit: e.target.value }))}
                  className="w-1/4 bg-transparent focus:outline-none text-center placeholder:text-gray-400 text-xs md:text-base font-medium border-r border-gray-200"
                />
                <input
                  type="text"
                  placeholder="카테고리(ex:팬츠)"
                  value={detailedSearchQuery.category}
                  onChange={(e) => setDetailedSearchQuery(prev => ({ ...prev, category: e.target.value }))}
                  className="w-1/4 bg-transparent focus:outline-none text-center placeholder:text-gray-400 text-xs md:text-base font-medium"
                />
              </div>
            ) : (
              <input
                type="text"
                onPaste={handlePaste}
                placeholder={
                  searchMode === "digging" 
                    ? "What are you looking for? (e.g., 워싱 디스트로이드 데님)"
                    : searchMode === "ai"
                    ? "머릿속 무드를 설명해주세요 (e.g., 연청 크롭 데님 트러커 자켓)"
                    : "이미지를 붙여넣고(Ctrl+V) 추가 설명(선택)을 입력하세요."
                }
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-16 pr-32 py-5 bg-white border-2 border-gray-100 rounded-[2rem] shadow-lg shadow-gray-100 focus:outline-none focus:border-black transition-all text-lg font-medium"
              />
            )}

            <button
              disabled={loading || quotaCountdown !== null}
              className="absolute right-3 top-1/2 -translate-y-1/2 px-8 py-3 bg-black text-white rounded-full hover:bg-gray-800 disabled:opacity-50 transition-all font-black tracking-widest uppercase text-xs"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : quotaCountdown !== null ? `${quotaCountdown}s` : "Search"}
            </button>
          </div>
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
              <div className="flex justify-center py-12 flex-col items-center gap-4">
                <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
                <p className="text-sm font-medium text-gray-500 animate-pulse text-center">
                  {searchMode === "digging" 
                    ? "디깅하는 중...." 
                    : searchMode === "ai"
                    ? "AI가 디깅하는 중...\n(약 10~15초 소요)"
                    : "멀티모달 이미지 분석 중...\n(약 10~15초 소요)"}
                </p>
              </div>
            ) : (
              <div className="space-y-8">
                {searchMode === "ai" && generatedImage && (
                  <motion.div 
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="flex flex-col items-center bg-white p-6 rounded-3xl border border-gray-100 shadow-sm"
                  >
                    <span className="text-xs font-black tracking-widest uppercase text-purple-600 mb-4 flex items-center gap-2">
                      <Sparkles className="w-4 h-4" /> Generated Vibe
                    </span>
                    <img 
                      src={generatedImage} 
                      alt="AI Generated Vibe" 
                      className="w-48 md:w-64 aspect-[3/4] object-cover rounded-2xl shadow-md"
                    />
                    <p className="text-xs text-gray-400 mt-4 font-medium">를 기반으로 검색한 상품입니다.</p>
                  </motion.div>
                )}

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

      <ItemDetailDialog
        item={selectedItem}
        onOpenChange={(open) => !open && setSelectedItem(null)}
      />
    </>
  );
}
