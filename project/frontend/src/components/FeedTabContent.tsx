import { motion } from 'framer-motion';
import { Plus, Loader2, Zap } from 'lucide-react';
import { useMemo, useState, type FormEvent } from 'react';

import type { SavedItem } from '../types/item';
import type { AppUser } from '../types/user';
import { FeedItemCard } from './FeedItemCard';

type FeedTabContentProps = {
  items: SavedItem[];
  onItemsChange: React.Dispatch<React.SetStateAction<SavedItem[]>>;
  onSelectItem: (item: SavedItem) => void;
  refreshItems: () => Promise<void>;
  refreshTaste: () => Promise<void>;
  user: AppUser | null;
};

export function FeedTabContent({
  items,
  onItemsChange,
  onSelectItem,
  refreshItems,
  refreshTaste,
  user,
}: FeedTabContentProps) {
  const [newUrl, setNewUrl] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [loading, setLoading] = useState(false);

  const factKeysToShow = ['title', 'price_info', 'location_text', 'time_info', 'key_details'];
  const categories = useMemo(
    () => ['All', ...Array.from(new Set(items.map((item) => item.category))).filter(Boolean)],
    [items]
  );
  const filteredItems = useMemo(
    () => (selectedCategory === 'All' ? items : items.filter((item) => item.category === selectedCategory)),
    [items, selectedCategory]
  );

  const handleAddItem = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
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

      const responseData = await res.json();
      if (responseData.success && responseData.status === 'processing') {
        alert(`✨ ${responseData.message}`);
      } else if (responseData.success && responseData.data && Array.isArray(responseData.data)) {
        const newItems = responseData.data.map((item: any, index: number) => ({
          id: Date.now() + index,
          url: newUrl,
          category: item.category || 'General',
          facts: item.facts || {},
          vibe: item.vibe_text || 'Extracted',
          image_url: item.image_url || '',
          created_at: new Date().toISOString(),
          summary_text: item.summary_text || ''
        }));
        onItemsChange([...newItems, ...items]);
      }

      setNewUrl("");
      setSessionId("");

      window.setTimeout(() => {
        void refreshItems();
        void refreshTaste();
      }, 3000);

    } catch (error: any) {
      console.error(error);
      alert(`분석 요청 중 오류가 발생했습니다: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!user) return;
    const shouldDelete = window.confirm('정말로 삭제하십니까?');
    if (!shouldDelete) return;

    const previousItems = items;
    onItemsChange((currentItems) => currentItems.filter((item) => item.id !== id));

    try {
      await fetch(`/api/items/${id}?user_id=${user.id}`, { method: 'DELETE' });
    } catch (error) {
      console.error('Delete failed:', error);
      onItemsChange(previousItems);
      alert('삭제 중 오류가 발생했습니다.');
    }
  };

  return (
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

      {items.length > 0 && (
        <div className="flex flex-wrap gap-2 py-2">
          {categories.map((category) => (
            <button
              key={category}
              onClick={() => setSelectedCategory(category)}
              className={[
                "px-5 py-2 rounded-full text-[11px] font-black uppercase tracking-widest transition-all",
                selectedCategory === category
                  ? "bg-black text-white shadow-md scale-105"
                  : "bg-gray-100 text-gray-500 hover:bg-gray-200",
              ].join(' ')}
            >
              {category}
            </button>
          ))}
        </div>
      )}

      <div className="columns-2 md:columns-3 lg:columns-4 gap-4 space-y-4 mt-4">
        {filteredItems.map((item) => (
          <FeedItemCard
            key={item.id}
            factKeysToShow={factKeysToShow}
            item={item}
            onDelete={handleDelete}
            onSelect={() => onSelectItem(item)}
          />
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
  );
}
