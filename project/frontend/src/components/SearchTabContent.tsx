import { motion, AnimatePresence } from 'framer-motion';
import { Search, Loader2, Sparkles, BrainCircuit, Zap, X, Plus, ExternalLink } from 'lucide-react';
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
  "폴로 카라티",
  "아카이브 헬무트랭",
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
  { name: "HYPEBEAST", desc: "글로벌 스트릿 패션 트렌드 및 큐레이션", url: "https://hypebeast.kr" },
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
];

// URL에서 도메인을 추출하는 헬퍼 함수
const getDomain = (url: string) => {
  try { return new URL(url).hostname.replace('www.', ''); }
  catch { return url.replace(/^https?:\/\//, '').split('/')[0]; }
};

export function SearchTabContent({
  onItemsChange,
  refreshItems,
  refreshTaste,
  user,
  searchSecondhandQuery,
  searchSecondhandTrigger,
}: SearchTabContentProps) {
  const [shops, setShops] = useState(SELECT_SHOPS);
  const [searchMode, setSearchMode] = useState<"digging" | "ai">("digging");
  const [generatedImage, setGeneratedImage] = useState<string | null>(null);
  const [pastedImage, setPastedImage] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [isDetailedSearch, setIsDetailedSearch] = useState(false);
  const [detailedSearchQuery, setDetailedSearchQuery] = useState({ mood: "", color: "", fit: "", category: "" , brand: "" });
  const [randomSuggestions, setRandomSuggestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchActive, setSearchActive] = useState(false);
  const MIN_LOADING_MS = 700; // 최소 로딩 표시 시간
  const fetchCounterRef = useRef(0);
  const loadingStartRef = useRef<number | null>(null);
  const [quotaCountdown, setQuotaCountdown] = useState<number | null>(null);
  const [searchResults, setSearchResults] = useState<SavedItem[]>([]);
  const [selectedShopNames, setSelectedShopNames] = useState<string[]>([]);
  const [activeDomainMap, setActiveDomainMap] = useState<Record<string, string> | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [isModeMenuOpen, setIsModeMenuOpen] = useState(false);
  const [showDetailedSuggestions, setShowDetailedSuggestions] = useState(false);
  // displayActivity: determines compact layout (results/loading/quota)
  const displayActivity = loading || searchResults.length > 0 || quotaCountdown !== null || searchActive;
  const [isAddShopModalOpen, setIsAddShopModalOpen] = useState(false);
  const [newShopData, setNewShopData] = useState({ name: "", url: "", desc: "" });
  // 모달 제어 상태
  const [selectedItem, setSelectedItem] = useState<SavedItem | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const modeOptions = [
    { value: "digging", label: "일반 검색", icon: Plus, activeClass: "text-black cursor-pointer hover:bg-gray-200", hoverClass: "hover:text-black hover:cursor-pointer" },
    { value: "ai", label: "AI 검색", icon: BrainCircuit, activeClass: "text-black cursor-pointer hover:bg-gray-200", hoverClass: "hover:text-black hover:cursor-pointer" },
  ] as const;
  const activeMode = modeOptions.find(opt => opt.value === searchMode) || modeOptions[0];
  const ActiveModeIcon = activeMode?.icon ?? Plus;
  const detailFields = [
    { key: "mood", placeholder: "무드", suggestions: ["빈티지", "미니멀", "스트릿"] },
    { key: "color", placeholder: "색상", suggestions: ["블랙", "연청", "아이보리"] },
    { key: "fit", placeholder: "핏", suggestions: ["오버핏", "크롭", "와이드"] },
    { key: "category", placeholder: "카테고리", suggestions: ["티셔츠", "자켓", "팬츠"] },
    { key: "brand", placeholder: "브랜드", suggestions: ["리바이스", "엘무드", "노이어"] },
  ] as const;

  useEffect(() => {
    // 20개 중 6개 랜덤 선택
    const shuffled = [...SUGGESTION_POOL].sort(() => 0.5 - Math.random());
    setRandomSuggestions(shuffled.slice(0, 6));
  }, []);

  type ModeOptionValue = (typeof modeOptions)[number]["value"];

  useEffect(() => {
    if (searchMode !== "digging" || !isDetailedSearch || displayActivity) {
      setShowDetailedSuggestions(false);
      return;
    }

    const timer = window.setTimeout(() => setShowDetailedSuggestions(true), 100);
    return () => window.clearTimeout(timer);
  }, [displayActivity, isDetailedSearch, searchMode]);

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
          
          if (data.type === "SEARCH_SUCCESS") {
            const incoming: SavedItem[] = (data.results || []).map((rawItem: any) => {
              const item: any = rawItem.result || rawItem;
              return {
                ...item,
                id: item.id || `ws-${Math.random().toString(36).slice(2, 11)}`
              } as SavedItem;
            });

            setSearchResults(prev => {
              if (!data.is_append) return incoming;
              
              const existingIds = new Set(prev.map(i => i.id));
              const existingUrls = new Set(prev.map(i => i.url));
              const uniqueIncoming = incoming.filter((i: SavedItem) => !existingIds.has(i.id) && !existingUrls.has(i.url));
              
              return [...prev, ...uniqueIncoming];
            });
          } else if (data.type === "SEARCH_FINISHED" || data.type === "SEARCH_ERROR") {
            // Respect minimum loading display time
            const started = loadingStartRef.current || Date.now();
            const elapsed = Date.now() - started;
            const remaining = Math.max(0, MIN_LOADING_MS - elapsed);
            setTimeout(() => setLoading(false), remaining);
            if (data.type === "SEARCH_ERROR") setTimeout(() => alert(data.message || "검색 중 오류가 발생했습니다."), remaining);
          }
        } catch (err) {
          // JSON 파싱 에러 등 처리
        }
      };
    } catch (err) {
      // 연결 실패 처리
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

  // Infinite Scroll Observer
  useEffect(() => {
    const currentBottomRef = bottomRef.current;
    if (!currentBottomRef) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !loading && hasMore && searchResults.length > 0) {
          handleLoadMore();
        }
      },
      { threshold: 0.1, rootMargin: '1000px' } // 더 일찍 다음 아이템을 가져오도록 임계값 상향
    );

    observer.observe(currentBottomRef);
    return () => observer.unobserve(currentBottomRef);
  }, [loading, hasMore, searchResults.length, currentPage]);

  useEffect(() => {
    if (quotaCountdown !== null && quotaCountdown > 0) {
      const timer = setTimeout(() => setQuotaCountdown(quotaCountdown - 1), 1000);
      return () => clearTimeout(timer);
    }
    if (quotaCountdown === 0) setQuotaCountdown(null);
  }, [quotaCountdown]);

  const fetchResults = async (page: number, isAppend: boolean, queryOverride?: string, domainMapOverride?: Record<string, string> | null) => {
    const myFetchId = ++fetchCounterRef.current;
    const startedAt = Date.now();
    loadingStartRef.current = startedAt;
    setLoading(true);
    try {
      const currentQuery = queryOverride ?? searchQuery;
      const token = localStorage.getItem('access_token');
      const endpoint = searchMode === "digging" ? '/api/pse' : '/api/lens';
      
      const body: any = { query: currentQuery, page };
      const currentDomainMap = domainMapOverride ?? activeDomainMap;
      if (currentDomainMap) body.domain_map = currentDomainMap;
      // If query is a pasted data URL image, signal backend not to persist/upload it
      if (typeof currentQuery === 'string' && currentQuery.startsWith('data:')) {
        body.no_store = true;
      }

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify(body)
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
      if (searchMode === "digging" && data.success && !data.results) return;

      if (isAppend) {
        setSearchResults(prev => [...prev, ...(data.results || [])]);
        if (!data.results?.length) setHasMore(false);
      } else {
        setSearchResults(data.results || []);
        // 일반 검색(digging)은 계속해서 다음 페이지를 불러올 수 있도록 true 유지
        // AI 검색(렌즈)은 API 특성상 단일 페이지 결과만 제공하므로 더 불러오기 방지
        setHasMore(searchMode === "digging" ? true : false);
        setGeneratedImage(searchMode === "ai" ? data.generated_vibe_image_url : null);
      }
    } catch (error: any) {
      alert(error.message);
      setLoading(false);
    } finally {
      // Digging 모드(PSE)는 결과가 WebSocket으로 비동기 수신되므로, 
      // HTTP 응답 직후에 로딩을 해제하지 않고 SEARCH_FINISHED 메시지를 기다립니다.
      if (searchMode !== "digging") {
        const elapsed = Date.now() - startedAt;
        const remaining = Math.max(0, MIN_LOADING_MS - elapsed);
        setTimeout(() => {
          if (myFetchId === fetchCounterRef.current) setLoading(false);
        }, remaining);
      }
    }
  };
  
  const handlePaste = (e: React.ClipboardEvent) => {
    const items = e.clipboardData.items;
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.indexOf("image") !== -1) {
        const file = items[i].getAsFile();
        if (file) {
          const reader = new FileReader();
          reader.onload = (event) => {
            const dataUrl = event.target?.result as string;
            setPastedImage(dataUrl);
            setSearchMode("ai"); // 이미지는 렌즈 검색으로 자동 전환
          };
          reader.readAsDataURL(file);
        }
      }
    }
  };

  // 1. 엔터 쳐서 '새롭게 검색'할 때
  const handleSearch = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!user) return;

    setSearchActive(true);

    // loading will be handled inside fetchResults to ensure minimum display time
    let finalQuery = searchQuery;
    let domainMap: Record<string, string> | null = null;

    // 붙여넣은 이미지가 있는 경우 AI 모드에서 이미지 검색 우선 수행
    if (searchMode === "ai" && pastedImage) {
      setCurrentPage(1);
      return await fetchResults(1, false, pastedImage, null);
    }

    if (searchMode === "digging" && isDetailedSearch) {
      const detailParts = Object.values(detailedSearchQuery).filter(Boolean).join(" ");
      finalQuery = detailParts || searchQuery;
      if (!finalQuery.trim()) return;
      setSearchQuery(finalQuery); 
    } else if (!searchQuery.trim()) return;

    if (searchMode === "digging" && selectedShopNames.length > 0) {
      domainMap = {};
      selectedShopNames.forEach(name => {
        const shop = shops.find(s => s.name === name);
        if (shop) domainMap![getDomain(shop.url)] = shop.name;
      });
    }

    setCurrentPage(1);       // 1페이지로 리셋
    setGeneratedImage(null);
    setHasMore(true);        // 무한 스크롤 상태 리셋
    setActiveDomainMap(domainMap);
    await fetchResults(1, false, finalQuery, domainMap); // 1페이지 데이터 가져와서 덮어쓰기
  };

  // 2. '더 보기' 버튼을 눌렀을 때
  const handleLoadMore = async () => {
    if (loading || !hasMore) return;

    const nextPage = currentPage + 1;
    await fetchResults(nextPage, true); // 다음 페이지 데이터 가져와서 이어 붙이기
    setCurrentPage(nextPage);      // 성공 시 페이지 번호 1 증가
  };

  const handleSecondhandSearch = async (title: string) => {
    setSearchMode("digging");
    setIsDetailedSearch(false);
    setSearchQuery(title);
    setSearchActive(true);
    setSearchResults([]);
    const myFetchId = ++fetchCounterRef.current;
    loadingStartRef.current = Date.now();
    setLoading(true);
    setGeneratedImage(null);
    setHasMore(true); // 세컨핸드 검색 시에도 무한 스크롤이 가능하도록 true로 설정
    setCurrentPage(1);

    try {
      const token = localStorage.getItem('access_token');
      const authHeaders: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await fetch('/api/pse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({ 
          query: title, 
          page: 1,
          domain_map: { 
            "fruitsfamily.com": "후루츠패밀리",
            "collectiv.kr": "콜랙티브",
            "m.bunjang.co.kr": "번개장터"
          }
        })
      });
      if (!res.ok) throw new Error("Search failed");
      // 결과는 WebSocket(SEARCH_SUCCESS)을 통해 수신됩니다.
    } catch (err) {
      const started = loadingStartRef.current || Date.now();
      const elapsed = Date.now() - started;
      const remaining = Math.max(0, MIN_LOADING_MS - elapsed);
      setTimeout(() => {
        if (myFetchId === fetchCounterRef.current) setLoading(false);
      }, remaining);
    }
  };

  useEffect(() => {
    if (!searchSecondhandQuery || searchSecondhandTrigger === undefined) return;
    void handleSecondhandSearch(searchSecondhandQuery);
  }, [searchSecondhandQuery, searchSecondhandTrigger]);

  const applySelectedMode = (mode: ModeOptionValue) => {
    setSearchMode(mode);
    // AI 모드로 변경하거나 다른 모드로 갈 때 상세 검색창 닫기
    if (mode !== "digging") {
      setIsDetailedSearch(false);
    }
  };

  const handleSelectMode = (mode: ModeOptionValue) => {
    setIsModeMenuOpen(false);

    if (showDetailedSuggestions) {
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
      
      onItemsChange((prev) => [{
        ...item,
        id: Date.now(),
        created_at: new Date().toISOString()
      }, ...prev]);
      
      void refreshItems();

      alert("피드에 저장되었습니다!");
      await refreshTaste();
    } catch (error: any) {
      console.error(error);
      alert(error.message);
    }
  };

  const handleAddShop = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newShopData.name || !newShopData.url) return;

    const formattedUrl = newShopData.url.startsWith('http') 
      ? newShopData.url 
      : `https://${newShopData.url}`;

    const newShop = { ...newShopData, url: formattedUrl };
    setShops(prev => [newShop, ...prev]);
    setNewShopData({ name: "", url: "", desc: "" });
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

        {/* Header Section with Smooth Sticky Transition */}
        <div className={`${displayActivity ? 'sticky top-0 z-40 bg-background/95 backdrop-blur-xl -mx-4 px-4 py-6 border-b border-border/50 shadow-sm mb-12' : 'relative w-full mb-0'}`}>
          <motion.div
            className="flex w-full flex-col items-center gap-8"
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          >
          <AnimatePresence>
            {!displayActivity && (
              <motion.div
                key="search-brand"
                initial={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20, height: 0, marginBottom: 0 }}
                transition={{ duration: 0.3 }}
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

            <form onSubmit={handleSearch} className="relative group max-w-3xl w-full flex flex-col gap-4 z-50">
              <motion.div
                transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                className="relative w-full"
              >
                <div className="absolute left-3 top-1/2 z-30 -translate-y-1/2 flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => setIsModeMenuOpen((open) => !open)}
                    className={`flex h-10 w-10 items-center justify-center rounded-full transition-colors ${activeMode.activeClass}`}
                  >
                    <ActiveModeIcon className="h-5 w-5" />
                  </button>

                  {searchMode === "digging" && !displayActivity && !pastedImage && (
                    <button
                      type="button"
                      onClick={() => setIsDetailedSearch(!isDetailedSearch)}
                      className={`flex h-10 w-10 items-center justify-center rounded-full transition-all ${isDetailedSearch ? "bg-black text-white shadow-md" : "text-muted-foreground hover:bg-muted"}`}
                    >
                      <Zap className={`h-4 w-4 ${isDetailedSearch ? "fill-current" : ""}`} />
                    </button>
                  )}

                  {pastedImage && (
                    <motion.div initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} className="flex items-center gap-1 bg-black/5 p-1 rounded-lg border border-border">
                      <img src={pastedImage} className="w-8 h-8 object-cover rounded-md" />
                      <button type="button" onClick={() => setPastedImage(null)} className="p-0.5 hover:bg-black/10 rounded-full">
                        <X className="w-3 h-3 text-muted-foreground" />
                      </button>
                    </motion.div>
                  )}

                  <AnimatePresence>
                    {isModeMenuOpen && (
                      <motion.div
                        initial={{ opacity: 0, y: -8, scale: 0.98 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: -8, scale: 0.98 }}
                        className="absolute left-0 top-12 flex w-44 flex-col gap-1 rounded-2xl bg-background p-1.5 shadow-2xl border border-border z-[100]"
                      >
                        {modeOptions.map((opt) => (
                          <button
                            key={opt.value}
                            type="button"
                            onClick={() => handleSelectMode(opt.value)}
                            className={`flex h-11 items-center gap-3 rounded-xl px-3 text-left text-sm font-bold transition-all hover:bg-muted ${searchMode === opt.value ? opt.activeClass : `text-muted-foreground ${opt.hoverClass}`}`}
                          >
                            <opt.icon className="h-4 w-4" />
                            <span className="whitespace-nowrap">{opt.label}</span>
                          </button>
                        ))}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>

                <AnimatePresence mode="wait">
                  {searchMode === "digging" && isDetailedSearch && !displayActivity ? (
                    <motion.div
                      key="detail-search-panel"
                      layout
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                      className="overflow-hidden flex w-full flex-col justify-center border-b-2 border-foreground bg-transparent pl-28 pr-16"
                    >
                      {detailFields.map(({ key, placeholder, suggestions }, index) => (
                        <div key={key} className={`flex min-h-14 items-center gap-3 ${index < detailFields.length - 1 ? "border-b border-border" : ""}`}>
                          <input
                            type="text"
                            placeholder={placeholder}
                            value={detailedSearchQuery[key]}
                            onChange={(e) => setDetailedSearchQuery((prev) => ({ ...prev, [key]: e.target.value }))}
                            className="h-full min-w-0 flex-1 bg-transparent text-sm font-bold placeholder:text-muted-foreground focus:outline-none"
                          />
                          <div className="flex max-w-[14rem] gap-1.5 flex-wrap justify-end">
                            {suggestions.map((suggestion) => (
                              <button
                                key={suggestion}
                                type="button"
                                onClick={() => setDetailedSearchQuery(prev => ({ ...prev, [key]: prev[key] === suggestion ? "" : suggestion }))}
                                className={`shrink-0 rounded-full border px-3 py-1.5 text-xs font-bold transition-colors ${detailedSearchQuery[key] === suggestion ? "border-black bg-black text-white" : "border-border text-muted-foreground hover:border-black hover:text-black"}`}
                              >
                                {suggestion}
                              </button>
                            ))}
                          </div>
                        </div>
                      ))}
                    </motion.div>
                  ) : (
                    <motion.div
                      key="search-input-panel"
                      layout
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                      className="overflow-hidden relative w-full"
                    >
                      <div className="relative h-14 w-full border-b-2 border-foreground">
                        <input
                          type="text"
                          placeholder={searchMode === "digging" ? "스타일을 검색해보세요" : "이미지 검색이 가능합니다"}
                          value={pastedImage ? "" : searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                          onPaste={handlePaste}
                          className={`h-full w-full bg-transparent ${pastedImage ? 'pl-32' : 'pl-28'} pr-24 text-base font-bold placeholder:text-muted-foreground outline-none`}
                        />
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                <button
                  disabled={loading || quotaCountdown !== null}
                  className="absolute right-2 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full text-foreground hover:bg-muted disabled:opacity-50"
                >
                  {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : quotaCountdown !== null ? <span className="text-xs font-bold">{quotaCountdown}s</span> : <Search className="w-5 h-5" />}
                </button>
              </motion.div>

              {/* Selected Shops Badges Inside Form for Layout Stability */}
              <div className={`mt-2 ${selectedShopNames.length > 0 ? 'min-h-[2.25rem]' : 'min-h-0'}`}>
                <AnimatePresence>
                  {selectedShopNames.length > 0 && (
                    <motion.div initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} className="flex flex-wrap gap-2">
                      {selectedShopNames.map((name) => (
                        <div key={name} className="flex items-center gap-1.5 px-3 py-1 bg-black text-white rounded-full text-[10px] font-bold uppercase">
                          {name}
                          <button type="button" onClick={() => setSelectedShopNames(prev => prev.filter(n => n !== name))} className="hover:text-red-400">
                            <X className="w-3 h-3" />
                          </button>
                        </div>
                      ))}
                      <button type="button" onClick={() => setSelectedShopNames([])} className="text-[10px] font-bold text-muted-foreground hover:text-black uppercase underline">Clear All</button>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </form>
          </motion.div>
        </div>

        {/* 추천 검색어 영역 */}
        {!displayActivity && !isDetailedSearch && randomSuggestions.length > 0 && (
          <motion.div 
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            className="w-full max-w-3xl mx-auto flex flex-wrap gap-x-4 gap-y-2 px-1 mb-2"
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

          {/* 주요 편집샵 안내 영역 */}
          {!displayActivity && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="w-full max-w-3xl mx-auto space-y-4 pt-8"
            >
              <div className="flex items-center gap-2 px-1">
                <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground/60">Curated Shop Guide</span>
                <button
                  onClick={() => setIsAddShopModalOpen(true)}
                  className="ml-2 flex items-center gap-1 px-2 py-0.5 rounded-full border border-border bg-white text-[9px] font-bold uppercase tracking-wider text-muted-foreground hover:text-black hover:border-black transition-all"
                >
                  <Plus className="w-2.5 h-2.5" />
                  Add Shop
                </button>
                <div className="h-px flex-1 bg-border/50" />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {shops.map((shop) => (
                  <div 
                    key={`${shop.name}-${shop.url}`} 
                    className="flex items-center justify-between p-3.5 rounded-xl border border-border/60 bg-white/40 backdrop-blur-sm hover:bg-white transition-all group shadow-sm"
                  >
                    <div className="flex flex-col gap-0.5 min-w-0">
                      <span className="text-[11px] font-bold text-foreground">{shop.name}</span>
                      <span className="text-[9px] text-muted-foreground truncate">{shop.desc}</span>
                    </div>
                    <div className="flex items-center gap-3 ml-2 shrink-0">
                      <label className="flex items-center gap-2 cursor-pointer group/cb">
                        <input
                          type="checkbox"
                          checked={selectedShopNames.includes(shop.name)}
                          onChange={() => {
                            setSelectedShopNames(prev => 
                              prev.includes(shop.name) 
                                ? prev.filter(n => n !== shop.name) 
                                : [...prev, shop.name]
                            );
                          }}
                          className="w-4 h-4 rounded border-border text-black focus:ring-black cursor-pointer"
                        />
                        <span className="text-[10px] font-bold text-muted-foreground group-hover/cb:text-black transition-colors uppercase tracking-tight">선택</span>
                      </label>
                      <a
                        href={shop.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center justify-center w-7 h-7 rounded-full bg-muted group-hover:bg-black group-hover:text-white transition-colors"
                        title={`${shop.name} 이동하기`}
                      >
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          )}

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
        {(displayActivity || searchResults.length > 0) && (
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
            className="min-h-[60vh]"
          >
            <div className="w-full flex flex-col">
              <AnimatePresence>
                {loading && searchResults.length === 0 && (
                  <motion.div
                    key="loading-indicator"
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="flex flex-col items-center justify-center gap-4 py-8 overflow-hidden"
                  >
                    <div className="w-12 h-12 rounded-full border-2 border-muted border-t-foreground animate-spin" />
                    <p style={{ whiteSpace: 'pre-line' }} className="text-sm font-bold text-muted-foreground text-center">
                      {searchMode === "digging"
                        ? "Searching..."
                        : searchMode === "ai"
                        ? "AI가 유저 취향에 맞는 느좋탬들을 디깅하는 중..."
                        : "Analyzing..."}
                    </p>
                  </motion.div>
                )}

                {loading && searchResults.length > 0 && (
                  <motion.div
                    key="loading-inline"
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="mb-4 rounded-2xl border border-border/60 bg-muted/70 px-4 py-3 text-sm font-semibold text-muted-foreground"
                  >
                    {searchMode === "digging"
                      ? `계속 불러오는 중... (${searchResults.length}개 검색됨)`
                      : "AI가 추가 결과를 준비하고 있어요..."}
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

              {/* Orderly Grid Layout: Left to Right, Top to Bottom */}
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
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
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4 mt-4">
                  {Array.from({ length: Math.max(5, 10 - searchResults.length) }).map((_, i) => (
                    <div key={`skeleton-${i}`} className="relative">
                      <div 
                        className="w-full bg-muted rounded-2xl animate-pulse" 
                        style={{ 
                          aspectRatio: '3/4'
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

      {/* Add Shop Modal */}
      <AnimatePresence>
        {isAddShopModalOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsAddShopModalOpen(false)}
              className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="fixed left-1/2 top-1/2 z-[101] w-full max-w-md -translate-x-1/2 -translate-y-1/2 p-4"
            >
              <div className="rounded-3xl border border-border bg-background p-6 shadow-2xl sm:p-8">
                <div className="mb-6 flex items-center justify-between">
                  <h3 className="text-xl font-bold tracking-tight text-foreground">새 사이트 추가</h3>
                  <button onClick={() => setIsAddShopModalOpen(false)} className="rounded-full p-2 hover:bg-muted transition-colors">
                    <X className="h-5 w-5 text-muted-foreground" />
                  </button>
                </div>
                <form onSubmit={handleAddShop} className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">사이트명</label>
                    <input
                      required
                      type="text"
                      placeholder="예: POSE SELECT"
                      value={newShopData.name}
                      onChange={(e) => setNewShopData(prev => ({ ...prev, name: e.target.value }))}
                      className="w-full rounded-xl border border-border bg-muted/50 px-4 py-3 text-sm font-medium focus:border-black focus:outline-none transition-colors"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">URL</label>
                    <input
                      required
                      type="text"
                      placeholder="https://..."
                      value={newShopData.url}
                      onChange={(e) => setNewShopData(prev => ({ ...prev, url: e.target.value }))}
                      className="w-full rounded-xl border border-border bg-muted/50 px-4 py-3 text-sm font-medium focus:border-black focus:outline-none transition-colors"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">설명 (선택)</label>
                    <input
                      type="text"
                      placeholder="간단한 사이트 설명을 적어주세요"
                      value={newShopData.desc}
                      onChange={(e) => setNewShopData(prev => ({ ...prev, desc: e.target.value }))}
                      className="w-full rounded-xl border border-border bg-muted/50 px-4 py-3 text-sm font-medium focus:border-black focus:outline-none transition-colors"
                    />
                  </div>
                  <button
                    type="submit"
                    className="mt-4 w-full rounded-full bg-black py-4 text-sm font-bold tracking-widest text-white transition-opacity hover:opacity-90 uppercase"
                  >
                    추가 완료
                  </button>
                </form>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
