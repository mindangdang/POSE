import { motion, AnimatePresence } from 'framer-motion';
import { Search, Loader2, Sparkles, BrainCircuit, Zap, X, Plus } from 'lucide-react';
import { useEffect, useState, useRef } from 'react';

import type { SavedItem } from '../types/item';
import type { AppUser } from '../types/user';
import { ItemDetailDialog } from './ItemDetailDialog';
import { SearchResultCard } from './SearchResultCard';

type SearchTabContentProps = {
  onItemsChange: React.Dispatch<React.SetStateAction<SavedItem[]>>;
  refreshItems: () => Promise<void>;
  refreshTaste: () => Promise<void>;
  user: AppUser | null;
  searchSecondhandQuery?: string;
  searchSecondhandTrigger?: number;
};

const SUGGESTION_POOL = [
  "빈티지 리바이스",
  "미니멀 셋업",
  "아카이브 헬무트랭",
  "오버핏 가디건",
  "시티보이 룩",
  "고프코어 자켓",
  "와이드 실루엣 팬츠",
  "디스트로이드 데님",
  "크롭 레이어링",
  "테크니컬 웨어",
  "90년대 스트릿",
  "그런지 무드",
  "올드머니 룩",
  "가죽 자켓",
  "발레코어",
  "Y2K 스타일",
  "클래식 트렌치 코트",
  "헤비 스웨트셔츠",
  "워크웨어 부츠",
  "보헤미안 시크"
];

export function SearchTabContent({
  onItemsChange,
  refreshItems,
  refreshTaste,
  user,
  searchSecondhandQuery,
  searchSecondhandTrigger,
}: SearchTabContentProps) {
  const [searchMode, setSearchMode] = useState<"digging" | "ai">("digging");
  const [generatedImage, setGeneratedImage] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [isDetailedSearch, setIsDetailedSearch] = useState(false);
  const [detailedSearchQuery, setDetailedSearchQuery] = useState({ mood: "", color: "", fit: "", category: "" });
  const [randomSuggestions, setRandomSuggestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [quotaCountdown, setQuotaCountdown] = useState<number | null>(null);
  const [searchResults, setSearchResults] = useState<SavedItem[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [isModeMenuOpen, setIsModeMenuOpen] = useState(false);
  const [showDetailedSuggestions, setShowDetailedSuggestions] = useState(false);
  const hasSearchActivity = loading || searchResults.length > 0 || quotaCountdown !== null;
  // 모달 제어 상태
  const [selectedItem, setSelectedItem] = useState<SavedItem | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const modeOptions = [
    { value: "digging", label: "일반 검색", icon: Plus, activeClass: "text-black cursor-pointer hover:bg-gray-200", hoverClass: "hover:text-black hover:cursor-pointer" },
    { value: "detail", label: "상세 검색", icon: Zap, activeClass: "text-yellow-500 cursor-pointer hover:bg-gray-200", hoverClass: "hover:text-yellow-500 hover:cursor-pointer" },
    { value: "ai", label: "AI 검색", icon: BrainCircuit, activeClass: "text-blue-600 cursor-pointer hover:bg-gray-200", hoverClass: "hover:text-blue-600 hover:cursor-pointer" },
  ] as const;
  const activeMode = searchMode === "digging" && isDetailedSearch
    ? modeOptions[1]
    : searchMode === "digging"
      ? modeOptions[0]
    : searchMode === "ai"
      ? modeOptions[2]
        : null;
  const ActiveModeIcon = activeMode?.icon ?? Plus;
  const detailFields = [
    { key: "mood", placeholder: "무드", suggestions: ["빈티지", "미니멀", "스트릿"] },
    { key: "color", placeholder: "색상", suggestions: ["블랙", "연청", "아이보리"] },
    { key: "fit", placeholder: "핏", suggestions: ["오버핏", "크롭", "와이드"] },
    { key: "category", placeholder: "카테고리", suggestions: ["티셔츠", "자켓", "팬츠"] },
  ] as const;

  useEffect(() => {
    // 20개 중 6개 랜덤 선택
    const shuffled = [...SUGGESTION_POOL].sort(() => 0.5 - Math.random());
    setRandomSuggestions(shuffled.slice(0, 6));
  }, []);

  type ModeOptionValue = (typeof modeOptions)[number]["value"];

  useEffect(() => {
    if (searchMode !== "digging" || !isDetailedSearch || hasSearchActivity) {
      setShowDetailedSuggestions(false);
      return;
    }

    const timer = window.setTimeout(() => setShowDetailedSuggestions(true), 100);
    return () => window.clearTimeout(timer);
  }, [hasSearchActivity, isDetailedSearch, searchMode]);

  useEffect(() => {
    if (!user) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws/${user.id}`;
    let ws: WebSocket;

   try {
      console.log(`[웹소켓] 연결 시도 중... (${wsUrl})`);
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log("[웹소켓] 연결 성공!");
      };

      ws.onerror = (error) => {
        console.error("[웹소켓] 에러 발생:", error);
      };

      ws.onclose = (event) => {
        console.log(`[웹소켓] 연결 종료 (코드: ${event.code}, 이유: ${event.reason})`);
      };

      ws.onmessage = (event) => {
        console.log("[웹소켓] 메시지 수신 (raw):", event.data);
        try {
          const data = JSON.parse(event.data);
          console.log("[웹소켓] 메시지 파싱 완료:", data);
          
          if (data.type === "SEARCH_SUCCESS") {
            console.log(`[웹소켓] 검색 결과(SEARCH_SUCCESS) ${data.results?.length || 0}개 수신, is_append: ${data.is_append}`);
            
            if (data.is_append) {
              setSearchResults(prev => {
                // 검색 결과에 고유 id가 없는 경우 프론트에서 임시 id 생성
                const newItems = (data.results || []).map((rawItem: any) => {
                  const item = rawItem.result ? rawItem.result : rawItem;
                  return {
                    ...item,
                    id: item.id || `ws-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`
                  };
                });

                const uniqueItems = newItems.filter(
                  (newItem: SavedItem) => !prev.some(item => item.id === newItem.id || (item.url && item.url === newItem.url))
                );
                
                return [...prev, ...uniqueItems];
              });
            } else {
              setSearchResults((data.results || []).map((rawItem: any) => {
                const item = rawItem.result ? rawItem.result : rawItem;
                return {
                  ...item,
                  id: item.id || `ws-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`
                };
              }));
            }
          } else if (data.type === "SEARCH_FINISHED") {
            console.log("[웹소켓] 검색 완료(SEARCH_FINISHED). 로딩 상태 해제.");
            setLoading(false);
          } else if (data.type === "SEARCH_ERROR") {
            console.log("[웹소켓] 검색 에러(SEARCH_ERROR):", data.message);
            alert(data.message || "검색 중 오류가 발생했습니다.");
            setLoading(false);
          }
        } catch (err) {
          console.error("웹소켓 메시지 파싱 오류:", err);
        }
      };
    } catch (err) {
      console.error("웹소켓 연결 에러:", err);
    }

    return () => {
      if (ws) {
        if (ws.readyState === WebSocket.CONNECTING) {
          ws.addEventListener('open', () => ws.close());
        } else {
          ws.close();
        }
      }
    };
  }, [user]);

  // 검색 결과 무한 스크롤 (Lazy Loading) 구현 및 자동 스크롤 제거
  useEffect(() => {
    const currentBottomRef = bottomRef.current;
    if (!currentBottomRef) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !loading && hasMore && searchResults.length > 0) {
          handleLoadMore();
        }
      },
      { threshold: 0.1, rootMargin: '200px' }
    );

    observer.observe(currentBottomRef);

    return () => {
      observer.unobserve(currentBottomRef);
    };
  }, [loading, hasMore, searchResults.length, currentPage]);

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

      const token = localStorage.getItem('access_token');
      const authHeaders: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
      const endpoint = searchMode === "digging" ? '/api/pse' : '/api/lens';
      res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({ query: currentQuery, page: page }) // 백엔드에 page 번호도 같이 보냄!
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

      const data = await res.json();

      if (searchMode === "digging" && data.success && !data.results) {
        // 검색이 백그라운드 태스크로 전환되었으므로 웹소켓 이벤트 수신 대기 (로딩 상태 유지)
        return;
      }

      if (isAppend) {
        // 더 보기: 기존 결과 뒤에 새 결과를 배열로 이어 붙임
        setSearchResults(prev => [...prev, ...(data.results || [])]);
        if (!data.results || data.results.length === 0) setHasMore(false);
      } else {
        // 새 검색: 기존 결과를 싹 지우고 새 결과만 보여줌
        setSearchResults(data.results || []);
        if (!data.results || data.results.length === 0) setHasMore(false);
        if (searchMode === "ai" && data.generated_vibe_image_url) {
          setGeneratedImage(data.generated_vibe_image_url);
        } else {
          setGeneratedImage(null);
        }
      }
      setLoading(false);
    } catch (error: any) {
      console.error(error);
      alert(error.message);
      setLoading(false);
    }
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
      if (!searchQuery) return;
    }

    setCurrentPage(1);       // 1페이지로 리셋
    setSearchResults([]);    // 기존 화면 싹 지우기
    setGeneratedImage(null);
    setHasMore(true);        // 무한 스크롤 상태 리셋
    await fetchResults(1, false, finalQuery); // 1페이지 데이터 가져와서 덮어쓰기
  };

  // 2. '더 보기' 버튼을 눌렀을 때
  const handleLoadMore = async () => {
    const nextPage = currentPage + 1;
    setCurrentPage(nextPage);      // 페이지 번호 1 증가
    await fetchResults(nextPage, true); // 다음 페이지 데이터 가져와서 이어 붙이기
  };

  const handleSecondhandSearch = async (title: string) => {
    setSearchMode("digging");
    setIsDetailedSearch(false);
    setSearchQuery(title);
    setSearchResults([]);
    setLoading(true);
    setGeneratedImage(null);
    setHasMore(false);

    try {
      const token = localStorage.getItem('access_token');
      const authHeaders: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await fetch('/api/search/secondhand', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({ query: title })
      });
      if (!res.ok) throw new Error("Secondhand search failed");
      const data = await res.json();
      setSearchResults(data.results || []);
    } catch (error: any) {
      alert(error.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!searchSecondhandQuery || searchSecondhandTrigger === undefined) return;
    void handleSecondhandSearch(searchSecondhandQuery);
  }, [searchSecondhandQuery, searchSecondhandTrigger]);

  const applySelectedMode = (mode: ModeOptionValue) => {
    if (mode === "digging") {
      setSearchMode("digging");
      setIsDetailedSearch(false);
    } else if (mode === "detail") {
      setSearchMode("digging");
      setIsDetailedSearch(true);
    } else {
      setSearchMode(mode);
      setIsDetailedSearch(false);
    }
  };

  const handleSelectMode = (mode: ModeOptionValue) => {
    setIsModeMenuOpen(false);

    if (showDetailedSuggestions && mode !== "detail") {
      setShowDetailedSuggestions(false);
      window.setTimeout(() => applySelectedMode(mode), 110);
      return;
    }

    applySelectedMode(mode);
  };

  // 개별 카드를 내 피드에 저장하는 함수
  const handleSaveToFeed = async (e: React.MouseEvent, item: SavedItem) => {
    e.stopPropagation(); // 카드 클릭(모달 열기) 이벤트 막기
    if (!user) return;

    try {
      const token = localStorage.getItem('access_token');
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch('/api/items/manual', {
        method: 'POST',
        headers,
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
      await refreshItems();

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
        className={[
          "relative",
          "mx-auto flex w-full flex-col transition-[max-width] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
          hasSearchActivity ? "max-w-6xl" : "max-w-4xl",
          hasSearchActivity ? "space-y-8 py-8" : "min-h-[calc(100vh-8rem)] justify-center",
        ].join(" ")}
      >
        {/* Subtle Background Image Layer for Window Tab */}
        {!hasSearchActivity && (
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

        <motion.div
          layout
          className="flex w-full flex-col items-center gap-8"
          animate={{ y: hasSearchActivity ? -56 : 0 }}
          transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
        >
          <AnimatePresence>
            {!hasSearchActivity && (
              <motion.div
                key="search-brand"
                initial={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20, height: 0, marginBottom: -32 }}
                transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
                className="flex w-full max-w-3xl flex-col items-start gap-4 sm:gap-6 overflow-hidden"
              >
                <h1 className="font-bold text-2xl sm:text-3xl md:text-4xl lg:text-5xl text-foreground text-left leading-tight tracking-tight">
                  네 자신을 찾는 일을 목표로
                  <br />
                  하는 인생은 재밌어.
                  <br />
                  그렇지 않아?
                </h1>
              </motion.div>
            )}
          </AnimatePresence>

          <form onSubmit={handleSearch} className="relative group max-w-3xl w-full flex flex-col gap-4">

          <motion.div
            layout
            transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
            className="relative w-full"
          >
            <div className="absolute left-3 top-1/2 z-20 -translate-y-1/2">
              <button
                type="button"
                aria-label={activeMode ? `${activeMode.label} 모드 변경` : "검색 모드 선택"}
                title={activeMode ? `${activeMode.label} 모드` : "검색 모드 선택"}
                onClick={() => setIsModeMenuOpen((open) => !open)}
                className={`flex h-10 w-10 items-center justify-center rounded-full transition-colors ${
                  activeMode ? activeMode.activeClass : "text-muted-foreground hover:bg-muted"
                }`}
              >
                <ActiveModeIcon className="h-5 w-5" />
              </button>

              <AnimatePresence>
                {isModeMenuOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: -8, scale: 0.98 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -8, scale: 0.98 }}
                    transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
                    className="absolute left-0 top-12 flex w-44 flex-col gap-1 rounded-2xl bg-background p-1.5 shadow-2xl border border-border z-[100]"
                  >
                    {modeOptions.map(({ value, label, icon: Icon, activeClass, hoverClass }) => (
                      <button
                        key={value}
                        type="button"
                        aria-label={`${label} 모드`}
                        onClick={() => handleSelectMode(value)}
                        className={`flex h-11 items-center gap-3 rounded-xl px-3 text-left text-sm font-bold transition-all hover:bg-muted ${
                          activeMode?.value === value ? activeClass : `text-muted-foreground ${hoverClass}`
                        }`}
                      >
                        <Icon className="h-4 w-4" />
                        <span className="whitespace-nowrap">{label}</span>
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {searchMode === "digging" && isDetailedSearch && !hasSearchActivity ? (
              <motion.div
                layout
                initial={false}
                animate={{ height: 240 }}
                transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
                className="flex w-full flex-col justify-center border-b-2 border-foreground bg-background py-0 pl-16 pr-16"
              >
                {detailFields.map(({ key, placeholder, suggestions }, index) => (
                  <div
                    key={key}
                    className={[
                      "flex min-h-14 items-center gap-3",
                      index < detailFields.length - 1 ? "border-b border-border" : "",
                    ].join(" ")}
                  >
                    <input
                      type="text"
                      placeholder={placeholder}
                      value={detailedSearchQuery[key]}
                      onChange={(e) => setDetailedSearchQuery((prev) => ({ ...prev, [key]: e.target.value }))}
                      className="h-full min-w-0 flex-1 bg-transparent text-sm font-bold placeholder:text-muted-foreground focus:outline-none"
                    />

                    <div className="flex w-36 shrink-0 justify-end overflow-hidden py-1 sm:w-44 md:w-52">
                      <AnimatePresence initial={false}>
                        {showDetailedSuggestions && (
                          <motion.div
                            key={`${key}-suggestions`}
                            initial={{ opacity: 0, x: 10, scale: 0.98 }}
                            animate={{ opacity: 1, x: 0, scale: 1 }}
                            exit={{ opacity: 0, x: 10, scale: 0.98 }}
                            transition={{ duration: 0.1, ease: [0.16, 1, 0.3, 1] }}
                            className="flex justify-end gap-1.5"
                          >
                            {suggestions.map((suggestion) => {
                              const selected = detailedSearchQuery[key] === suggestion;

                              return (
                                <button
                                  key={suggestion}
                                  type="button"
                                  onClick={() => setDetailedSearchQuery((prev) => ({
                                    ...prev,
                                    [key]: prev[key] === suggestion ? "" : suggestion,
                                  }))}
                                  className={[
                                    "shrink-0 rounded-full border px-3 py-1.5 text-xs font-bold transition-colors",
                                    selected
                                      ? "border-black bg-black text-white"
                                      : "border-border bg-background text-muted-foreground hover:border-black hover:text-black",
                                  ].join(" ")}
                                >
                                  {suggestion}
                                </button>
                              );
                            })}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  </div>
                ))}
              </motion.div>
            ) : (
              <motion.div
                layout
                initial={false}
                animate={{ height: 56 }}
                transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
                className="w-full border-b-2 border-foreground bg-background transition-all duration-300"
              >
                <input
                  type="text"
                  placeholder={
                    searchMode === "digging"
                      ? "원하는 스타일을 검색해보세요 (예: 디스트로이드 데님)"
                      : "떠오르는 스타일을 자유롭게 입력해보세요"
                  }
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="h-full w-full rounded-full bg-transparent pl-16 pr-16 text-base font-bold placeholder:text-muted-foreground outline-0"
                />
              </motion.div>
            )}

            <button
              disabled={loading || quotaCountdown !== null}
              className="absolute right-2 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full text-foreground transition-colors hover:bg-muted disabled:opacity-50"
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : quotaCountdown !== null ? <span className="text-xs font-bold">{quotaCountdown}s</span> : <Search className="w-5 h-5" />}
            </button>
          </motion.div>
          </form>

          {/* 추천 검색어 영역 */}
          {!hasSearchActivity && randomSuggestions.length > 0 && (
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="w-full max-w-3xl flex flex-wrap gap-x-4 gap-y-2 px-1"
            >
              {randomSuggestions.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => {
                    setSearchQuery(suggestion);
                    // 클릭 시 바로 검색 실행을 원하시면 여기에 handleSearch 호출 로직 추가 가능
                  }}
                  className="text-xs sm:text-sm text-muted-foreground hover:text-black border-b border-transparent hover:border-black transition-all pb-0.5"
                >
                  {suggestion}
                </button>
              ))}
            </motion.div>
          )}
        </motion.div>

        {quotaCountdown !== null && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center p-4 bg-red-50 text-red-600 rounded-xl border border-red-100 text-sm font-bold max-w-3xl mx-auto"
          >
            토큰이 부족합니다. {quotaCountdown}초 뒤에 다시 시도하세요.
          </motion.div>
        )}

        {/* 검색 결과 영역 */}
        {(loading || searchResults.length > 0) && (
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
            className="min-h-[60vh]"
          >
            <div className="w-full flex flex-col">
              <AnimatePresence>
                {loading && (
                  <motion.div
                    key="loading-indicator"
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="flex flex-col items-center justify-center gap-4 py-8 overflow-hidden"
                  >
                    <div className="w-12 h-12 rounded-full border-2 border-muted border-t-foreground animate-spin" />
                    <p style={{ whiteSpace: 'pre-line' }} className="text-sm font-bold text-muted-foreground text-center">
                      {searchResults.length > 0
                        ? `Discovering... (${searchResults.length} items found)`
                        : searchMode === "digging"
                        ? "Searching..."
                        : searchMode === "ai"
                        ? "AI is finding your style...\nThis may take 10-15 seconds"
                        : "Analyzing..."}
                    </p>
                  </motion.div>
                )}
              </AnimatePresence>

              {searchMode === "ai" && generatedImage && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="flex flex-col items-center bg-muted/50 p-8 rounded-2xl border border-border mb-8"
                >
                  <span className="text-[10px] font-bold tracking-[0.2em] uppercase text-muted-foreground mb-4 flex items-center gap-2">
                    <Sparkles className="w-4 h-4" /> Generated Vibe
                  </span>
                  <img
                    src={generatedImage}
                    alt="AI Generated Vibe"
                    className="w-48 md:w-56 aspect-[3/4] object-cover rounded-xl shadow-lg"
                  />
                  <p className="text-xs text-muted-foreground mt-4 font-bold">Based on your style input</p>
                </motion.div>
              )}

              {/* Pinterest-style Masonry Grid */}
              <div className="masonry-grid">
                <AnimatePresence>
                  {searchResults.map((item, index) => (
                    <SearchResultCard
                      key={item.id}
                      delay={0.03 * (index % 20)}
                      item={item}
                      onClick={() => setSelectedItem(item)}
                      onSave={handleSaveToFeed}
                      onSearchSecondhand={handleSecondhandSearch}
                    />
                  ))}
                </AnimatePresence>
              </div>

              {/* Loading Skeletons */}
              {loading && (
                <div className="masonry-grid mt-4">
                  {Array.from({ length: Math.max(5, 10 - searchResults.length) }).map((_, i) => (
                    <div key={`skeleton-${i}`} className="masonry-item">
                      <div 
                        className="w-full bg-muted rounded-2xl animate-pulse" 
                        style={{ 
                          aspectRatio: [3/4, 4/5, 1, 2/3, 5/6][i % 5]
                        }}
                      />
                      <div className="mt-3 space-y-2 px-1">
                        <div className="h-2 bg-muted rounded w-1/3 animate-pulse" />
                        <div className="h-3 bg-muted rounded w-3/4 animate-pulse" />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div ref={bottomRef} className="h-4" />
              
              {searchResults.length > 0 && hasMore && (
                <div className="flex justify-center py-10 w-full">
                  <button
                    onClick={handleLoadMore}
                    disabled={loading}
                    className="h-12 px-8 bg-foreground text-background rounded-full text-sm font-semibold hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-2"
                  >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                    Load More
                  </button>
                </div>
              )}
            </div>
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
