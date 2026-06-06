import { motion, AnimatePresence } from 'framer-motion';
import { Search, Loader2, Sparkles, BrainCircuit, Zap, X, Plus, Music, ExternalLink } from 'lucide-react';
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
  const [detailedSearchQuery, setDetailedSearchQuery] = useState({ mood: "", color: "", fit: "", category: "" , brand: "", site: "" });
  const [randomSuggestions, setRandomSuggestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [quotaCountdown, setQuotaCountdown] = useState<number | null>(null);
  const [searchResults, setSearchResults] = useState<SavedItem[]>([]);
  const [activeDomainMap, setActiveDomainMap] = useState<Record<string, string> | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [isModeMenuOpen, setIsModeMenuOpen] = useState(false);
  const [showDetailedSuggestions, setShowDetailedSuggestions] = useState(false);
  const hasSearchActivity = loading || searchResults.length > 0 || quotaCountdown !== null;
  const [isAddShopModalOpen, setIsAddShopModalOpen] = useState(false);
  const [newShopData, setNewShopData] = useState({ name: "", url: "", desc: "" });
  const [isPlayerOpen, setIsPlayerOpen] = useState(false);
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
    { key: "site", placeholder: "사이트", suggestions: [] }
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

  const fetchResults = async (page: number, isAppend: boolean, queryOverride?: string, domainMapOverride?: Record<string, string> | null) => {
    setLoading(true);
    try {
      let res;
      const currentQuery = queryOverride !== undefined ? queryOverride : searchQuery;

      const token = localStorage.getItem('access_token');
      const authHeaders: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
      const endpoint = searchMode === "digging" ? '/api/pse' : '/api/lens';
      
      const body: any = { query: currentQuery, page: page };
      const currentDomainMap = domainMapOverride !== undefined ? domainMapOverride : activeDomainMap;
      if (currentDomainMap) body.domain_map = currentDomainMap;

      res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
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
            if (!searchQuery) setSearchQuery("Pasted Image");
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

    let finalQuery = searchQuery;
    let domainMap: Record<string, string> | null = null;

    // 붙여넣은 이미지가 있는 경우 AI 모드에서 이미지 검색 우선 수행
    if (searchMode === "ai" && pastedImage) {
      setCurrentPage(1);
      setSearchResults([]);
      await fetchResults(1, false, pastedImage, null);
      return;
    }

    if (searchMode === "digging" && isDetailedSearch) {
      const detailParts = [
        detailedSearchQuery.mood,
        detailedSearchQuery.color,
        detailedSearchQuery.fit,
        detailedSearchQuery.category,
        detailedSearchQuery.brand
      ].filter(Boolean).join(" ");
      
      // 상세 필드가 비어있으면 메인 검색어 사용
      finalQuery = detailParts || searchQuery;
      
      if (detailedSearchQuery.site) {
        const shop = shops.find(s => s.name === detailedSearchQuery.site);
        if (shop) {
          let domain = "";
          try { domain = new URL(shop.url).hostname.replace('www.', ''); }
          catch (e) { domain = shop.url.replace('https://', '').replace('http://', '').split('/')[0]; }
          domainMap = { [domain]: shop.name };
        }
      }

      if (!finalQuery.trim()) return;
      if (detailParts) setSearchQuery(finalQuery); 
    } else {
      if (!searchQuery) return;
    }

    setCurrentPage(1);       // 1페이지로 리셋
    setSearchResults([]);    // 기존 화면 싹 지우기
    setGeneratedImage(null);
    setHasMore(true);        // 무한 스크롤 상태 리셋
    setActiveDomainMap(domainMap);
    await fetchResults(1, false, finalQuery, domainMap); // 1페이지 데이터 가져와서 덮어쓰기
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
    } catch (error: any) {
      alert(error.message);
      setLoading(false);
    }
  };

  const handleShopSearch = (name: string) => {
    // UI 상태 업데이트
    setSearchMode("digging");
    setIsDetailedSearch(true);
    setDetailedSearchQuery(prev => ({ ...prev, site: name }));
    
    // 입력창으로 포커스를 유도하기 위해 최상단으로 스크롤
    window.scrollTo({ top: 0, behavior: 'smooth' });
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
        className={[
          "relative",
          "mx-auto flex w-full flex-col transition-[max-width] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
          hasSearchActivity ? "max-w-6xl" : "max-w-4xl",
        hasSearchActivity ? "space-y-8 py-8 pb-40" : "min-h-[110vh] pt-20 pb-60",
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
            <div className="absolute left-3 top-1/2 z-30 -translate-y-1/2 flex items-center gap-1.5">
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

              {searchMode === "digging" && !hasSearchActivity && !pastedImage && (
                <button
                  type="button"
                  onClick={() => setIsDetailedSearch(!isDetailedSearch)}
                  className={`flex h-10 w-10 items-center justify-center rounded-full transition-all ${
                    isDetailedSearch 
                      ? "bg-black text-white shadow-md" 
                      : "text-muted-foreground hover:bg-muted"
                  }`}
                  title={isDetailedSearch ? "일반 검색으로 전환" : "상세 검색으로 전환"}
                >
                  <Zap className={`h-4 w-4 ${isDetailedSearch ? "fill-current" : ""}`} />
                </button>
              )}

              {pastedImage && (
                <motion.div 
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="flex items-center gap-1 bg-black/5 p-1 rounded-lg border border-border group/preview"
                >
                  <img src={pastedImage} className="w-8 h-8 object-cover rounded-md" />
                  <button 
                    type="button"
                    onClick={() => { setPastedImage(null); if (searchQuery === "Pasted Image") setSearchQuery(""); }}
                    className="p-0.5 hover:bg-black/10 rounded-full transition-colors"
                  >
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
                animate={{ height: 360 }}
                transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
                className="flex w-full flex-col justify-center border-b-2 border-foreground bg-transparent py-0 pl-28 pr-16"
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
                className="w-full border-b-2 border-foreground bg-transparent transition-all duration-300"
              >
                <input
                  type="text"
                  placeholder={
                    searchMode === "digging"
                      ? isDetailedSearch ? "상세 조건을 입력하세요" : "원하는 스타일을 검색해보세요 (예: 디스트로이드 데님)"
                      : "떠오르는 스타일을 자유롭게 입력해보세요"
                  }
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onPaste={handlePaste}
                  disabled={searchMode === "digging" && isDetailedSearch}
                  className={`h-full w-full rounded-full bg-transparent ${pastedImage ? 'pl-32' : (searchMode === 'digging' && !hasSearchActivity ? 'pl-28' : 'pl-16')} pr-24 text-base font-bold placeholder:text-muted-foreground outline-0 transition-all ${isDetailedSearch ? 'opacity-0' : 'opacity-100'}`}
                />
              </motion.div>
            )}

            <div className="absolute right-12 top-1/2 -translate-y-1/2 flex items-center">
              <button
                type="button"
                onClick={() => setIsPlayerOpen(!isPlayerOpen)}
                title="Shopping Playlist"
                className="flex h-10 w-10 items-center justify-center rounded-full text-muted-foreground hover:text-black hover:bg-muted transition-colors"
              >
                <Music className="w-4 h-4" />
                <span className="absolute -top-1 -right-1 flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-black opacity-20"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-black/10"></span>
                </span>
              </button>

              <AnimatePresence>
                {isPlayerOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: 10, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 10, scale: 0.95 }}
                    className="absolute right-0 top-12 z-[100] w-72 overflow-hidden rounded-2xl border border-border bg-background shadow-2xl"
                  >
                    <div className="flex items-center justify-between border-b border-border p-3">
                      <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-2">
                        <Music className="w-3 h-3" /> RoomShow Selects
                      </span>
                      <button onClick={() => setIsPlayerOpen(false)} className="rounded-full p-1 hover:bg-muted">
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                    <div className="aspect-video w-full bg-black">
                      <iframe
                        width="100%"
                        height="100%"
                        src="https://www.youtube.com/embed/videoseries?list=PL4fGSI1pDJn6jWqsS_4v6n_33p_D3l4a6"
                        title="Zara Playlist"
                        frameBorder="0"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                        allowFullScreen
                        className="opacity-90"
                      ></iframe>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <button
              disabled={loading || quotaCountdown !== null}
              className="absolute right-2 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full text-foreground transition-colors hover:bg-muted disabled:opacity-50"
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : quotaCountdown !== null ? <span className="text-xs font-bold">{quotaCountdown}s</span> : <Search className="w-5 h-5" />}
            </button>
          </motion.div>
          </form>

          {/* 추천 검색어 영역 */}
          {!hasSearchActivity && !isDetailedSearch && randomSuggestions.length > 0 && (
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

          {/* 주요 편집샵 안내 영역 */}
          {!hasSearchActivity && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="w-full max-w-3xl space-y-4 pt-8"
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
                    <div className="flex items-center gap-2 ml-2 shrink-0">
                      <button
                        type="button"
                        onClick={() => handleShopSearch(shop.name)}
                        className="px-2 py-1 text-[9px] font-bold text-muted-foreground border border-border rounded-md hover:bg-black hover:text-white hover:border-black transition-colors uppercase tracking-wider"
                      >
                        이 편집샵에서 검색하기
                      </button>
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
