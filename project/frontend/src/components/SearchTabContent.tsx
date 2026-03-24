import { motion, AnimatePresence } from 'framer-motion';
import { Search, Loader2, Sparkles, ThumbsUp, ThumbsDown, Send } from 'lucide-react';
import Markdown from 'react-markdown';
import { useEffect, useState } from 'react';

import type { SavedItem } from '../App';

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
  const [feedbackType, setFeedbackType] = useState<'like' | 'dislike' | null>(null);
  const [feedbackReason, setFeedbackReason] = useState("");
  const [showFeedbackReason, setShowFeedbackReason] = useState(false);
  const [loading, setLoading] = useState(false);
  const [quotaCountdown, setQuotaCountdown] = useState<number | null>(null);
  const [searchResults, setSearchResults] = useState<string | null>(null);

  useEffect(() => {
    if (!searchResults) {
      setFeedbackType(null);
      setFeedbackReason("");
      setShowFeedbackReason(false);
    }
  }, [searchResults]);

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
      if (!res.ok) throw new Error(data.detail || "Search failed");
      setSearchResults(data.result || null);
    } catch (error: any) {
      console.error(error);
      alert(error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveSearchResult = async (silent = false) => {
    if (!searchResults || !user) return;
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
      onItemsChange((previousItems) => [newItem, ...previousItems]);

      if (!silent) alert("Saved to your feed!");
      await refreshTaste();
    } catch (error: any) {
      console.error(error);
      if (!silent) alert(error.message);
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
      await refreshTaste();
      setShowFeedbackReason(false);
      setFeedbackReason("");
    } catch (error) {
      console.error("Failed to submit feedback:", error);
    }
  };

  return (
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
                onClick={() => {
                  if (!searchResults) return;
                  void handleFeedback('like');
                }}
                className={[
                  "flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs font-black tracking-widest uppercase transition-all",
                  feedbackType === 'like'
                    ? "bg-black text-white shadow-md"
                    : "bg-transparent text-gray-500 hover:bg-white hover:shadow-sm",
                ].join(' ')}
              >
                <ThumbsUp className="w-3.5 h-3.5" /> Like
              </button>
              <button
                onClick={() => {
                  if (!searchResults) return;
                  void handleFeedback('dislike');
                }}
                className={[
                  "flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs font-black tracking-widest uppercase transition-all",
                  feedbackType === 'dislike'
                    ? "bg-red-500 text-white shadow-md"
                    : "bg-transparent text-gray-500 hover:bg-white hover:shadow-sm",
                ].join(' ')}
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
                      onClick={async () => {
                        if (!searchResults || !feedbackType) return;
                        await submitFeedbackReason();
                      }}
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
  );
}
