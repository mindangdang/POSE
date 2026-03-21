import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Search, 
  Plus, 
  Grid, 
  User, 
  Sparkles, 
  Trash2, 
  ExternalLink, 
  Loader2,
  Instagram,
  Compass,
  Heart,
  MessageSquare,
  LogOut,
  X,
  ThumbsUp,
  ThumbsDown,
  Send,
  Zap
} from 'lucide-react';
import Markdown from 'react-markdown';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface SavedItem {
  id: number;
  url: string;
  category: string;
  facts: Record<string, unknown> | string | null;
  reviews?: Record<string, unknown> | null;
  vibe: string;
  image_url: string;
  created_at: string;
  summary_text?: string;
}

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export default function App() {
  const [user] = useState<{ id: number; username: string }>({ id: 1, username: 'guest' });
  const [items, setItems] = useState<SavedItem[]>([]);
  const [selectedItem, setSelectedItem] = useState<SavedItem | null>(null);
  const [taste, setTaste] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [newUrl, setNewUrl] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<string | null>(null);
  const [quotaCountdown, setQuotaCountdown] = useState<number | null>(null);
  const [isSavingSearch, setIsSavingSearch] = useState(false);
  const [feedbackType, setFeedbackType] = useState<'like' | 'dislike' | null>(null);
  const [feedbackReason, setFeedbackReason] = useState("");
  const [showFeedbackReason, setShowFeedbackReason] = useState(false);
  const [activeTab, setActiveTab] = useState<'feed' | 'search' | 'profile'>('feed');
  const [isGeneratingTaste, setIsGeneratingTaste] = useState(false); 
  const [isSharingProfile, setIsSharingProfile] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string>('All'); 

  const factKeysToShow = ['title', 'price_info', 'location_text', 'time_info', 'key_details'];

  useEffect(() => {
    if (user) {
      fetchItems();
      fetchTaste();
    }
  }, [user]);

  useEffect(() => {
    if (quotaCountdown !== null && quotaCountdown > 0) {
      const timer = setTimeout(() => setQuotaCountdown(quotaCountdown - 1), 1000);
      return () => clearTimeout(timer);
    } else if (quotaCountdown === 0) {
      setQuotaCountdown(null);
    }
  }, [quotaCountdown]);

  const categories = ['All', ...Array.from(new Set(items.map(item => item.category))).filter(Boolean)];
  
  const filteredItems = selectedCategory === 'All' 
    ? items 
    : items.filter(item => item.category === selectedCategory);

  const fetchItems = async () => {
    if (!user) return;
    try {
      const res = await fetch(`/api/items?user_id=${user.id}`, { cache: 'no-store' });
      const data = await res.json();
      setItems(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error("Failed to fetch items:", error);
      setItems([]);
    }
  };

  const fetchTaste = async () => {
    if (!user) return;
    try {
      const res = await fetch(`/api/taste?user_id=${user.id}`, { cache: 'no-store' });
      const data = await res.json();
      setTaste(data?.summary || "");
    } catch (error) {
      console.error("Failed to fetch taste:", error);
      setTaste("");
    }
  };

  const handleGenerateTaste = async () => {
    setIsGeneratingTaste(true);
    try {
      const res = await fetch('/api/generate-taste', { method: 'POST' });
      const data = await res.json();
      
      if (data.success) {
        setTaste(data.summary);
      } else {
        alert(data.message || "취향 분석에 실패했습니다.");
      }
    } catch (error) {
      console.error("Taste generation failed:", error);
      alert("취향 분석 중 에러가 발생했습니다.");
    } finally {
      setIsGeneratingTaste(false);
    }
  }; 

  const handleShareProfile = async () => {
    if (!taste) {
      alert('먼저 취향 프로필을 생성해 주세요.');
      return;
    }

    const shareText = `My POSE! 취향 프로필\n\n닉네임: ${user?.username || 'Anonymous'}\n\n${taste}\n\n#POSE #취향프로필 #Aesthetic`;

    setIsSharingProfile(true);
    try {
      if (navigator.share) {
        await navigator.share({
          title: '내 취향 프로필',
          text: shareText,
        });
      } else if (navigator.clipboard) {
        await navigator.clipboard.writeText(shareText);
        alert('취향 프로필 텍스트가 클립보드에 복사되었습니다. 인스타그램에서 붙여넣기 후 공유하세요.');
        window.open('https://www.instagram.com/', '_blank');
      } else {
        alert('공유를 지원하지 않는 환경입니다. 취향 텍스트를 수동으로 복사하여 인스타그램에 공유해주세요.');
      }
    } catch (error) {
      console.error('Profile share failed:', error);
      alert('프로필 공유 중 오류가 발생했습니다.');
    } finally {
      setIsSharingProfile(false);
    }
  };

  const handleAddItem = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUrl || !user) return;
    setLoading(true);
    try {
      const res = await fetch('/api/extract-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: newUrl, session_id: sessionId, user_id: user.id })
      });
      
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || "Failed to analyze URL");
      }
      
      // 🌟 Optimistic UI: 응답 데이터 즉시 state에 추가 (새로고침 없음)
      const responseData = await res.json();
      if (responseData.success && responseData.data && Array.isArray(responseData.data)) {
        const newItems = responseData.data.map((item: any, index: number) => ({
          id: Date.now() + index,
          url: newUrl,
          category: item.category || 'General',
          facts: item.facts || {},
          reviews: item.reviews || null,
          vibe: item.vibe_text || 'Extracted',
          image_url: item.image_url || '',
          created_at: new Date().toISOString(),
          summary_text: item.summary_text || ''
        }));
        setItems([...newItems, ...items]);
      }
      
      setNewUrl("");
      await fetchTaste();
    } catch (error: any) {
      console.error(error);
      alert("분석 중 일부 오류가 발생했습니다. 저장된 데이터만 확인합니다.");
      await fetchItems();
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!user) return;
    
    // 🌟 Optimistic UI: 먼저 UI에서 제거 (즉각 업데이트)
    const previousItems = items;
    setItems(items.filter(item => item.id !== id));
    
    try {
      await fetch(`/api/items/${id}?user_id=${user.id}`, { method: 'DELETE' });
    } catch (error) {
      console.error('Delete failed:', error);
      setItems(previousItems);
      alert('삭제 중 오류가 발생했습니다.');
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery || !user) return;
    setLoading(true);
    setSearchResults(null);
    setFeedbackType(null);
    setFeedbackReason("");
    setShowFeedbackReason(false);
    try {
      const res = await fetch('/api/agent-search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: searchQuery }) 
      });
      const data = await res.json();
      if (res.status === 429) {
        setQuotaCountdown(60); 
        return;
      }
      if (!res.ok) throw new Error(data.detail || "Search failed");
      setSearchResults(data.result || null);
    } catch (error: any) {
      console.error(error);
      alert(error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (type: 'like' | 'dislike') => {
    if (!user || !searchResults) return;
    setFeedbackType(type);
    setShowFeedbackReason(true);

    if (type === 'like') {
      await handleSaveSearchResult(true);
    }
  };

  const submitFeedbackReason = async () => {
    if (!user || !searchResults || !feedbackType) return;
    try {
      await fetch('/api/agentic-search/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: user.id,
          query: searchQuery,
          result: searchResults,
          feedback_type: feedbackType,
          reason: feedbackReason
        })
      });
      setShowFeedbackReason(false);
      setFeedbackReason("");
      await fetchTaste();
    } catch (error) {
      console.error("Failed to submit feedback:", error);
    }
  };

  const handleSaveSearchResult = async (silent = false) => {
    if (!searchResults || !user) return;
    setIsSavingSearch(true);
    try {
      const res = await fetch('/api/items/manual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          user_id: user.id,
          category: "INSPIRATION",
          vibe: `Agentic Search Result: ${searchQuery}`,
          facts: { content: searchResults },
          url: "agentic-search"
        })
      });
      
      if (!res.ok) throw new Error("Failed to save result");
      
      // Optimistic UI: 새로고침 없이 state 즉시 업데이트
      const newItem: SavedItem = {
        id: Date.now(),
        url: "agentic-search",
        category: "INSPIRATION",
        facts: { content: searchResults },
        reviews: null,
        vibe: `Agentic Search Result: ${searchQuery}`,
        image_url: '',
        created_at: new Date().toISOString(),
        summary_text: searchResults.substring(0, 100)
      };
      setItems([newItem, ...items]);
      
      if (!silent) alert("Saved to your feed!");
      await fetchTaste();
    } catch (error: any) {
      console.error(error);
      if (!silent) alert(error.message);
    } finally {
      setIsSavingSearch(false);
    }
  };

  return (
    <div className="min-h-screen bg-white text-black font-sans flex selection:bg-yellow-300 selection:text-black">
      {/* Sidebar Navigation */}
      <nav className="w-20 md:w-64 border-r border-black/10 h-screen sticky top-0 bg-white flex flex-col p-4 z-10">
        <div className="mb-12 px-2 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-500 via-yellow-300 to-purple-500 p-[2px] shadow-sm shrink-0">
            <div className="w-full h-full bg-black rounded-[10px] flex items-center justify-center">
              <Zap className="w-5 h-5 text-white" fill="white" />
            </div>
          </div>
          <h1 className="text-3xl font-black tracking-tighter uppercase hidden md:block">
            POSE!
          </h1>
        </div>

        <div className="space-y-3 flex-1">
          <NavItem 
            icon={<Grid className="w-5 h-5" />} 
            label="Feed" 
            active={activeTab === 'feed'} 
            onClick={() => setActiveTab('feed')} 
          />
          <NavItem 
            icon={<Search className="w-5 h-5" />} 
            label="Agentic Search" 
            active={activeTab === 'search'} 
            onClick={() => setActiveTab('search')} 
          />
          <NavItem 
            icon={<User className="w-5 h-5" />} 
            label="Taste Profile" 
            active={activeTab === 'profile'} 
            onClick={() => setActiveTab('profile')} 
          />
        </div>

        <div className="mt-auto space-y-2">
          <div className="flex items-center gap-3 p-3 w-full rounded-2xl bg-gray-50 border border-black/5">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-500 via-yellow-300 to-purple-500 p-[2px]">
              <div className="w-full h-full bg-white rounded-full"></div>
            </div>
            <span className="hidden md:block font-bold text-sm tracking-tight">@{user.username}</span>
          </div>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="flex-1 max-w-5xl mx-auto p-4 md:p-8 overflow-x-hidden">
        <AnimatePresence mode="wait">
          {activeTab === 'feed' && (
            <motion.div
              key="feed"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-8"
            >
              <header className="flex flex-col xl:flex-row xl:items-end justify-between gap-6">
                <div>
                  <h2 className="text-4xl font-black tracking-tighter uppercase">My POSE! Feed</h2>
                  <p className="text-gray-500 font-medium mt-1">Capture the vibes that define you.</p>
                </div>
                <form onSubmit={handleAddItem} className="flex flex-col sm:flex-row gap-2 items-end w-full xl:w-auto">
                  <div className="flex-1 w-full xl:w-64 space-y-1.5">
                    <label className="text-[10px] font-black text-gray-400 uppercase tracking-widest">Instagram URL</label>
                    <input
                      type="url"
                      placeholder="Paste link..."
                      value={newUrl}
                      onChange={(e) => setNewUrl(e.target.value)}
                      className="w-full px-4 py-3 bg-gray-50 border-none rounded-2xl focus:outline-none focus:ring-2 focus:ring-black text-sm font-medium transition-all"
                    />
                  </div>
                  <div className="w-full sm:w-48 space-y-1.5">
                    <label className="text-[10px] font-black text-gray-400 uppercase tracking-widest">Session ID</label>
                    <input
                      type="password"
                      placeholder="sessionid"
                      value={sessionId}
                      onChange={(e) => setSessionId(e.target.value)}
                      className="w-full px-4 py-3 bg-gray-50 border-none rounded-2xl focus:outline-none focus:ring-2 focus:ring-black text-sm font-medium transition-all"
                    />
                  </div>
                  <button
                    disabled={loading}
                    className="w-full sm:w-auto px-8 py-3 bg-black text-white rounded-2xl hover:bg-gray-800 hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-50 disabled:transform-none transition-all flex items-center justify-center gap-2 text-sm font-black tracking-widest uppercase h-[44px]"
                  >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                    Add
                  </button>
                </form>
              </header>

              {/* 카테고리 필터 버튼 영역 */}
              {items.length > 0 && (
                <div className="flex flex-wrap gap-2 py-2">
                  {categories.map(cat => (
                    <button
                      key={cat}
                      onClick={() => setSelectedCategory(cat)}
                      className={cn(
                        "px-5 py-2 rounded-full text-[11px] font-black uppercase tracking-widest transition-all",
                        selectedCategory === cat 
                          ? "bg-black text-white shadow-md scale-105" 
                          : "bg-gray-100 text-gray-500 hover:bg-gray-200"
                      )}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              )}

              {/* Pinterest-like Grid */}
              <div className="columns-2 md:columns-3 lg:columns-4 gap-4 space-y-4 mt-4">
                {Array.isArray(filteredItems) && filteredItems.map((item) => (
                  <motion.div
                    layout
                    key={item.id}
                    onClick={() => setSelectedItem(item)}
                    className="break-inside-avoid group relative bg-white rounded-3xl overflow-hidden border border-black/5 hover:shadow-2xl hover:-translate-y-1 transition-all duration-300 cursor-pointer"
                  >
                    <div className="relative overflow-hidden">
                      <img
                        src={item.image_url?.startsWith('http') ? item.image_url : item.image_url ? `/api/images/${item.image_url}` : 'https://via.placeholder.com/400x500?text=POSE+Not+Found'}
                        alt={item.category}
                        className="w-full h-auto object-cover transform group-hover:scale-105 transition-transform duration-700"
                        referrerPolicy="no-referrer"
                        onError={(e) => {
                          (e.target as HTMLImageElement).src = 'https://via.placeholder.com/400x500?text=POSE+Not+Found';
                        }}
                      />
                      <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                    </div>
                    <div className="p-4 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-[9px] font-black uppercase tracking-widest text-blue-600 bg-blue-50 px-2 py-1 rounded-md">
                          {item.category}
                        </span>
                        <button 
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(item.id);
                          }}
                          className="opacity-0 group-hover:opacity-100 p-1.5 bg-red-50 text-red-500 rounded-full hover:bg-red-100 transition-all"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                      <p className="text-sm font-bold leading-tight line-clamp-2 text-black">{item.vibe}</p>

                      {item.facts && typeof item.facts === 'object' && (
                        <>
                          {Object.entries(item.facts).filter(([key]) => factKeysToShow.includes(key.toLowerCase())).length > 0 && (
                            <div className="space-y-1.5 mt-3 border-t border-gray-100 pt-3">
                              {Object.entries(item.facts)
                                .filter(([key]) => factKeysToShow.includes(key.toLowerCase()))
                                .map(([key, value]) => (
                                  <div key={key} className="flex flex-col gap-0.5">
                                    <span className="text-[8px] font-black text-gray-400 uppercase tracking-widest">{key.replace(/_/g, ' ')}</span>
                                    <p className="text-[11px] text-gray-600 line-clamp-1 font-medium">
                                      {Array.isArray(value) ? value.join(', ') : String(value)}
                                    </p>
                                  </div>
                                ))}
                            </div>
                          )}
                        </>
                      )}

                      <div className="pt-3 flex items-center gap-2">
                        {item.url && item.url.startsWith('http') ? (
                          <a 
                            href={item.url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="text-[10px] font-bold text-gray-400 hover:text-black flex items-center gap-1 transition-colors"
                          >
                            <Instagram className="w-3 h-3" /> View Source
                          </a>
                        ) : (
                          <span className="text-[10px] font-bold text-gray-400 flex items-center gap-1">
                            <Sparkles className="w-3 h-3" /> AI Curated
                          </span>
                        )}
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
              
              {items.length === 0 && !loading && (
                <div className="text-center py-32 bg-gray-50 rounded-[3rem] border-2 border-dashed border-gray-200">
                  <div className="w-20 h-20 bg-white rounded-full flex items-center justify-center mx-auto mb-6 shadow-sm">
                    <Zap className="w-10 h-10 text-yellow-400" fill="currentColor" />
                  </div>
                  <h3 className="text-2xl font-black tracking-tight mb-2">Strike your first POSE!</h3>
                  <p className="text-gray-500 font-medium">인스타그램 링크를 넣고 나만의 바이브를 수집하세요.</p>
                </div>
              )}
            </motion.div>
          )}

          {activeTab === 'search' && (
            <motion.div
              key="search"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="max-w-3xl mx-auto space-y-12 py-12"
            >
              <div className="text-center space-y-4">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-tr from-blue-500 via-yellow-300 to-purple-500 p-[2px] mb-4">
                  <div className="w-full h-full bg-black rounded-[14px] flex items-center justify-center">
                    <Search className="w-8 h-8 text-white" />
                  </div>
                </div>
                <h2 className="text-4xl font-black tracking-tighter uppercase">POSE! Search</h2>
                <p className="text-gray-500 font-medium">당신의 취향을 기반으로 새로운 영감을 찾아냅니다.</p>
              </div>

              <form onSubmit={handleSearch} className="relative group">
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
                  className="text-center p-4 bg-red-50 text-red-600 rounded-2xl border border-red-100 text-sm font-bold tracking-tight"
                >
                  토큰이 부족합니다. {quotaCountdown}초 뒤에 다시 시도하세요.
                </motion.div>
              )}

              {searchResults && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="bg-white p-8 md:p-10 rounded-[3rem] border border-black/5 shadow-xl shadow-gray-100 prose prose-sm max-w-none relative"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6 mb-8 pb-8 border-b border-gray-100">
                    <div className="flex items-center gap-3 text-xs font-black uppercase tracking-widest text-black">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-500 via-yellow-300 to-purple-500 p-[2px]">
                        <div className="w-full h-full bg-black rounded-full flex items-center justify-center">
                          <Sparkles className="w-4 h-4 text-white" />
                        </div>
                      </div>
                      Curated Results
                    </div>
                    <div className="flex items-center gap-2 bg-gray-50 p-1.5 rounded-2xl">
                      <button
                        onClick={() => handleFeedback('like')}
                        className={cn(
                          "flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs font-black tracking-widest uppercase transition-all",
                          feedbackType === 'like' 
                            ? "bg-black text-white shadow-md" 
                            : "bg-transparent text-gray-500 hover:bg-white hover:shadow-sm"
                        )}
                      >
                        <ThumbsUp className="w-3.5 h-3.5" /> Like
                      </button>
                      <button
                        onClick={() => handleFeedback('dislike')}
                        className={cn(
                          "flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs font-black tracking-widest uppercase transition-all",
                          feedbackType === 'dislike' 
                            ? "bg-red-500 text-white shadow-md" 
                            : "bg-transparent text-gray-500 hover:bg-white hover:shadow-sm"
                        )}
                      >
                        <ThumbsDown className="w-3.5 h-3.5" /> Dislike
                      </button>
                    </div>
                  </div>

                  <AnimatePresence>
                    {showFeedbackReason && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="mb-8 overflow-hidden"
                      >
                        <div className="p-6 bg-gray-50 rounded-3xl border border-gray-100 space-y-4">
                          <p className="text-sm font-black text-black uppercase tracking-tight">
                            {feedbackType === 'like' ? "What caught your eye?" : "How can we improve?"}
                          </p>
                          <div className="flex flex-col sm:flex-row gap-3">
                            <input
                              type="text"
                              placeholder="Leave a quick note..."
                              value={feedbackReason}
                              onChange={(e) => setFeedbackReason(e.target.value)}
                              className="flex-1 px-5 py-3 bg-white border-none rounded-2xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-black shadow-sm"
                            />
                            <button
                              onClick={submitFeedbackReason}
                              className="px-8 py-3 bg-black text-white rounded-2xl text-xs font-black tracking-widest uppercase hover:bg-gray-800 transition-all flex items-center justify-center gap-2 h-[48px] sm:h-auto"
                            >
                              <Send className="w-3.5 h-3.5" /> Submit
                            </button>
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  <div className="markdown-body prose-headings:font-black prose-headings:tracking-tighter prose-a:text-blue-600 prose-a:font-bold">
                    <Markdown>{searchResults}</Markdown>
                  </div>
                </motion.div>
              )}
            </motion.div>
          )}

          {activeTab === 'profile' && (
            <motion.div
              key="profile"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="max-w-4xl mx-auto space-y-16 py-8"
            >
              <div className="flex flex-col md:flex-row items-start md:items-end justify-between gap-8 border-b border-black/10 pb-12">
                <div className="space-y-5">
                  <div className="w-28 h-28 rounded-full bg-gradient-to-tr from-blue-600 via-yellow-300 to-purple-600 p-[3px] shadow-2xl">
                    <div className="w-full h-full bg-white rounded-full flex items-center justify-center overflow-hidden">
                      <User className="w-12 h-12 text-black" />
                    </div>
                  </div>
                  <div className="space-y-1">
                    <h2 className="text-5xl font-black tracking-tighter text-black uppercase">
                      {user?.username || 'Anonymous'}
                    </h2>
                    <p className="text-xs font-black text-gray-400 uppercase tracking-widest bg-gray-100 inline-block px-3 py-1 rounded-full">
                      POSE Creator No. {user?.id || '000'}
                    </p>
                  </div>
                </div>
                <div className="text-left md:text-right max-w-xs">
                  <p className="text-2xl font-black text-black leading-tight tracking-tighter uppercase bg-clip-text text-transparent bg-gradient-to-r from-black to-gray-500">
                    "My Vibe is<br/>my POSE."
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">
                <div className="lg:col-span-4 space-y-6">
                  <div className="flex items-center gap-3 text-[10px] font-black uppercase tracking-[0.3em] text-blue-600">
                    <Zap className="w-3.5 h-3.5" fill="currentColor" />
                    Taste Analysis
                  </div>
                  <h3 className="text-3xl font-black tracking-tighter leading-none uppercase">
                    The Patterns<br/>of your<br/>Choices.
                  </h3>
                  <div className="h-2 w-12 bg-black rounded-full" />
                </div>

                <div className="lg:col-span-8">
                  {taste ? (
                    <div className="bg-gray-50 p-8 md:p-12 rounded-[3rem] border border-black/5">
                      <div className="markdown-body font-medium text-gray-800 text-lg leading-relaxed prose-p:mb-6 prose-strong:font-black prose-strong:text-black">
                        <Markdown>{taste}</Markdown>
                      </div>
                      
                      <div className="mt-12 pt-8 border-t border-gray-200 flex flex-wrap items-center justify-end gap-3">
                        <button 
                          onClick={handleGenerateTaste}
                          disabled={isGeneratingTaste}
                          className="flex items-center gap-2 px-6 py-3 bg-white hover:bg-gray-100 text-black rounded-2xl text-xs font-black tracking-widest uppercase transition-all shadow-sm"
                        >
                          {isGeneratingTaste ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                          {isGeneratingTaste ? 'Analyzing...' : 'Re-Analyze'}
                        </button>
                        <button 
                          onClick={handleShareProfile}
                          disabled={isSharingProfile}
                          className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white rounded-2xl text-xs font-black tracking-widest uppercase transition-all shadow-lg shadow-purple-500/30"
                        >
                          {isSharingProfile ? <Loader2 className="w-4 h-4 animate-spin" /> : <Instagram className="w-4 h-4" />}
                          {isSharingProfile ? 'Preparing...' : 'Share to IG'}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="py-24 bg-gray-50 rounded-[3rem] flex flex-col items-center justify-center text-center space-y-8 px-4 border-2 border-dashed border-gray-200">
                      <div className="w-20 h-20 bg-white rounded-full flex items-center justify-center shadow-sm">
                        <Sparkles className="w-8 h-8 text-yellow-400" fill="currentColor" />
                      </div>
                      
                      {items.length > 0 ? (
                        <div className="space-y-6 flex flex-col items-center">
                          <p className="text-gray-500 font-bold text-lg max-w-sm">
                            충분한 영감이 모였습니다.<br/>당신의 무의식적인 패턴을 꺼내볼까요?
                          </p>
                          <button 
                            onClick={handleGenerateTaste}
                            disabled={isGeneratingTaste}
                            className="px-10 py-4 bg-black text-white rounded-full text-sm font-black tracking-widest uppercase hover:bg-gray-800 hover:scale-105 active:scale-95 transition-all flex items-center gap-3 disabled:opacity-50 shadow-xl"
                          >
                            {isGeneratingTaste ? <Loader2 className="w-5 h-5 animate-spin" /> : <Zap className="w-5 h-5 text-yellow-400" fill="currentColor" />}
                            {isGeneratingTaste ? 'Analyzing POSE...' : 'Analyze My POSE'}
                          </button>
                        </div>
                      ) : (
                        <div className="space-y-6 flex flex-col items-center">
                          <p className="text-gray-400 font-bold text-lg">아직 수집된 영감이 없습니다.</p>
                          <button 
                            onClick={() => setActiveTab('feed')}
                            className="px-8 py-3 bg-white border-2 border-gray-200 text-black rounded-full text-xs font-black uppercase tracking-widest hover:border-black transition-all"
                          >
                            Explore Feed
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              <div className="space-y-8 pt-12">
                <div className="flex items-center justify-between border-b border-black/5 pb-6">
                  <h4 className="text-xl font-black uppercase tracking-tighter text-black">
                    Recent Inspirations
                  </h4>
                  <div className="text-xs font-bold text-gray-400 uppercase tracking-widest bg-gray-100 px-3 py-1 rounded-full">
                    {items.length} Items
                  </div>
                </div>
                <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
                  {Array.isArray(items) && items.slice(0, 12).map((item) => (
                    <div 
                      key={item.id} 
                      className="aspect-square bg-gray-100 overflow-hidden cursor-pointer group relative rounded-2xl"
                      onClick={() => setSelectedItem(item)}
                    >
                      <img 
                        src={item.image_url ? `/api/images/${item.image_url}` : 'https://via.placeholder.com/400x500?text=No+Image'}
                        className="w-full h-full object-cover grayscale opacity-80 group-hover:opacity-100 group-hover:grayscale-0 transition-all duration-500 group-hover:scale-110" 
                        referrerPolicy="no-referrer"
                        onError={(e) => {
                          (e.target as HTMLImageElement).src = 'https://via.placeholder.com/400x500?text=No+Image';
                        }}
                      />
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* Item Detail Modal */}
      <AnimatePresence>
        {selectedItem && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md" onClick={() => setSelectedItem(null)}>
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white w-full max-w-4xl rounded-[3rem] overflow-hidden shadow-2xl flex flex-col md:flex-row max-h-[90vh] border border-white/20"
            >
              <div className="md:w-1/2 bg-gray-50 flex items-center justify-center overflow-hidden p-8">
                <img 
                  // http로 시작하면 그대로 쓰고, 아니면 /api/images/를 붙이도록 분기 처리
                  src={
                    selectedItem.image_url?.startsWith('http') 
                      ? selectedItem.image_url 
                      : selectedItem.image_url 
                        ? `/api/images/${selectedItem.image_url}` 
                        : 'https://via.placeholder.com/600x600?text=No+Image'
                  } 
                  alt={selectedItem.category}
                  className="w-full h-full object-contain rounded-2xl shadow-sm"
                  referrerPolicy="no-referrer"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src = 'https://via.placeholder.com/600x600?text=No+Image';
                  }}
                />
              </div>
              <div className="md:w-1/2 p-8 md:p-10 flex flex-col bg-white">
                <div className="flex items-center justify-between mb-8">
                  <span className="text-[10px] font-black uppercase tracking-widest text-white bg-black px-3 py-1.5 rounded-lg">
                    {selectedItem.category}
                  </span>
                  <button 
                    onClick={() => setSelectedItem(null)}
                    className="p-2 hover:bg-gray-100 rounded-full transition-colors"
                  >
                    <X className="w-6 h-6" />
                  </button>
                </div>
                
                <div className="flex-1 overflow-y-auto space-y-8 pr-4 custom-scrollbar">
                  <section>
                    <h3 className="text-xs font-black text-gray-400 uppercase tracking-widest mb-3 flex items-center gap-2">
                      <Zap className="w-4 h-4 text-yellow-400" fill="currentColor"/> Vibe Analysis
                    </h3>
                    <p className="text-lg font-bold leading-relaxed text-black tracking-tight">{selectedItem.vibe}</p>
                  </section>

                  <section>
                    <h3 className="text-xs font-black text-gray-400 uppercase tracking-widest mb-4">Extracted Information</h3>
                    <div className="grid grid-cols-1 gap-4">
                      {(() => {
                        const facts = (() => {
                          if (!selectedItem.facts) return null;
                          if (typeof selectedItem.facts === 'string') {
                            try {
                              return JSON.parse(selectedItem.facts);
                            } catch {
                              return null;
                            }
                          }
                          return selectedItem.facts;
                        })();

                        return facts && typeof facts === 'object' ? (
                          Object.entries(facts).map(([key, value]) => (
                            <div key={key} className="group/fact bg-gray-50 p-4 rounded-2xl border border-gray-100">
                              <dt className="text-[9px] font-black text-gray-400 uppercase tracking-widest mb-2">
                                {key.replace(/_/g, ' ')}
                              </dt>
                              <dd className="text-sm font-medium text-black">
                                {Array.isArray(value) ? (
                                  <div className="flex flex-wrap gap-2">
                                    {value.map((val, i) => (
                                      <span key={i} className="px-3 py-1 bg-white border border-gray-200 rounded-lg text-xs font-bold shadow-sm">
                                        {String(val)}
                                      </span>
                                    ))}
                                  </div>
                                ) : (
                                  <span>{String(value)}</span>
                                )}
                              </dd>
                            </div>
                          ))
                        ) : (
                          <p className="text-sm text-gray-400 font-medium">No detailed facts available.</p>
                        );
                      })()}
                    </div>
                  </section>

                  <section className="border-t border-gray-100 pt-8">
                    <h3 className="text-xs font-black text-gray-400 uppercase tracking-widest mb-4">Review Insights</h3>
                    {(() => {
                      const facts = typeof selectedItem.facts === 'string' ? (() => {
                        try {
                          return JSON.parse(selectedItem.facts);
                        } catch {
                          return null;
                        }
                      })() : selectedItem.facts;
                      const reviewData = selectedItem.reviews || facts;

                      return (reviewData?.star_review || reviewData?.core_summary || reviewData?.review) ? (
                        <div className="bg-gradient-to-tr from-yellow-50 to-orange-50 p-6 rounded-3xl border border-yellow-100/50">
                          <div className="flex items-center gap-2 mb-3">
                            <span className="text-sm font-black text-yellow-600 uppercase tracking-tight">
                              {reviewData.star_review || "Recommended"}
                            </span>
                            <div className="flex text-yellow-400">
                              {"★".repeat(Math.min(5, Math.floor(parseFloat(reviewData.star_review) || 5)))}
                            </div>
                          </div>
                          <p className="text-sm font-bold leading-relaxed text-gray-800 tracking-tight">
                            "{reviewData.core_summary || reviewData.review || "No summary available"}"
                          </p>
                        </div>
                      ) : (
                        <p className="text-sm text-gray-400 font-medium">No review data extracted for this item.</p>
                      );
                    })()}
                  </section>

                  {selectedItem.url && (
                    <section className="pt-4">
                      <a 
                        href={selectedItem.url} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="flex items-center justify-center gap-2 w-full py-4 bg-gray-100 hover:bg-gray-200 text-black rounded-2xl text-xs font-black uppercase tracking-widest transition-colors"
                      >
                        <Instagram className="w-4 h-4" />
                        Open Original Post
                      </a>
                    </section>
                  )}
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

function NavItem({ icon, label, active, onClick }: { icon: React.ReactNode, label: string, active: boolean, onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-4 p-4 w-full rounded-2xl transition-all duration-200",
        active ? "bg-black text-white shadow-lg" : "hover:bg-gray-50 text-gray-400 hover:text-black"
      )}
    >
      <div className={cn("shrink-0", active && "text-white")}>
        {icon}
      </div>
      <span className="hidden md:block text-sm font-black tracking-widest uppercase">{label}</span>
    </button>
  );
}
