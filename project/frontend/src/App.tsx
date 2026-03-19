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

  const wrapText = (ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string[] => {
    const words = text.split(' ');
    const lines: string[] = [];
    let currentLine = '';

    for (const word of words) {
      const testLine = currentLine ? `${currentLine} ${word}` : word;
      const testWidth = ctx.measureText(testLine).width;
      if (testWidth > maxWidth && currentLine) {
        lines.push(currentLine);
        currentLine = word;
      } else {
        currentLine = testLine;
      }
    }
    if (currentLine) lines.push(currentLine);
    return lines;
  };

  const createStoryCardBlob = async (nickname: string, profile: string): Promise<Blob | null> => {
    const width = 1080;
    const height = 1920;
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;

    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, '#2d2a67');
    gradient.addColorStop(1, '#1f1b4f');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);

    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 72px Pretendard, system-ui, sans-serif';
    ctx.fillText('My POSE! 취향 프로필', 70, 130);

    ctx.font = 'bold 44px Pretendard, system-ui, sans-serif';
    ctx.fillText(`닉네임: ${nickname || 'Anonymous'}`, 70, 220);

    ctx.font = '36px Pretendard, system-ui, sans-serif';
    const wrappedLines = profile.split('\n').flatMap((line) => wrapText(ctx, line, 940));
    let y = 300;
    const lineHeight = 54;
    for (const line of wrappedLines) {
      if (y > height - 120) break;
      ctx.fillText(line, 70, y);
      y += lineHeight;
    }

    ctx.font = 'bold 40px Pretendard, system-ui, sans-serif';
    ctx.fillStyle = '#f8d442';
    ctx.fillText('#POSE #취향프로필 #Aesthetic', 70, height - 90);

    return await new Promise((resolve) => {
      canvas.toBlob((blob) => resolve(blob), 'image/png');
    });
  };

  const handleDownloadStoryCard = async () => {
    if (!taste) {
      alert('먼저 취향 프로필을 생성해 주세요.');
      return;
    }

    const blob = await createStoryCardBlob(user?.username || 'Anonymous', taste);
    if (!blob) {
      alert('스토리 카드 이미지 생성에 실패했습니다.');
      return;
    }

    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'pose_story_profile.png';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);

    alert('스토리 카드 이미지가 다운로드되었습니다. 인스타그램 스토리에 업로드하세요.');
  };

  const handleShareProfile = async () => {
    if (!taste) {
      alert('먼저 취향 프로필을 생성해 주세요.');
      return;
    }

    setIsSharingProfile(true);
    try {
      const blob = await createStoryCardBlob(user?.username || 'Anonymous', taste);
      if (blob && navigator.canShare && navigator.canShare({ files: [new File([blob], 'pose_story_profile.png', { type: 'image/png' })] })) {
        await navigator.share({
          title: '내 취향 프로필',
          text: '인스타그램 스토리용 POSE 취향 프로필',
          files: [new File([blob], 'pose_story_profile.png', { type: 'image/png' })],
        });
        return;
      }

      const shareText = `My POSE! 취향 프로필\n\n닉네임: ${user?.username || 'Anonymous'}\n\n${taste}\n\n#POSE #취향프로필 #Aesthetic`;

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
      setNewUrl("");
    } catch (error: any) {
      console.error(error);
      alert("분석 중 일부 오류가 발생했습니다. 저장된 데이터만 확인합니다.");
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
      
      if (!silent) alert("Saved to your feed!");
      await fetchItems();
      await fetchTaste();
    } catch (error: any) {
      console.error(error);
      if (!silent) alert(error.message);
    } finally {
      setIsSavingSearch(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 via-yellow-400 to-blue-900 animate-gradient text-black font-sans flex selection:bg-yellow-300 selection:text-black selection:backdrop-blur-sm selection:bg-black/10">
      {/* Sidebar Navigation */}
      <nav className="w-20 md:w-72 border-r border-gradient-r-from-yellow-400 border-r-to-blue-500 backdrop-blur-md bg-white/5 h-screen sticky top-0 flex flex-col p-6 z-10 space-y-12">
        <div className="flex items-center gap-4 border border-black/10 bg-white/5 p-4 rounded-3xl shadow-sm">
          <img src="/logo-pose.png" alt="POSE! Logo" className="w-12 h-12 rounded-xl shrink-0" />
          <div className="hidden md:flex flex-col gap-0.5">
            <h1 className="text-2xl font-serif font-black tracking-tighter uppercase">POSE!</h1>
            <p className="text-[10px] font-sans font-medium text-gray-500 tracking-widest uppercase">My Aesthetic Archive</p>
          </div>
        </div>

        <div className="space-y-4 flex-1">
          <NavItem 
            icon={<Grid className="w-6 h-6" />} 
            label="Archive" 
            active={activeTab === 'feed'} 
            onClick={() => setActiveTab('feed')} 
          />
          <NavItem 
            icon={<Search className="w-6 h-6" />} 
            label="Aesthetic Search" 
            active={activeTab === 'search'} 
            onClick={() => setActiveTab('search')} 
          />
          <NavItem 
            icon={<User className="w-6 h-6" />} 
            label="Vibe Profile" 
            active={activeTab === 'profile'} 
            onClick={() => setActiveTab('profile')} 
          />
        </div>

        <div className="mt-auto space-y-2">
          <div className="flex items-center gap-3 p-3 w-full rounded-2xl bg-white/5 border border-black/5 backdrop-blur-md">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-yellow-400 to-blue-500 p-[1.5px] shadow-md shadow-yellow-500/10">
              <div className="w-full h-full bg-white rounded-full flex items-center justify-center">
                <User className="w-4 h-4 text-black"/>
              </div>
            </div>
            <span className="hidden md:block font-serif font-medium text-lg tracking-tight">@{user.username}</span>
          </div>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="flex-1 max-w-6xl mx-auto p-4 md:p-10 overflow-x-hidden">
        <AnimatePresence mode="wait">
          {activeTab === 'feed' && (
            <motion.div
              key="feed"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-12"
            >
              <header className="flex flex-col xl:flex-row xl:items-end justify-between gap-10">
                <div className="space-y-1">
                  <h2 className="text-4xl xl:text-5xl font-serif font-black tracking-tighter uppercase bg-clip-text text-transparent bg-gradient-to-r from-black to-gray-500 animate-text-gradient">Catch your POSE!</h2>
                  <p className="text-gray-500 font-sans font-medium mt-1">나만의 무드를 박제하세요.</p>
                </div>
                <form onSubmit={handleAddItem} className="flex flex-col sm:flex-row gap-3 items-end w-full xl:w-auto p-4 bg-white/5 backdrop-blur-sm rounded-3xl border border-black/5">
                  <div className="flex-1 w-full xl:w-80 space-y-2">
                    <label className="text-[10px] font-sans font-black text-gray-400 uppercase tracking-widest">Instagram URL</label>
                    <input
                      type="url"
                      placeholder="Paste link..."
                      value={newUrl}
                      onChange={(e) => setNewUrl(e.target.value)}
                      className="w-full px-5 py-3.5 bg-gray-50 border-none rounded-2xl focus:outline-none focus:ring-2 focus:ring-black text-sm font-medium transition-all"
                    />
                  </div>
                  <div className="w-full sm:w-60 space-y-2">
                    <label className="text-[10px] font-sans font-black text-gray-400 uppercase tracking-widest">Session ID</label>
                    <input
                      type="password"
                      placeholder="sessionid cookie"
                      value={sessionId}
                      onChange={(e) => setSessionId(e.target.value)}
                      className="w-full px-5 py-3.5 bg-gray-50 border-none rounded-2xl focus:outline-none focus:ring-2 focus:ring-black text-sm font-medium transition-all"
                    />
                  </div>
                  <button
                    disabled={loading}
                    className="w-full sm:w-auto px-10 py-3.5 bg-black text-white rounded-full hover:bg-gray-800 hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-50 disabled:transform-none transition-all flex items-center justify-center gap-2.5 text-xs font-sans font-black tracking-widest uppercase h-[50px] sm:h-auto shadow-md shadow-black/10"
                  >
                    {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Plus className="w-5 h-5" />}
                    Add
                  </button>
                </form>
              </header>

              {/* 카테고리 필터 버튼 영역 */}
              {items.length > 0 && (
                <div className="flex flex-wrap gap-2.5 py-4 border-t border-b border-black/5">
                  {categories.map(cat => (
                    <button
                      key={cat}
                      onClick={() => setSelectedCategory(cat)}
                      className={cn(
                        "px-6 py-2.5 rounded-full text-[11px] font-sans font-black uppercase tracking-widest transition-all",
                        selectedCategory === cat 
                          ? "bg-black text-white shadow-lg scale-105" 
                          : "bg-gray-100 text-gray-500 hover:bg-gray-200"
                      )}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              )}

              {/* Pinterest-like Grid */}
              <div className="columns-2 md:columns-3 lg:columns-4 xl:columns-5 gap-5 space-y-5 mt-4">
                {Array.isArray(filteredItems) && filteredItems.map((item) => (
                  <motion.div
                    layout
                    key={item.id}
                    onClick={() => setSelectedItem(item)}
                    className="break-inside-avoid group relative bg-white rounded-[2rem] overflow-hidden border border-black/5 hover:shadow-2xl hover:-translate-y-1.5 transition-all duration-300 cursor-pointer"
                  >
                    <div className="relative overflow-hidden">
                      <img
                        src={item.image_url ? `/api/images/${item.image_url}` : 'https://via.placeholder.com/400x500?text=POSE+Not+Found'}
                        alt={item.category}
                        className="w-full h-auto object-cover transform group-hover:scale-110 transition-transform duration-700"
                        referrerPolicy="no-referrer"
                        onError={(e) => {
                          (e.target as HTMLImageElement).src = 'https://via.placeholder.com/400x500?text=POSE+Not+Found';
                        }}
                      />
                      <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-center justify-center backdrop-blur-sm bg-black/10">
                        <span className="text-white text-[11px] font-sans font-black uppercase tracking-widest bg-black/20 px-3 py-1 rounded-full border border-white/20">View Detail</span>
                      </div>
                    </div>
                    <div className="p-5 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-sans font-black uppercase tracking-widest text-black bg-yellow-300 px-3 py-1 rounded-full">
                          {item.category}
                        </span>
                        <button 
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(item.id);
                          }}
                          className="opacity-0 group-hover:opacity-100 p-2.5 bg-red-50 text-red-500 rounded-full hover:bg-red-100 transition-all shadow-md shadow-red-500/10"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                      <p className="text-sm xl:text-base font-serif font-black leading-tight line-clamp-2 text-black">{item.vibe}</p>

                      <div className="pt-3 flex items-center gap-3">
                        {item.url && item.url.startsWith('http') ? (
                          <a 
                            href={item.url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="text-[11px] font-sans font-bold text-gray-500 hover:text-black flex items-center gap-1.5 transition-colors bg-gray-50 px-3 py-1 rounded-full border border-gray-100"
                          >
                            <Instagram className="w-3.5 h-3.5" /> View Source
                          </a>
                        ) : (
                          <span className="text-[11px] font-sans font-bold text-gray-400 flex items-center gap-1.5 bg-gray-50 px-3 py-1 rounded-full border border-gray-100">
                            <Sparkles className="w-3.5 h-3.5 text-yellow-400" fill="currentColor"/> AI Curated
                          </span>
                        )}
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
              
              {items.length === 0 && !loading && (
                <div className="text-center py-40 bg-white/5 border-2 border-dashed border-gradient-r-from-yellow-400 border-r-to-blue-500 rounded-[3rem] backdrop-blur-sm animate-pulse-border">
                  <div className="w-24 h-24 bg-white/10 backdrop-blur-sm rounded-full flex items-center justify-center mx-auto mb-10 shadow-lg border border-white/20">
                    <Zap className="w-12 h-12 text-yellow-300" fill="currentColor" />
                  </div>
                  <h3 className="text-3xl font-serif font-black tracking-tighter mb-3 uppercase bg-clip-text text-transparent bg-gradient-to-r from-black to-gray-500">Strike your first POSE!</h3>
                  <p className="text-gray-500 font-sans font-medium">인스타그램 링크를 넣고 나만의 바이브를 수집하세요.</p>
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
              className="max-w-4xl mx-auto space-y-16 py-12"
            >
              <div className="text-center space-y-4">
                <div className="inline-flex items-center justify-center w-20 h-20 rounded-3xl bg-gradient-to-tr from-yellow-400 via-white to-blue-500 p-[3px] mb-6 shadow-xl animate-spin-gradient">
                  <div className="w-full h-full bg-black rounded-[20px] flex items-center justify-center">
                    <Search className="w-10 h-10 text-white" />
                  </div>
                </div>
                <h2 className="text-5xl font-serif font-black tracking-tighter uppercase bg-clip-text text-transparent bg-gradient-to-r from-black to-gray-500 animate-text-gradient">POSE! Aesthetic Search</h2>
                <p className="text-gray-500 font-sans font-medium mt-1">당신의 취향을 기반으로 새로운 영감을 찾아냅니다.</p>
              </div>

              <form onSubmit={handleSearch} className="relative group p-4 bg-white/5 backdrop-blur-sm rounded-[3rem] border border-black/5">
                <Search className="absolute left-10 top-1/2 -translate-y-1/2 text-gray-400 w-7 h-7 transition-colors group-focus-within:text-black" />
                <input
                  type="text"
                  placeholder="What are you looking for? (e.g., 빈티지한 조명)"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-24 pr-40 py-6 bg-white border-2 border-gray-100 rounded-[2.5rem] shadow-xl shadow-gray-100 focus:outline-none focus:border-black transition-all text-xl font-medium"
                />
                <button
                  disabled={loading || quotaCountdown !== null}
                  className="absolute right-7 top-1/2 -translate-y-1/2 px-10 py-4 bg-black text-white rounded-full hover:bg-gray-800 disabled:opacity-50 transition-all font-sans font-black tracking-widest uppercase text-xs h-[56px]"
                >
                  {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : quotaCountdown !== null ? `${quotaCountdown}s` : "Dig for POSE"}
                </button>
              </form>

              {quotaCountdown !== null && (
                <motion.div 
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-center p-5 bg-red-50 text-red-600 rounded-2xl border border-red-100 text-sm font-sans font-bold tracking-tight shadow-lg shadow-red-500/10"
                >
                  토큰이 부족합니다. {quotaCountdown}초 뒤에 다시 시도하세요.
                </motion.div>
              )}

              {searchResults && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="bg-white p-10 md:p-12 rounded-[4rem] border border-black/5 shadow-2xl shadow-gray-100 prose prose-lg max-w-none relative backdrop-blur-sm bg-white/5 overflow-hidden"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-8 mb-10 pb-10 border-b border-gray-100">
                    <div className="flex items-center gap-4 text-xs xl:text-sm font-sans font-black uppercase tracking-widest text-black">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-yellow-400 via-white to-blue-500 p-[2px] shadow-lg animate-spin-gradient">
                        <div className="w-full h-full bg-black rounded-full flex items-center justify-center">
                          <Sparkles className="w-5 h-5 text-yellow-400" fill="currentColor"/>
                        </div>
                      </div>
                      Curated Results for your POSE
                    </div>
                    <div className="flex items-center gap-3 bg-gray-100 p-2 rounded-2xl">
                      <button
                        onClick={() => handleFeedback('like')}
                        className={cn(
                          "flex items-center gap-2 px-8 py-3 rounded-xl text-xs xl:text-sm font-sans font-black tracking-widest uppercase transition-all",
                          feedbackType === 'like' 
                            ? "bg-black text-white shadow-xl scale-105" 
                            : "bg-transparent text-gray-500 hover:bg-white hover:shadow-sm"
                        )}
                      >
                        <ThumbsUp className="w-4 h-4" /> Like
                      </button>
                      <button
                        onClick={() => handleFeedback('dislike')}
                        className={cn(
                          "flex items-center gap-2 px-8 py-3 rounded-xl text-xs xl:text-sm font-sans font-black tracking-widest uppercase transition-all",
                          feedbackType === 'dislike' 
                            ? "bg-red-500 text-white shadow-xl scale-105" 
                            : "bg-transparent text-gray-500 hover:bg-white hover:shadow-sm"
                        )}
                      >
                        <ThumbsDown className="w-4 h-4" /> Dislike
                      </button>
                    </div>
                  </div>

                  <AnimatePresence>
                    {showFeedbackReason && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="mb-10 overflow-hidden"
                      >
                        <div className="p-8 bg-gray-50 rounded-[2.5rem] border border-gray-100 space-y-5">
                          <p className="text-sm xl:text-base font-sans font-black text-black uppercase tracking-tight">
                            {feedbackType === 'like' ? "What defined this POSE?" : "How can we refine your POSE?"}
                          </p>
                          <div className="flex flex-col sm:flex-row gap-4">
                            <input
                              type="text"
                              placeholder="Leave a quick note..."
                              value={feedbackReason}
                              onChange={(e) => setFeedbackReason(e.target.value)}
                              className="flex-1 px-6 py-4 bg-white border-none rounded-2xl text-base font-medium focus:outline-none focus:ring-2 focus:ring-black shadow-lg shadow-gray-100"
                            />
                            <button
                              onClick={submitFeedbackReason}
                              className="px-10 py-4 bg-black text-white rounded-2xl text-xs font-sans font-black tracking-widest uppercase hover:bg-gray-800 transition-all flex items-center justify-center gap-2.5 h-[56px] sm:h-auto"
                            >
                              <Send className="w-4 h-4" /> Submit
                            </button>
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  <div className="markdown-body prose-headings:font-serif prose-headings:font-black prose-headings:tracking-tighter prose-headings:uppercase prose-a:text-blue-600 prose-a:font-bold prose-lg prose-gray max-w-none text-gray-800 font-sans font-medium prose-strong:font-black">
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
              className="max-w-5xl mx-auto space-y-20 py-12"
            >
              <div className="flex flex-col md:flex-row items-start md:items-end justify-between gap-10 border-b border-black/10 pb-16">
                <div className="space-y-6">
                  <div className="w-32 h-32 rounded-full bg-gradient-to-tr from-yellow-400 via-white to-blue-500 p-[4px] shadow-2xl shadow-black/10 animate-spin-gradient">
                    <div className="w-full h-full bg-white rounded-full flex items-center justify-center overflow-hidden">
                      <User className="w-16 h-16 text-black" />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <h2 className="text-6xl font-serif font-black tracking-tighter text-black uppercase bg-clip-text text-transparent bg-gradient-to-r from-black to-gray-500 animate-text-gradient">
                      {user?.username || 'Anonymous'}
                    </h2>
                    <p className="text-xs font-sans font-black text-gray-400 uppercase tracking-widest bg-gray-100 inline-block px-4 py-1.5 rounded-full border border-gray-200">
                      POSE Creator No. {user?.id || '000'}
                    </p>
                  </div>
                </div>
                <div className="text-left md:text-right max-w-sm">
                  <p className="text-3xl xl:text-4xl font-serif font-black text-black leading-tight tracking-tighter uppercase bg-clip-text text-transparent bg-gradient-to-r from-black to-gray-500">
                    "My Vibe is<br/>My POSE."
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-12 gap-16 p-6 bg-white/5 backdrop-blur-sm rounded-[3rem] border border-black/5">
                <div className="lg:col-span-4 space-y-8">
                  <div className="flex items-center gap-4 text-[11px] xl:text-xs font-sans font-black uppercase tracking-[0.3em] text-blue-600 bg-blue-50 px-4 py-2 rounded-full border border-blue-100 w-auto inline-flex">
                    <Zap className="w-4 h-4 text-yellow-400" fill="currentColor" />
                    Taste Analysis
                  </div>
                  <h3 className="text-4xl xl:text-5xl font-serif font-black tracking-tighter leading-none uppercase bg-clip-text text-transparent bg-gradient-to-r from-black via-gray-700 to-black animate-text-gradient">
                    The Patterns<br/>of your<br/>Choices.
                  </h3>
                  <div className="h-3 w-16 bg-gradient-to-r from-yellow-400 to-blue-500 rounded-full" />
                </div>

                <div className="lg:col-span-8">
                  {taste ? (
                    <div className="bg-gray-50 p-10 md:p-16 rounded-[4rem] border border-gray-100 space-y-12">
                      <div className="markdown-body font-medium text-gray-800 text-lg leading-relaxed prose-p:mb-8 prose-strong:font-black prose-strong:text-black font-sans prose-headings:font-serif prose-headings:uppercase">
                        <Markdown>{taste}</Markdown>
                      </div>
                      
                      <div className="pt-10 border-t border-gray-200 flex flex-wrap items-center justify-end gap-4">
                        <button 
                          onClick={handleGenerateTaste}
                          disabled={isGenDownloadStoryCard}
                          className="flex items-center gap-2.5 px-8 py-3.5 bg-gradient-to-r from-pink-500 to-orange-500 hover:from-pink-600 hover:to-orange-600 text-white rounded-full text-xs font-sans font-black tracking-widest uppercase transition-all shadow-xl shadow-pink-500/20 h-[50px]"
                        >
                          <Instagram className="w-5 h-5" />
                          {'스토리 카드 다운로드'}
                        </button>
                        <button 
                          onClick={handleeratingTaste}
                          className="flex items-center gap-2.5 px-8 py-3.5 bg-white hover:bg-gray-100 text-black rounded-full text-xs font-sans font-black tracking-widest uppercase transition-all shadow-md shadow-gray-200 border border-gray-100 h-[50px]"
                        >
                          {isGeneratingTaste ? <Loader2 className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5 text-yellow-400" fill="currentColor"/>}
                          {isGeneratingTaste ? 'Re-Analyzing...' : 'Analyze Again'}
                        </button>
                        <button 
                          onClick={handleShareProfile}
                          disabled={isSharingProfile}
                          className="flex items-center gap-2.5 px-8 py-3.5 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white rounded-full text-xs font-sans font-black tracking-widest uppercase transition-all shadow-xl shadow-purple-500/20 h-[50px]"
                        >
                          {isSharingProfile ? <Loader2 className="w-5 h-5 animate-spin" /> : <Instagram className="w-5 h-5" />}
                          {isSharingProfile ? 'Preparing...' : 'Share My POSE'}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="py-28 bg-gray-50 rounded-[3rem] flex flex-col items-center justify-center text-center space-y-10 px-6 border-2 border-dashed border-gradient-r-from-yellow-400 border-r-to-blue-500 backdrop-blur-sm animate-pulse-border">
                      <div className="w-24 h-24 bg-white/50 backdrop-blur-sm rounded-full flex items-center justify-center shadow-lg border border-white/20">
                        <Sparkles className="w-10 h-10 text-yellow-300" fill="currentColor" />
                      </div>
                      
                      {items.length > 0 ? (
                        <div className="space-y-8 flex flex-col items-center">
                          <p className="text-gray-500 font-bold text-xl xl:text-2xl max-w-sm">
                            충분한 영감이 모였습니다.<br/>당신의 무의식적인 패턴을 꺼내볼까요?
                          </p>
                          <button 
                            onClick={handleGenerateTaste}
                            disabled={isGeneratingTaste}
                            className="px-12 py-5 bg-black text-white rounded-full text-sm xl:text-base font-sans font-black tracking-widest uppercase hover:bg-gray-800 hover:scale-105 active:scale-95 transition-all flex items-center gap-3.5 disabled:opacity-50 shadow-2xl shadow-black/20"
                          >
                            {isGeneratingTaste ? <Loader2 className="w-6 h-6 animate-spin" /> : <Zap className="w-6 h-6 text-yellow-300" fill="currentColor" />}
                            {isGeneratingTaste ? 'Analyzing My POSE...' : 'Show My POSE'}
                          </button>
                        </div>
                      ) : (
                        <div className="space-y-6 flex flex-col items-center">
                          <p className="text-gray-400 font-bold text-lg xl:text-xl">아직 수집된 영감이 없습니다.</p>
                          <button 
                            onClick={() => setActiveTab('feed')}
                            className="px-10 py-3.5 bg-white border-2 border-gray-100 text-black rounded-full text-xs xl:text-sm font-sans font-black uppercase tracking-widest hover:border-black transition-all shadow-lg shadow-gray-100"
                          >
                            Explore Feed
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              <div className="space-y-10 pt-16 border-t border-black/10">
                <div className="flex items-center justify-between">
                  <h4 className="text-2xl xl:text-3xl font-serif font-black uppercase tracking-tighter text-black">
                    Recent Inspirations
                  </h4>
                  <div className="text-xs font-sans font-black text-gray-400 uppercase tracking-widest bg-gray-100 px-4 py-1.5 rounded-full border border-gray-200">
                    {items.length} Items Captured
                  </div>
                </div>
                <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-4">
                  {Array.isArray(items) && items.slice(0, 16).map((item) => (
                    <div 
                      key={item.id} 
                      className="aspect-square bg-white/5 backdrop-blur-sm border border-black/5 overflow-hidden cursor-pointer group relative rounded-3xl hover:shadow-2xl hover:-translate-y-1.5 transition-all duration-300 shadow-lg shadow-black/5"
                      onClick={() => setSelectedItem(item)}
                    >
                      <img 
                        src={item.image_url ? `/api/images/${item.image_url}` : 'https://via.placeholder.com/400x500?text=No+Image'}
                        className="w-full h-full object-cover grayscale opacity-70 group-hover:opacity-100 group-hover:grayscale-0 transition-all duration-500 group-hover:scale-110 ease-in-out" 
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
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-6 bg-black/80 backdrop-blur-lg" onClick={() => setSelectedItem(null)}>
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 30 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 30 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white/5 backdrop-blur-md w-full max-w-5xl rounded-[4rem] overflow-hidden shadow-2xl shadow-black/30 flex flex-col md:flex-row max-h-[95vh] border-2 border-white/10"
            >
              <div className="md:w-1/2 bg-gray-50 flex items-center justify-center overflow-hidden p-8 lg:p-12 relative border-r-2 border-white/10">
                <img 
                  src={selectedItem.image_url ? `/api/images/${selectedItem.image_url}` : 'https://via.placeholder.com/600x600?text=No+Image'} 
                  alt={selectedItem.category}
                  className="w-full h-auto object-contain rounded-3xl shadow-xl shadow-black/10"
                  referrerPolicy="no-referrer"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src = 'https://via.placeholder.com/600x600?text=No+Image';
                  }}
                />
              </div>
              <div className="md:w-1/2 p-10 md:p-14 flex flex-col bg-white">
                <div className="flex items-center justify-between mb-10 pb-6 border-b border-gray-100">
                  <span className="text-[11px] font-sans font-black uppercase tracking-widest text-black bg-yellow-300 px-4 py-2 rounded-full border border-yellow-400">
                    {selectedItem.category}
                  </span>
                  <button 
                    onClick={() => setSelectedItem(null)}
                    className="p-3 hover:bg-gray-100 rounded-full transition-all shadow-md shadow-black/5"
                  >
                    <X className="w-7 h-7" />
                  </button>
                </div>
                
                <div className="flex-1 overflow-y-auto space-y-12 pr-5 custom-scrollbar font-sans text-gray-800">
                  <section>
                    <h3 className="text-xs xl:text-sm font-sans font-black text-gray-400 uppercase tracking-widest mb-4 flex items-center gap-2">
                      <Zap className="w-4 h-4 text-yellow-300" fill="currentColor"/> Vibe Analysis
                    </h3>
                    <p className="text-xl xl:text-2xl font-serif font-black leading-tight text-black tracking-tight">{selectedItem.vibe}</p>
                  </section>

                  <section>
                    <h3 className="text-xs xl:text-sm font-sans font-black text-gray-400 uppercase tracking-widest mb-5">Extracted Information</h3>
                    <div className="grid grid-cols-1 gap-5">
                      {(() => {
                        const facts = typeof selectedItem.facts === 'string' 
                          ? JSON.parse(selectedItem.facts) 
                          : selectedItem.facts;

                        return facts && typeof facts === 'object' ? (
                          Object.entries(facts).map(([key, value]) => (
                            <div key={key} className="group/fact bg-gray-50 p-6 rounded-3xl border border-gray-100 shadow-sm">
                              <dt className="text-[10px] font-sans font-black text-gray-400 uppercase tracking-widest mb-2.5">
                                {key.replace(/_/g, ' ')}
                              </dt>
                              <dd className="text-base xl:text-lg font-sans font-semibold text-black leading-snug">
                                {Array.isArray(value) ? (
                                  <div className="flex flex-wrap gap-2.5 pt-1">
                                    {value.map((val, i) => (
                                      <span key={i} className="px-3.5 py-1.5 bg-white border border-gray-200 rounded-xl text-[11px] xl:text-xs font-black shadow-md shadow-gray-100">
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
                          <p className="text-base text-gray-400 font-medium italic">No detailed facts available.</p>
                        );
                      })()}
                    </div>
                  </section>

                  <section className="border-t border-gray-100 pt-10">
                    <h3 className="text-xs xl:text-sm font-sans font-black text-gray-400 uppercase tracking-widest mb-5">Review Insights</h3>
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
                        <div className="bg-yellow-50/50 p-8 rounded-4xl border border-yellow-100/50 shadow-lg shadow-yellow-500/5">
                          <div className="flex items-center gap-2 mb-4">
                            <span className="text-sm xl:text-base font-sans font-black text-black uppercase tracking-tight">
                              {reviewData.star_review || "Recommended"}
                            </span>
                            <div className="flex text-yellow-400">
                              {"★".repeat(Math.min(5, Math.floor(parseFloat(reviewData.star_review) || 5)))}
                            </div>
                          </div>
                          <p className="text-lg font-serif font-black leading-tight text-gray-900 tracking-tight italic">
                            "{reviewData.core_summary || reviewData.review || "No summary available"}"
                          </p>
                        </div>
                      ) : (
                        <p className="text-base text-gray-400 font-medium italic">No review data extracted for this item.</p>
                      );
                    })()}
                  </section>

                  {selectedItem.url && (
                    <section className="pt-6">
                      <a 
                        href={selectedItem.url} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="flex items-center justify-center gap-2.5 w-full py-5 bg-gradient-to-r from-gray-50 to-gray-100 hover:from-gray-100 hover:to-gray-200 text-black rounded-2xl text-[11px] font-sans font-black uppercase tracking-widest transition-colors shadow-lg shadow-gray-200/50"
                      >
                        <Instagram className="w-5 h-5" />
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
        "flex items-center gap-4.5 p-5 w-full rounded-3xl transition-all duration-300 backdrop-blur-sm",
        active 
          ? "bg-gradient-to-tr from-yellow-400 via-white to-blue-500 shadow-xl shadow-yellow-500/10 text-black font-serif font-black tracking-tighter" 
          : "hover:bg-white/5 text-gray-500 hover:text-black font-sans font-medium"
      )}
    >
      <div className={cn("shrink-0 w-7 h-7 flex items-center justify-center", active && "text-black")}>
        {icon}
      </div>
      <span className="hidden md:block text-sm xl:text-base tracking-widest uppercase">{label}</span>
    </button>
  );
}