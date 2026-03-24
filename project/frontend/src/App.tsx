import React, { useState, useEffect } from 'react';
import { AnimatePresence } from 'framer-motion';
import * as Tabs from '@radix-ui/react-tabs';
import {
  Search,
  Grid,
  User,
  Zap,
} from 'lucide-react';

import { FeedTabContent } from './components/FeedTabContent';
import { ItemDetailDialog } from './components/ItemDetailDialog';
import { NavItem } from './components/NavItem';
import { ProfileTabContent } from './components/ProfileTabContent';
import { SearchTabContent } from './components/SearchTabContent';
import type { SavedItem } from './types/item';

export default function App() {
  const [user] = useState<{ id: number; username: string }>({ id: 1, username: 'guest' });
  const [items, setItems] = useState<SavedItem[]>([]);
  const [selectedItem, setSelectedItem] = useState<SavedItem | null>(null);
  const [taste, setTaste] = useState<string>('');
  const [currentTab, setCurrentTab] = useState<'feed' | 'search' | 'profile'>('feed');

  useEffect(() => {
    if (user) {
      void fetchItems();
      void fetchTaste();
    }
  }, [user]);

  const fetchItems = async () => {
    if (!user) return;
    try {
      const res = await fetch(`/api/items?user_id=${user.id}`, { cache: 'no-store' });
      const data = await res.json();
      setItems(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Failed to fetch items:', error);
      setItems([]);
    }
  };

  const fetchTaste = async () => {
    if (!user) return;
    try {
      const res = await fetch(`/api/taste?user_id=${user.id}`, { cache: 'no-store' });
      const data = await res.json();
      setTaste(data?.summary || '');
    } catch (error) {
      console.error('Failed to fetch taste:', error);
      setTaste('');
    }
  };

  return (
    <>
      <Tabs.Root
        value={currentTab}
        onValueChange={(value) => setCurrentTab(value as 'feed' | 'search' | 'profile')}
        orientation="vertical"
        className="min-h-screen bg-white text-black font-sans flex selection:bg-yellow-300 selection:text-black"
      >
        <nav className="w-20 md:w-64 border-r border-black/10 h-screen sticky top-0 bg-white flex flex-col p-4 z-10">
          <button
            type="button"
            onClick={() => {
              setCurrentTab('feed');
              setSelectedItem(null);
            }}
            className="mb-12 px-2 flex items-center gap-3 text-left transition-transform hover:scale-[1.02]"
          >
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-500 via-yellow-300 to-purple-500 p-[2px] shadow-sm shrink-0">
              <div className="w-full h-full bg-black rounded-[10px] flex items-center justify-center">
                <Zap className="w-5 h-5 text-white" fill="white" />
              </div>
            </div>
            <h1 className="text-3xl font-black tracking-tighter uppercase hidden md:block">
              POSE!
            </h1>
          </button>

          <Tabs.List aria-label="POSE sections" className="space-y-3 flex-1">
            <NavItem value="feed" icon={<Grid className="w-5 h-5" />} label="Feed" />
            <NavItem value="search" icon={<Search className="w-5 h-5" />} label="Agentic Search" />
            <NavItem value="profile" icon={<User className="w-5 h-5" />} label="Taste Profile" />
          </Tabs.List>

          <div className="mt-auto space-y-2">
            <div className="flex items-center gap-3 p-3 w-full rounded-2xl bg-gray-50 border border-black/5">
              <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-500 via-yellow-300 to-purple-500 p-[2px]">
                <div className="w-full h-full bg-white rounded-full"></div>
              </div>
              <span className="hidden md:block font-bold text-sm tracking-tight">@{user.username}</span>
            </div>
          </div>
        </nav>

        <main className="flex-1 max-w-5xl mx-auto p-4 md:p-8 overflow-x-hidden">
          <AnimatePresence mode="wait">
            {currentTab === 'feed' && (
              <Tabs.Content value="feed" forceMount>
                <FeedTabContent
                  items={items}
                  onItemsChange={setItems}
                  onSelectItem={setSelectedItem}
                  refreshItems={fetchItems}
                  refreshTaste={fetchTaste}
                  user={user}
                />
              </Tabs.Content>
            )}

            {currentTab === 'search' && (
              <Tabs.Content value="search" forceMount>
                <SearchTabContent
                  onItemsChange={setItems}
                  refreshTaste={fetchTaste}
                  user={user}
                />
              </Tabs.Content>
            )}

            {currentTab === 'profile' && (
              <Tabs.Content value="profile" forceMount>
                <ProfileTabContent
                  items={items}
                  onGoToFeed={() => setCurrentTab('feed')}
                  onSelectItem={setSelectedItem}
                  onTasteChange={setTaste}
                  taste={taste}
                  user={user}
                />
              </Tabs.Content>
            )}
          </AnimatePresence>
        </main>
      </Tabs.Root>

      <ItemDetailDialog
        item={selectedItem}
        onOpenChange={(open) => {
          if (!open) setSelectedItem(null);
        }}
      />
    </>
  );
}
