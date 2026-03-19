/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

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
  const [isGeneratingTaste, setIsGeneratingTaste] = useState(false); 
  const [isSharingProfile, setIsSharingProfile] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string>('All'); 

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
        await navigator.share({ title: '내 취향 프로필', text: shareText });
      } else if (navigator.clipboard) {
        await navigator.clipboard.writeText(shareText);
        alert('클립보드에 복사되었습니다. 인스타그램에 공유하세요!');
      }
    } catch (error) {
      console.error('Share failed:', error);
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
      if (!res.ok) throw new Error("Failed to analyze URL");
      setNewUrl("");
    } catch (error) {
      alert("분석 중 오류가 발생했습니다.");
    } finally {
      await fetchItems();
      await fetchTaste(); 
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!user) return;
    await fetch(`/api/items/${id}?user_id=${user.id}`, { method: 'DELETE' });
    fetchItems();
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery || !user) return;
    setLoading(true);
    setSearchResults(null);
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
      setSearchResults(data.result || null);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (type: 'like' | 'dislike') => {
    if (!user || !searchResults) return;
    setFeedbackType(type);
    setShowFeedbackReason(true);
    if (type === 'like') await handleSaveSearchResult(true);
  };

  const submitFeedbackReason = async () => {
    if (!user || !searchResults || !feedbackType) return;
    try {
      await fetch('/api/agentic-search/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: user.id, query: searchQuery, result: searchResults, feedback_type: feedbackType, reason: feedbackReason
        })
      });
      setShowFeedbackReason(false);
      setFeedbackReason("");
      await fetchTaste();
    } catch (error) { console.error(error); }
  };

  const handleSaveSearchResult = async (silent = false) => {
    if (!searchResults || !user) return;
    setIsSavingSearch(true);
    try {
      const res = await fetch('/api/items/manual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          user_id: user.id, category: "INSPIRATION", vibe: `Search: ${searchQuery}`, facts: { content: searchResults }, url: "agentic-search"
        })
      });
      if (!res.ok) throw new Error();
      if (!silent) alert("Saved!");
      await fetchItems();
      await fetchTaste();
    } finally { setIsSavingSearch(false); }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-yellow-400 via-white to-sky-400 text-black font-sans flex selection:bg-yellow-300">
      {/* Sidebar */}
      <nav className="w-20 md:w-72 border-r border-black/10 backdrop-blur-md bg-white/5 h-screen sticky top-0 flex flex-col p-6 z-10 space-y-12">
        <div className="flex items-center gap-4 border border-black/10 bg-white/10 p-4 rounded-3xl shadow-sm">
          <img src="https://picsum.photos/seed/pose/200/200" alt="POSE! Logo" className="w-12 h-12 rounded-xl shrink-0" />
          <div className="hidden md:flex flex-col gap-0.5">
            <h1 className="text-2xl font-serif font-black tracking-tighter uppercase">POSE!</h1>
            <p className="text-[10px] font-sans font-medium text-gray-500 tracking-widest uppercase">My Aesthetic Archive</p>
          </div>
        </div>

        <div className="space-y-4 flex-1">
          <NavItem icon={<Grid className="w-6 h-6" />} label="Archive" active={activeTab === 'feed'} onClick={() => setActiveTab('feed')} />
          <NavItem icon={<Search className="w-6 h-6" />} label="Aesthetic Search" active={activeTab === 'search'} onClick={() => setActiveTab('search')} />
          <NavItem icon={<User className="w-6 h-6" />} label="Vibe Profile" active={activeTab === 'profile'} onClick={() => setActiveTab('profile')} />
        </div>

        <div className="mt-auto">
          <div className="flex items-center gap-3 p-3 rounded-2xl bg-white/10 border border-black/5">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-yellow-400 to-blue-500 p-[1.5px]">
              <div className="w-full h-full bg-white rounded-full flex items-center justify-center">
                <User className="w-4 h-4 text-black"/>
              </div>
            </div>
            <span className="hidden md:block font-serif font-medium text-lg tracking-tight">@{user.username}</span>
          </div>
        </div>
      </nav>

      {/* Main */}
      <main className="flex-1 max-w-6xl mx-auto p-4 md:p-10 overflow-x-hidden">
        <AnimatePresence mode="wait">
          {activeTab === 'feed' && (
            <motion.div key="feed" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} className="space-y-12">
              <header className="flex flex-col xl:flex-row xl:items-end justify-between gap-10">
                <div className="space-y-1">
                  <h2 className="text-4xl xl:text-5xl font-serif font-black tracking-tighter uppercase">Catch your POSE!</h2>
                  <p className="text-gray-500 font-sans font-medium mt-1">나만의 무드를 박제하세요.</p>
                </div>
                <form onSubmit={handleAddItem} className="flex flex-col sm:flex-row gap-3 items-end p-4 bg-white/20 backdrop-blur-sm rounded-3xl border border-black/5">
                  <div className="flex-1 w-full xl:w-80 space-y-2">
                    <label className="text-[10px] font-sans font-black text-gray-400 uppercase tracking-widest">Instagram URL</label>
                    <input type="url" placeholder="Paste link..." value={newUrl} onChange={(e) => setNewUrl(e.target.value)} className="w-full px-5 py-3.5 bg-white/50 border-none rounded-2xl focus:ring-2 focus:ring-black text-sm" />
                  </div>
                  <div className="w-full sm:w-60 space-y-2">
                    <label className="text-[10px] font-sans font-black text-gray-400 uppercase tracking-widest">Session ID</label>
                    <input type="password" placeholder="sessionid" value={sessionId} onChange={(e) => setSessionId(e.target.value)} className="w-full px-5 py-3.5 bg-white/50 border-none rounded-2xl focus:ring-2 focus:ring-black text-sm" />
                  </div>
                  <button disabled={loading} className="px-10 py-3.5 bg-black text-white rounded-full hover:bg-gray-800 transition-all flex items-center gap-2 text-xs font-black uppercase h-[50px]">
                    {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Plus className="w-5 h-5" />} Add
                  </button>
                </form>
              </header>

              {items.length > 0 && (
                <div className="flex flex-wrap gap-2.5 py-4 border-t border-b border-black/5">
                  {categories.map(cat => (
                    <button key={cat} onClick={() => setSelectedCategory(cat)} className={cn("px-6 py-2.5 rounded-full text-[11px] font-black uppercase tracking-widest transition-all", selectedCategory === cat ? "bg-black text-white" : "bg-white/40 text-gray-500 hover:bg-white/60")}>
                      {cat}
                    </button>
                  ))}
                </div>
              )}

              <div className="columns-2 md:columns-3 lg:columns-4 xl:columns-5 gap-5 space-y-5 mt-4">
                {filteredItems.map((item) => (
                  <motion.div layout key={item.id} onClick={() => setSelectedItem(item)} className="break-inside-avoid group relative bg-white rounded-[2rem] overflow-hidden border border-black/5 hover:shadow-2xl transition-all cursor-pointer">
                    <div className="relative overflow-hidden">
                      <img src={item.image_url.startsWith('http') ? item.image_url : `https://picsum.photos/seed/${item.id}/400/500`} alt={item.category} className="w-full h-auto object-cover transform group-hover:scale-110 transition-transform duration-700" />
                      <div className="absolute inset-0 bg-black/10 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-sm">
                        <span className="text-white text-[11px] font-black uppercase bg-black/20 px-3 py-1 rounded-full border border-white/20">View Detail</span>
                      </div>
                    </div>
                    <div className="p-5 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-black uppercase text-black bg-yellow-300 px-3 py-1 rounded-full">{item.category}</span>
                        <button onClick={(e) => { e.stopPropagation(); handleDelete(item.id); }} className="opacity-0 group-hover:opacity-100 p-2 text-red-500"><Trash2 className="w-4 h-4" /></button>
                      </div>
                      <p className="text-sm font-serif font-black leading-tight line-clamp-2">{item.vibe}</p>
                    </div>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          )}

          {activeTab === 'search' && (
            <motion.div key="search" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} className="max-w-4xl mx-auto space-y-16 py-12">
              <div className="text-center space-y-4">
                <div className="inline-flex items-center justify-center w-20 h-20 rounded-3xl bg-black mb-6">
                  <Search className="w-10 h-10 text-white" />
                </div>
                <h2 className="text-5xl font-serif font-black uppercase">POSE! Aesthetic Search</h2>
                <p className="text-gray-500">당신의 취향을 기반으로 새로운 영감을 찾아냅니다.</p>
              </div>
              <form onSubmit={handleSearch} className="relative p-4 bg-white/20 backdrop-blur-sm rounded-[3rem] border border-black/5">
                <Search className="absolute left-10 top-1/2 -translate-y-1/2 text-gray-400 w-7 h-7" />
                <input type="text" placeholder="빈티지한 조명..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="w-full pl-24 pr-40 py-6 bg-white border-2 border-transparent rounded-[2.5rem] focus:border-black transition-all text-xl" />
                <button disabled={loading || quotaCountdown !== null} className="absolute right-7 top-1/2 -translate-y-1/2 px-10 py-4 bg-black text-white rounded-full font-black uppercase text-xs">
                  {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : quotaCountdown !== null ? `${quotaCountdown}s` : "Dig for POSE"}
                </button>
              </form>
              {searchResults && (
                <motion.div className="bg-white p-10 rounded-[4rem] shadow-2xl prose max-w-none">
                   <Markdown>{searchResults}</Markdown>
                   <div className="flex gap-4 mt-8">
                     <button onClick={() => handleFeedback('like')} className="flex items-center gap-2 px-6 py-2 bg-black text-white rounded-xl uppercase text-xs font-black"><ThumbsUp className="w-4 h-4"/> Like</button>
                     <button onClick={() => handleFeedback('dislike')} className="flex items-center gap-2 px-6 py-2 bg-gray-100 rounded-xl uppercase text-xs font-black"><ThumbsDown className="w-4 h-4"/> Dislike</button>
                   </div>
                </motion.div>
              )}
            </motion.div>
          )}

          {activeTab === 'profile' && (
            <motion.div key="profile" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} className="max-w-5xl mx-auto space-y-20 py-12">
              <div className="flex justify-between items-end border-b border-black/10 pb-16">
                <div className="space-y-6">
                  <div className="w-32 h-32 rounded-full bg-black p-1">
                    <div className="w-full h-full bg-white rounded-full flex items-center justify-center overflow-hidden">
                      <User className="w-16 h-16" />
                    </div>
                  </div>
                  <h2 className="text-6xl font-serif font-black uppercase">@{user.username}</h2>
                </div>
                <p className="text-4xl font-serif font-black uppercase text-right">"My Vibe is<br/>My POSE."</p>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-12 gap-16 p-8 bg-white/20 rounded-[3rem] border border-black/5">
                <div className="lg:col-span-4 space-y-8">
                  <div className="flex items-center gap-4 text-xs font-black uppercase tracking-widest text-blue-600 bg-blue-50 px-4 py-2 rounded-full w-fit">
                    <Zap className="w-4 h-4 fill-current" /> Taste Analysis
                  </div>
                  <h3 className="text-5xl font-serif font-black uppercase leading-none">The Patterns<br/>of your<br/>Choices.</h3>
                </div>
                <div className="lg:col-span-8">
                  {taste ? (
                    <div className="bg-white/60 p-10 rounded-[4rem] space-y-12">
                      <div className="prose text-lg"><Markdown>{taste}</Markdown></div>
                      <div className="flex justify-end gap-4">
                        <button onClick={handleGenerateTaste} disabled={isGeneratingTaste} className="flex items-center gap-2 px-8 py-4 bg-white border border-black/10 rounded-full font-black uppercase text-xs">
                          {isGeneratingTaste ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />} Analyze Again
                        </button>
                        <button onClick={handleShareProfile} disabled={isSharingProfile} className="flex items-center gap-2 px-8 py-4 bg-black text-white rounded-full font-black uppercase text-xs">
                          <Instagram className="w-4 h-4" /> Share My POSE
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="py-28 bg-white/40 rounded-[3rem] flex flex-col items-center gap-8 border-2 border-dashed border-black/10">
                      <Zap className="w-12 h-12 text-yellow-500 fill-current" />
                      <p className="text-xl font-bold">충분한 영감이 모였습니다.</p>
                      <button onClick={handleGenerateTaste} disabled={isGeneratingTaste} className="px-12 py-5 bg-black text-white rounded-full font-black uppercase">
                        {isGeneratingTaste ? 'Analyzing...' : 'Show My POSE'}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* Detail Modal */}
      <AnimatePresence>
        {selectedItem && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/60 backdrop-blur-xl" onClick={() => setSelectedItem(null)}>
            <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.9 }} onClick={(e) => e.stopPropagation()} className="bg-white w-full max-w-5xl rounded-[4rem] overflow-hidden flex flex-col md:row h-[80vh]">
              <div className="md:w-1/2 bg-gray-50 flex items-center justify-center p-8">
                <img src={selectedItem.image_url.startsWith('http') ? selectedItem.image_url : `https://picsum.photos/seed/${selectedItem.id}/600/600`} alt="Detail" className="max-h-full rounded-2xl shadow-2xl" />
              </div>
              <div className="md:w-1/2 p-12 flex flex-col overflow-y-auto">
                <div className="flex justify-between items-center mb-8">
                  <span className="px-4 py-2 bg-yellow-300 rounded-full font-black text-xs uppercase">{selectedItem.category}</span>
                  <button onClick={() => setSelectedItem(null)}><X className="w-8 h-8" /></button>
                </div>
                <h3 className="text-3xl font-serif font-black mb-6">{selectedItem.vibe}</h3>
                <div className="space-y-6">
                  {selectedItem.facts && (
                    <div className="bg-gray-50 p-6 rounded-3xl">
                      <p className="text-[10px] font-black uppercase text-gray-400 mb-2">Details</p>
                      <pre className="whitespace-pre-wrap font-sans text-sm">{typeof selectedItem.facts === 'string' ? selectedItem.facts : JSON.stringify(selectedItem.facts, null, 2)}</pre>
                    </div>
                  )}
                  {selectedItem.url && (
                    <a href={selectedItem.url} target="_blank" rel="noreferrer" className="flex items-center justify-center gap-2 py-4 bg-black text-white rounded-2xl font-black uppercase text-xs">
                      <Instagram className="w-5 h-5" /> Open Original Post
                    </a>
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
    <button onClick={onClick} className={cn("flex items-center gap-4 p-5 w-full rounded-3xl transition-all", active ? "bg-white shadow-xl text-black" : "text-gray-500 hover:text-black")}>
      <div className="shrink-0">{icon}</div>
      <span className="hidden md:block text-xs font-black uppercase tracking-widest">{label}</span>
    </button>
  );
}
