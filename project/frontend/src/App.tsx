import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
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
  Send
} from 'lucide-react';
import Markdown from 'react-markdown';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface SavedItem {
  id: number;
  url: string;
  category: string;
  facts: any;
  reviews?: any; 
  vibe: string;
  image_url: string;
  created_at: string;
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

  // 필터링할 fact 키 목록 (소문자 기준)
  // DB에 저장되는 필드명 기준으로만 렌더링합니다.
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

  const fetchItems = async () => {
    if (!user) return;
    try {
      const res = await fetch(`/api/items?user_id=${user.id}`);
      const data = await res.json();
      
      // API 응답이 배열인지 확인 후 상태 업데이트
      setItems(Array.isArray(data) ? data : []);
      console.log("Items updated:", data);
    } catch (error) {
      console.error("Failed to fetch items:", error);
      setItems([]);
    }
  };

  const fetchTaste = async () => {
    if (!user) return;
    try {
      const res = await fetch(`/api/taste?user_id=${user.id}`);
      const data = await res.json();
      setTaste(data?.summary || "");
    } catch (error) {
      console.error("Failed to fetch taste:", error);
      setTaste("");
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
      setNewUrl("");
    } catch (error: any) {
      console.error(error);
      alert("분석 중 일부 오류가 발생했습니다. 저장된 데이터만 확인합니다.");
    } finally {
      await fetchItems();
   
      try {
        const tasteRes = await fetch('/api/generate-taste', { method: 'POST' });
        const tasteData = await tasteRes.json();
        if (tasteData.success) setTaste(tasteData.summary);
      } catch (e) { console.error("Taste update failed"); }
      
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!user) return;
    await fetch(`/api/items/${id}?user_id=${user.id}`, { method: 'DELETE' });
    fetchItems();
  };

  const handleLogin = (userData: { id: number; username: string }) => {
    // Removed login logic
  };

  const handleLogout = () => {
    // Removed logout logic
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
      
      if (!silent) alert("Saved to your feed!");
      await fetchItems();
    } catch (error: any) {
      console.error(error);
      if (!silent) alert(error.message);
    } finally {
      setIsSavingSearch(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FAFAFA] text-[#262626] font-sans flex">
      {/* Sidebar Navigation */}
      <nav className="w-20 md:w-64 border-r border-[#DBDBDB] h-screen sticky top-0 bg-white flex flex-col p-4">
        <div className="mb-10 px-2">
          <h1 className="text-xl font-bold hidden md:block italic">VibeSearch</h1>
          <div className="md:hidden flex justify-center">
            <Sparkles className="w-8 h-8" />
          </div>
        </div>

        <div className="space-y-2 flex-1">
          <NavItem 
            icon={<Grid />} 
            label="Feed" 
            active={activeTab === 'feed'} 
            onClick={() => setActiveTab('feed')} 
          />
          <NavItem 
            icon={<Search />} 
            label="Agentic Search" 
            active={activeTab === 'search'} 
            onClick={() => setActiveTab('search')} 
          />
          <NavItem 
            icon={<User />} 
            label="Taste Profile" 
            active={activeTab === 'profile'} 
            onClick={() => setActiveTab('profile')} 
          />
        </div>

        <div className="mt-auto space-y-2">
          <div className="flex items-center gap-4 p-3 w-full rounded-lg">
            <div className="w-6 h-6 rounded-full bg-gradient-to-tr from-yellow-400 to-purple-600" />
            <span className="hidden md:block font-medium">@{user.username}</span>
          </div>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="flex-1 max-w-5xl mx-auto p-4 md:p-8">
        <AnimatePresence mode="wait">
          {activeTab === 'feed' && (
            <motion.div
              key="feed"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-8"
            >
              <header className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <h2 className="text-2xl font-bold">Curated Inspirations</h2>
                  <p className="text-gray-500 text-sm">Collect the vibes that define you.</p>
                </div>
                <form onSubmit={handleAddItem} className="flex flex-col md:flex-row gap-2 items-end">
                  <div className="flex-1 w-full space-y-1">
                    <label className="text-[10px] font-bold text-gray-400 uppercase">Instagram URL</label>
                    <input
                      type="url"
                      placeholder="Paste Instagram link..."
                      value={newUrl}
                      onChange={(e) => setNewUrl(e.target.value)}
                      className="w-full px-4 py-2 bg-white border border-[#DBDBDB] rounded-lg focus:outline-none focus:ring-1 focus:ring-black text-sm"
                    />
                  </div>
                  <div className="w-full md:w-48 space-y-1">
                    <label className="text-[10px] font-bold text-gray-400 uppercase">Session ID</label>
                    <input
                      type="password"
                      placeholder="sessionid cookie"
                      value={sessionId}
                      onChange={(e) => setSessionId(e.target.value)}
                      className="w-full px-4 py-2 bg-white border border-[#DBDBDB] rounded-lg focus:outline-none focus:ring-1 focus:ring-black text-sm"
                    />
                  </div>
                  <button
                    disabled={loading}
                    className="w-full md:w-auto px-6 py-2 bg-black text-white rounded-lg hover:bg-gray-800 disabled:opacity-50 transition-all flex items-center justify-center gap-2 text-sm font-medium h-[38px]"
                  >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                    Add
                  </button>
                </form>
              </header>

              {/* Pinterest-like Grid */}
              <div className="columns-2 md:columns-3 lg:columns-4 gap-4 space-y-4">
                {Array.isArray(items) && items.map((item) => (
                  <motion.div
                    layout
                    key={item.id}
                    onClick={() => setSelectedItem(item)}
                    className="break-inside-avoid group relative bg-white rounded-xl overflow-hidden border border-[#DBDBDB] hover:shadow-xl transition-all duration-300 cursor-pointer"
                  >
                    <img
                      src={item.image_url ? `/api/images/${item.image_url}` : 'https://via.placeholder.com/400x500?text=Image+Not+Found'}
                      alt={item.category}
                      className="w-full h-auto object-cover"
                      referrerPolicy="no-referrer"
                      onError={(e) => {
                        (e.target as HTMLImageElement).src = 'https://via.placeholder.com/400x500?text=Image+Not+Found';
                      }}
                    />
                    <div className="p-3 space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
                          {item.category}
                        </span>
                        <button 
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(item.id);
                          }}
                          className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500 transition-opacity"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                      <p className="text-xs font-bold leading-tight line-clamp-1">{item.vibe}</p>

                      {/* 상세 리뷰(facts) 정보 렌더링 */}
                      {item.facts && typeof item.facts === 'object' && (
                        <>
                          {Object.entries(item.facts).filter(([key]) => factKeysToShow.includes(key.toLowerCase())).length > 0 && (
                            <div className="space-y-1 mt-2 border-t border-gray-50 pt-2">
                              {Object.entries(item.facts)
                                .filter(([key]) => factKeysToShow.includes(key.toLowerCase()))
                                .map(([key, value]) => (
                                  // 너무 긴 정보는 제외하고 핵심 리뷰 정보만 노출 (예: brand, price, review 등)
                                  <div key={key} className="flex flex-col gap-0.5">
                                    <span className="text-[9px] font-bold text-gray-400 uppercase">{key.replace(/_/g, ' ')}</span>
                                    <p className="text-[10px] text-gray-600 line-clamp-2 italic">
                                      {Array.isArray(value) ? value.join(', ') : String(value)}
                                    </p>
                                  </div>
                                ))}
                            </div>
                          )}
                        </>
                      )}

                      <div className="pt-2 flex items-center gap-2">
                        {item.url && item.url.startsWith('http') ? (
                          <a 
                            href={item.url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="text-[10px] text-blue-500 hover:underline flex items-center gap-1"
                          >
                            <Instagram className="w-3 h-3" /> View Source
                          </a>
                        ) : (
                          <span className="text-[10px] text-gray-400 flex items-center gap-1">
                            <Sparkles className="w-3 h-3" /> AI Curated
                          </span>
                        )}
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
              
              {items.length === 0 && !loading && (
                <div className="text-center py-20 border-2 border-dashed border-gray-200 rounded-2xl">
                  <Compass className="w-12 h-12 mx-auto text-gray-300 mb-4" />
                  <p className="text-gray-500">Your aesthetic journey starts here.</p>
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
              className="max-w-3xl mx-auto space-y-8"
            >
              <div className="text-center space-y-4">
                <h2 className="text-3xl font-bold italic">Agentic Curation</h2>
                <p className="text-gray-500">Search through the lens of your own taste.</p>
              </div>

              <form onSubmit={handleSearch} className="relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
                <input
                  type="text"
                  placeholder="What are you looking for? (e.g., 'A chair for my reading nook')"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-12 pr-4 py-4 bg-white border border-[#DBDBDB] rounded-2xl shadow-sm focus:outline-none focus:ring-2 focus:ring-black transition-all"
                />
                <button
                  disabled={loading || quotaCountdown !== null}
                  className="absolute right-2 top-1/2 -translate-y-1/2 px-6 py-2 bg-black text-white rounded-xl hover:bg-gray-800 disabled:opacity-50 transition-all font-medium"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : quotaCountdown !== null ? `${quotaCountdown}s` : "Dig"}
                </button>
              </form>

              {quotaCountdown !== null && (
                <motion.div 
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-center p-4 bg-red-50 text-red-600 rounded-2xl border border-red-100 text-sm font-medium"
                >
                  토큰이 부족합니다. {quotaCountdown}초 뒤에 다시 시도하세요.
                </motion.div>
              )}

              {searchResults && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="bg-white p-8 rounded-3xl border border-[#DBDBDB] shadow-sm prose prose-sm max-w-none relative"
                >
                  <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-gray-400">
                      <Sparkles className="w-4 h-4 text-yellow-500" />
                      Curated Results
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleFeedback('like')}
                        className={cn(
                          "flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all border",
                          feedbackType === 'like' 
                            ? "bg-green-50 text-green-600 border-green-200" 
                            : "bg-gray-50 hover:bg-gray-100 text-gray-600 border-[#DBDBDB]"
                        )}
                      >
                        <ThumbsUp className="w-3 h-3" />
                        Like
                      </button>
                      <button
                        onClick={() => handleFeedback('dislike')}
                        className={cn(
                          "flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all border",
                          feedbackType === 'dislike' 
                            ? "bg-red-50 text-red-600 border-red-200" 
                            : "bg-gray-50 hover:bg-gray-100 text-gray-600 border-[#DBDBDB]"
                        )}
                      >
                        <ThumbsDown className="w-3 h-3" />
                        Dislike
                      </button>
                    </div>
                  </div>

                  <AnimatePresence>
                    {showFeedbackReason && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="mb-6 overflow-hidden"
                      >
                        <div className="p-4 bg-gray-50 rounded-2xl border border-gray-100 space-y-3">
                          <p className="text-xs font-medium text-gray-500">
                            {feedbackType === 'like' ? "What did you like about this result?" : "How can we improve this result?"}
                          </p>
                          <div className="flex gap-2">
                            <input
                              type="text"
                              placeholder="Optional reason..."
                              value={feedbackReason}
                              onChange={(e) => setFeedbackReason(e.target.value)}
                              className="flex-1 px-4 py-2 bg-white border border-gray-200 rounded-xl text-xs focus:outline-none focus:ring-1 focus:ring-black"
                            />
                            <button
                              onClick={submitFeedbackReason}
                              className="px-4 py-2 bg-black text-white rounded-xl text-xs font-bold hover:bg-gray-800 transition-all flex items-center gap-2"
                            >
                              <Send className="w-3 h-3" />
                              Submit
                            </button>
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  <div className="markdown-body">
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
              className="max-w-4xl mx-auto space-y-16"
            >
              <div className="flex flex-col md:flex-row items-start md:items-end justify-between gap-8 border-b border-black/5 pb-12">
                <div className="space-y-4">
                  <div className="w-20 h-20 rounded-full bg-gray-50 border border-black/5 flex items-center justify-center overflow-hidden">
                    <User className="w-10 h-10 text-gray-300" />
                  </div>
                  <div className="space-y-1">
                    <h2 className="text-4xl font-serif italic tracking-tight text-black">
                      {user?.username || 'Anonymous'}
                    </h2>
                    <p className="text-sm font-medium text-gray-400 uppercase tracking-widest">
                      Aesthetic Soul No. {user?.id || '000'}
                    </p>
                  </div>
                </div>
                <div className="text-left md:text-right max-w-xs">
                  <p className="text-lg font-serif italic text-gray-500 leading-relaxed">
                    "형용하지 못하는 나를 이루어주길"
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">
                <div className="lg:col-span-4 space-y-6">
                  <div className="flex items-center gap-3 text-[10px] font-bold uppercase tracking-[0.3em] text-gray-300">
                    <Sparkles className="w-3 h-3" />
                    Taste Analysis
                  </div>
                  <h3 className="text-2xl font-serif leading-tight">
                    The patterns of your <br />
                    <span className="italic">unconscious choices.</span>
                  </h3>
                  <div className="h-px w-12 bg-black/10" />
                </div>

                <div className="lg:col-span-8">
                  {taste ? (
                    <div className="markdown-body markdown-serif text-gray-800">
                      <Markdown>{taste}</Markdown>
                    </div>
                  ) : (
                    <div className="py-12 border border-dashed border-gray-200 rounded-3xl flex flex-col items-center justify-center text-center space-y-4">
                      <p className="text-gray-400 font-serif italic">Save more items to reveal your hidden patterns.</p>
                      <button 
                        onClick={() => setActiveTab('feed')}
                        className="text-xs font-bold uppercase tracking-widest hover:tracking-[0.2em] transition-all"
                      >
                        Explore Feed
                      </button>
                    </div>
                  )}
                </div>
              </div>

              <div className="space-y-8">
                <div className="flex items-center justify-between">
                  <h4 className="text-[10px] font-bold uppercase tracking-[0.3em] text-gray-300">
                    Recent Inspirations
                  </h4>
                  <div className="text-[10px] text-gray-400">
                    {items.length} Items Collected
                  </div>
                </div>
                <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
                  {Array.isArray(items) && items.slice(0, 12).map((item) => (
                    <div 
                      key={item.id} 
                      className="aspect-square bg-gray-50 overflow-hidden cursor-pointer group relative"
                      onClick={() => setSelectedItem(item)}
                    >
                      <img 
                        src={item.image_url ? `/api/images/${item.image_url}` : 'https://via.placeholder.com/400x500?text=Image+Not+Found'}
                        className="w-full h-full object-cover grayscale hover:grayscale-0 transition-all duration-700 ease-in-out group-hover:scale-105" 
                        referrerPolicy="no-referrer"
                        onError={(e) => {
                          (e.target as HTMLImageElement).src = 'https://via.placeholder.com/400x500?text=Image+Not+Found';
                        }}
                      />
                      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/5 transition-colors" />
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
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={() => setSelectedItem(null)}>
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white w-full max-w-2xl rounded-2xl overflow-hidden shadow-2xl flex flex-col md:flex-row max-h-[90vh]"
            >
              <div className="md:w-1/2 bg-gray-100 flex items-center justify-center overflow-hidden">
                <img 
                  src={selectedItem.image_url ? `/api/images/${selectedItem.image_url}` : 'https://via.placeholder.com/600x600?text=No+Image'} 
                  alt={selectedItem.category}
                  className="w-full h-full object-contain"
                  referrerPolicy="no-referrer"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src = 'https://via.placeholder.com/600x600?text=No+Image';
                  }}
                />
              </div>
              <div className="md:w-1/2 p-6 flex flex-col">
                <div className="flex items-center justify-between mb-4">
                  <span className="text-xs font-bold uppercase tracking-widest text-gray-400">
                    {selectedItem.category}
                  </span>
                  <button 
                    onClick={() => setSelectedItem(null)}
                    className="p-2 hover:bg-gray-100 rounded-full transition-colors"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
                
                <div className="flex-1 overflow-y-auto space-y-6 pr-2 custom-scrollbar">
                  <section>
                    <h3 className="text-[10px] font-bold text-gray-400 uppercase mb-2">Vibe Analysis</h3>
                    <p className="text-sm leading-relaxed text-gray-700">{selectedItem.vibe}</p>
                  </section>

                  <section>
                    <h3 className="text-[10px] font-bold text-gray-400 uppercase mb-3">Extracted Information</h3>
                    <div className="grid grid-cols-1 gap-3">
                      {(() => {
                        // facts가 문자열일 경우를 대비해 파싱 시도
                        const facts = typeof selectedItem.facts === 'string' 
                          ? JSON.parse(selectedItem.facts) 
                          : selectedItem.facts;

                        return facts && typeof facts === 'object' ? (
                          Object.entries(facts).map(([key, value]) => (
                            <div key={key} className="group/fact">
                              <dt className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-1">
                                {key.replace(/_/g, ' ')}
                              </dt>
                              <dd className="text-sm text-gray-800 bg-gray-50/50 p-3 rounded-xl border border-gray-100">
                                {Array.isArray(value) ? (
                                  <div className="flex flex-wrap gap-1.5">
                                    {value.map((val, i) => (
                                      <span key={i} className="px-2 py-0.5 bg-white border border-gray-200 rounded-md text-[11px]">
                                        {String(val)}
                                      </span>
                                    ))}
                                  </div>
                                ) : (
                                  <span className="font-medium">{String(value)}</span>
                                )}
                              </dd>
                            </div>
                          ))
                        ) : (
                          <p className="text-sm text-gray-400 italic">No detailed facts available.</p>
                        );
                      })()}
                    </div>
                  </section>

                  <section className="mt-6 border-t pt-6">
                    <h3 className="text-[10px] font-bold text-gray-400 uppercase mb-3">Review Insights</h3>
                    {/* facts 내부나 reviews 객체 양쪽을 모두 체크하도록 변경 */}
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
                        <div className="bg-yellow-50/50 p-4 rounded-2xl border border-yellow-100">
                          <div className="flex items-center gap-1 mb-2">
                            <span className="text-sm font-bold text-yellow-600">
                              {reviewData.star_review || "Recommended"}
                            </span>
                            <div className="flex text-yellow-400">
                              {/* 별점 데이터가 숫자일 경우 별표 렌더링 */}
                              {"★".repeat(Math.min(5, Math.floor(parseFloat(reviewData.star_review) || 5)))}
                            </div>
                          </div>
                          <p className="text-xs leading-relaxed text-gray-600 italic">
                            "{reviewData.core_summary || reviewData.review || "No summary available"}"
                          </p>
                        </div>
                      ) : (
                        <p className="text-xs text-gray-400 italic">No review data extracted for this item.</p>
                      );
                    })()}
                  </section>

                  {selectedItem.url && (
                    <section>
                      <h3 className="text-[10px] font-bold text-gray-400 uppercase mb-2">Source</h3>
                      <a 
                        href={selectedItem.url} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-2 px-4 py-2 bg-blue-50 text-blue-600 rounded-lg text-xs font-medium hover:bg-blue-100 transition-colors"
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
        "flex items-center gap-4 p-3 w-full rounded-lg transition-all duration-200",
        active ? "bg-gray-100 font-bold" : "hover:bg-gray-50 text-gray-500"
      )}
    >
      <div className={cn("w-6 h-6", active && "text-black")}>
        {icon}
      </div>
      <span className="hidden md:block text-sm">{label}</span>
    </button>
  );
}