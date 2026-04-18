import { useMutation } from '@tanstack/react-query';
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

  const factKeysToShow = ['title', 'price_info', 'location_text', 'time_info', 'key_details'];
  const categories = useMemo(
    () => ['All', ...Array.from(new Set(items.map((item) => item.category))).filter(Boolean)],
    [items]
  );
  const filteredItems = useMemo(
    () => (selectedCategory === 'All' ? items : items.filter((item) => item.category === selectedCategory)),
    [items, selectedCategory]
  );

  const addItemMutation = useMutation({
    mutationFn: async ({ nextUrl, nextSessionId, userId }: { nextUrl: string; nextSessionId: string; userId: number }) => {
      const res = await fetch('/api/extract-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: nextUrl, session_id: nextSessionId, user_id: userId })
      });

      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || "Failed to analyze URL");
      }

      return {
        nextUrl,
        data: await res.json(),
      };
    },
    onSuccess: ({ nextUrl, data }) => {
      if (data.success && data.status === 'processing') {
        alert(`✨ ${data.message}`);
      } else if (data.success && data.data && Array.isArray(data.data)) {
        const newItems = data.data.map((item: any, index: number) => ({
          id: Date.now() + index,
          url: nextUrl,
          category: item.category || 'General',
          facts: item.facts || {},
          recommend: item.recommend || 'Extracted',
          image_url: item.image_url || '',
          created_at: new Date().toISOString(),
          summary_text: item.summary_text || ''
        }));
        onItemsChange((prev) => [...newItems, ...prev]);
      }

      setNewUrl("");
      setSessionId("");

      window.setTimeout(() => {
        void refreshItems();
        void refreshTaste();
      }, 3000);
    },
    onError: (error: Error) => {
      console.error(error);
      alert(`분석 요청 중 오류가 발생했습니다: ${error.message}`);
    },
  });

  const deleteItemMutation = useMutation({
    mutationFn: async ({ id, userId }: { id: number; userId: number }) => {
      const res = await fetch(`/api/items/${id}?user_id=${userId}`, { method: 'DELETE' });

      if (!res.ok) {
        throw new Error('Failed to delete item');
      }

      return id;
    },
    onMutate: async ({ id }) => {
      const previousItems = items;
      onItemsChange((currentItems) => currentItems.filter((item) => item.id !== id));
      return { previousItems };
    },
    onError: (error, _variables, context) => {
      console.error('Delete failed:', error);
      if (context?.previousItems) {
        onItemsChange(context.previousItems);
      }
      alert('삭제 중 오류가 발생했습니다.');
    },
  });

  const handleAddItem = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!newUrl || !user) return;
    await addItemMutation.mutateAsync({
      nextSessionId: sessionId,
      nextUrl: newUrl,
      userId: user.id,
    });
  };

  const handleDelete = async (id: number) => {
    if (!user) return;
    const shouldDelete = window.confirm('정말로 삭제하십니까?');
    if (!shouldDelete) return;
    await deleteItemMutation.mutateAsync({ id, userId: user.id });
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
            <label className="text-[10px] font-black text-gray-400 uppercase tracking-widest">Instagram or Product URL or just a name</label>
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
            disabled={addItemMutation.isPending}
            className="w-full sm:w-auto px-8 py-3 bg-black text-white rounded-2xl hover:bg-gray-800 hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-50 disabled:transform-none transition-all flex items-center justify-center gap-2 text-sm font-black tracking-widest uppercase h-[44px]"
          >
            {addItemMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
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

      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4 items-stretch">
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

      {items.length === 0 && !addItemMutation.isPending && (
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
