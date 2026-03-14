import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  Search, 
  Plus, 
  Grid, 
  User, 
  Sparkles, 
  Trash2, 
  Loader2,
  Instagram,
  Compass,
  LogOut,
  X,
  ThumbsUp,
  ThumbsDown,
  Send
} from 'lucide-react';
import Markdown from 'react-markdown';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

// 💡 Auth 컴포넌트는 더 이상 사용하지 않으므로 임포트를 주석 처리하거나 제거해도 됩니다.
// import Auth from './components/Auth';

export interface SavedItem {
  id: number;
  url: string;
  category: string;
  facts: any;
  vibe: string;
  image_url: string;
  created_at: string;
}

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export default function App() {
  // 💡 [수정] 로그인 없이 바로 게스트 계정으로 시작하도록 설정
  const [user, setUser] = useState<{ id: number; username: string } | null>({
    id: 1,
    username: "Guest_User"
  });

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
      setItems(Array.isArray(data) ? data : []);
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
      await fetchItems();
      
      const tasteRes = await fetch('/api/generate-taste', { method: 'POST' });
      const tasteData = await tasteRes.json();
      if (tasteData.success) {
        setTaste(tasteData.summary);
      }
      
    } catch (error: any) {
      console.error(error);
      alert(error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!user) return;
    await fetch(`/api/items/${id}?user_id=${user.id}`, { method: 'DELETE' });
    fetchItems();
  };

  const handleLogout = () => {
    // 💡 [수정] 로그아웃 기능을 비활성화하거나 알림만 띄웁니다.
    alert("현재 개발 모드(No-Auth) 운영 중입니다.");
  };

  // 💡 [수정] if (!user) 체크 로직을 삭제하여 무조건 메인 UI를 렌더링합니다.

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery || !user) return;
    setLoading(true);
    setSearchResults(null);
    setFeedbackType(null);
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
          <NavItem icon={<Grid />} label="Feed" active={activeTab === 'feed'} onClick={() => setActiveTab('feed')} />
          <NavItem icon={<Search />} label="Agentic Search" active={activeTab === 'search'} onClick={() => setActiveTab('search')} />
          <NavItem icon={<User />} label="Taste Profile" active={activeTab === 'profile'} onClick={() => setActiveTab('profile')} />
        </div>

        <div className="mt-auto space-y-2">
          <button onClick={() => setActiveTab('profile')} className="flex items-center gap-4 p-3 w-full hover:bg-gray-50 rounded-lg transition-colors">
            <div className="w-6 h-6 rounded-full bg-gradient-to-tr from-yellow-400 to-purple-600" />
            <span className="hidden md:block font-medium">@{user?.username}</span>
          </button>
          <button onClick={handleLogout} className="flex items-center gap-4 p-3 w-full hover:bg-red-50 text-gray-500 hover:text-red-500 rounded-lg transition-colors">
            <LogOut className="w-6 h-6" />
            <span className="hidden md:block font-medium">Logout</span>
          </button>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="flex-1 max-w-5xl mx-auto p-4 md:p-8">
        <AnimatePresence mode="wait">
          {activeTab === 'feed' && (
            <motion.div key="feed" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} className="space-y-8">
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
                  <button
                    disabled={loading}
                    className="w-full md:w-auto px-6 py-2 bg-black text-white rounded-lg hover:bg-gray-800 disabled:opacity-50 transition-all flex items-center justify-center gap-2 text-sm font-medium h-[38px]"
                  >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                    Add
                  </button>
                </form>
              </header>

              <div className="columns-2 md:columns-3 lg:columns-4 gap-4 space-y-4">
                {Array.isArray(items) && items.map((item) => (
                  <motion.div
                    layout
                    key={item.id}
                    onClick={() => setSelectedItem(item)}
                    className="break-inside-avoid group relative bg-white rounded-xl overflow-hidden border border-[#DBDBDB] hover:shadow-xl transition-all duration-300 cursor-pointer"
                  >
                    <img src={item.image_url} alt={item.category} className="w-full h-auto object-cover" referrerPolicy="no-referrer" />
                    <div className="p-3 space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">{item.category}</span>
                        <button onClick={(e) => { e.stopPropagation(); handleDelete(item.id); }} className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500 transition-opacity">
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                      <p className="text-xs font-medium leading-tight line-clamp-2">{item.vibe}</p>
                    </div>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          )}

          {activeTab === 'search' && (
            <motion.div key="search" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} className="max-w-3xl mx-auto space-y-8">
              <div className="text-center space-y-4">
                <h2 className="text-3xl font-bold italic">Agentic Curation</h2>
                <p className="text-gray-500">Search through the lens of your own taste.</p>
              </div>

              <form onSubmit={handleSearch} className="relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
                <input
                  type="text"
                  placeholder="What are you looking for?"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-12 pr-4 py-4 bg-white border border-[#DBDBDB] rounded-2xl shadow-sm focus:outline-none focus:ring-2 focus:ring-black transition-all"
                />
                <button disabled={loading} className="absolute right-2 top-1/2 -translate-y-1/2 px-6 py-2 bg-black text-white rounded-xl hover:bg-gray-800 transition-all font-medium">
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Dig"}
                </button>
              </form>

              {searchResults && (
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="bg-white p-8 rounded-3xl border border-[#DBDBDB] shadow-sm prose prose-sm max-w-none relative">
                  <div className="markdown-body">
                    <Markdown>{searchResults}</Markdown>
                  </div>
                </motion.div>
              )}
            </motion.div>
          )}

          {activeTab === 'profile' && (
            <motion.div key="profile" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} className="max-w-4xl mx-auto space-y-16">
              <div className="flex flex-col md:flex-row items-start md:items-end justify-between gap-8 border-b border-black/5 pb-12">
                <div className="space-y-4">
                  <div className="w-20 h-20 rounded-full bg-gray-50 border border-black/5 flex items-center justify-center">
                    <User className="w-10 h-10 text-gray-300" />
                  </div>
                  <h2 className="text-4xl font-serif italic">{user?.username}</h2>
                </div>
              </div>
              <div className="lg:col-span-8">
                <div className="markdown-body markdown-serif text-gray-800">
                  <Markdown>{taste || "Save more items to reveal your hidden patterns."}</Markdown>
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
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} onClick={(e) => e.stopPropagation()} className="bg-white w-full max-w-2xl rounded-2xl overflow-hidden shadow-2xl flex flex-col md:flex-row max-h-[90vh]">
              <div className="md:w-1/2 bg-gray-100 flex items-center justify-center overflow-hidden">
                <img src={selectedItem.image_url} alt={selectedItem.category} className="w-full h-full object-contain" referrerPolicy="no-referrer" />
              </div>
              <div className="md:w-1/2 p-6 flex flex-col">
                <div className="flex items-center justify-between mb-4">
                  <span className="text-xs font-bold uppercase tracking-widest text-gray-400">{selectedItem.category}</span>
                  <button onClick={() => setSelectedItem(null)} className="p-2 hover:bg-gray-100 rounded-full"><X className="w-5 h-5" /></button>
                </div>
                <div className="flex-1 overflow-y-auto space-y-6">
                  <section>
                    <h3 className="text-[10px] font-bold text-gray-400 uppercase mb-2">Vibe Analysis</h3>
                    <p className="text-sm leading-relaxed text-gray-700">{selectedItem.vibe}</p>
                  </section>
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
    <button onClick={onClick} className={cn("flex items-center gap-4 p-3 w-full rounded-lg transition-all duration-200", active ? "bg-gray-100 font-bold" : "hover:bg-gray-50 text-gray-500")}>
      <div className={cn("w-6 h-6", active && "text-black")}>{icon}</div>
      <span className="hidden md:block text-sm">{label}</span>
    </button>
  );
}