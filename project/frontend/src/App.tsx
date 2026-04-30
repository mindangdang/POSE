import { useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import * as Tabs from '@radix-ui/react-tabs';
import {
  Grid,
  Menu,
  Search,
  User,
} from 'lucide-react';
import { FeedTabContent } from './components/FeedTabContent';
import { ItemDetailDialog } from './components/ItemDetailDialog';
import { NavItem } from './components/NavItem';
import { ProfileTabContent } from './components/ProfileTabContent';
import { SearchTabContent } from './components/SearchTabContent';
import { useItems } from './hooks/useItems';
import { useTaste } from './hooks/useTaste';
import type { SavedItem } from './types/item';
import type { AppUser } from './types/user';

export default function App() {
  const [user] = useState<AppUser>({ id: 1, username: 'guest' });
  const [selectedItem, setSelectedItem] = useState<SavedItem | null>(null);
  const [currentTab, setCurrentTab] = useState<'feed' | 'search' | 'profile'>('search');
  const [isNavExpanded, setIsNavExpanded] = useState(true);
  const { items, setItems, refreshItems } = useItems(user);
  const { taste, setTaste, refreshTaste } = useTaste(user);

  return (
    <>
      <Tabs.Root
        value={currentTab}
        onValueChange={(value) => setCurrentTab(value as 'feed' | 'search' | 'profile')}
        orientation="vertical"
        className="relative min-h-screen bg-white text-black font-sans selection:bg-yellow-300 selection:text-black"
      >
        <div
          className={[
            "group fixed z-20 top-0 bottom-0 bg-linear-to-b from-blue-500 via-yellow-300 to-purple-500 shadow-2xl shadow-black rounded-r-4xl",
            "transition-[width] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
            isNavExpanded ? "w-50" : "w-20",
          ].join(" ")}
        >
          <div className="absolute left-0 top-0 z-10 h-full w-0.5 bg-black" />
          <div
            className="absolute bottom-0 left-0.5 right-0.5 top-0 flex flex-col overflow-visible bg-black rounded-r-[calc(2.2rem)]"
          >
            <button
              type="button"
              aria-label={isNavExpanded ? "Hide navigation tabs" : "Show navigation tabs"}
              onClick={() => setIsNavExpanded((expanded) => !expanded)}
              className="mt-8 flex h-10 w-full items-center overflow-hidden rounded-xl text-left text-white transition-colors duration-200"
            >
              <span className="flex h-10 w-17.5 shrink-0 items-center justify-center">
                <Menu className="h-5 w-5 transition-transform hover:scale-120"/>
              </span>
              <span
                className={[
                  "block overflow-hidden whitespace-nowrap text-xs font-black uppercase tracking-widest transition-[max-width,opacity,transform] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
                  isNavExpanded ? "max-w-0 translate-x-0 delay-75" : "max-w-0 -translate-x-1 opacity-0",
                ].join(" ")}
              >
              </span>
            </button>

            <Tabs.List
              aria-label="POSE sections"
              className="flex w-full flex-1 flex-col items-center justify-start gap-4 overflow-visible pt-10"
            >
              <NavItem
                expanded={isNavExpanded}
                value="search"
                icon={<Search className="w-5 h-5" />}
                label="검색"
              />
              <NavItem
                expanded={isNavExpanded}
                value="feed"
                icon={<Grid className="w-5 h-5" />}
                label="피드"
              />
              <NavItem
                expanded={isNavExpanded}
                value="profile"
                icon={<User className="w-5 h-5" />}
                label="테이스팅"
              />
            </Tabs.List>

            <div className="mb-6 flex h-12 w-full items-center overflow-hidden rounded-xl text-left text-white/80">
              <span className="flex h-12 w-17 shrink-0 items-center justify-center">
                <span className="h-8 w-8 rounded-full bg-linear-to-tr from-blue-500 via-yellow-300 to-purple-500 p-0.5">
                  <span className="block h-full w-full rounded-full bg-black" />
                </span>
              </span>
              <span
                className={[
                  "block overflow-hidden whitespace-nowrap text-sm font-bold tracking-tight transition-[max-width,opacity,transform] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
                  isNavExpanded ? "max-w-28 translate-x-0 opacity-100 delay-75" : "max-w-0 -translate-x-1 opacity-0",
                ].join(" ")}
              >
                @{user.username}
              </span>
            </div>
          </div>
        </div>

        <main className="mx-auto flex min-h-screen w-full max-w-5xl items-center justify-center p-4 md:p-8 overflow-x-hidden">
          <AnimatePresence mode="wait">
            {currentTab === 'feed' && (
              <Tabs.Content value="feed" forceMount className="w-full">
                <FeedTabContent
                  items={items}
                  onItemsChange={setItems}
                  onSelectItem={setSelectedItem}
                  refreshItems={refreshItems}
                  refreshTaste={refreshTaste}
                  user={user}
                />
              </Tabs.Content>
            )}

            {currentTab === 'search' && (
              <Tabs.Content value="search" forceMount className="w-full">
                <SearchTabContent
                  onItemsChange={setItems}
                  refreshTaste={refreshTaste}
                  user={user}
                />
              </Tabs.Content>
            )}

            {currentTab === 'profile' && (
              <Tabs.Content value="profile" forceMount className="w-full">
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
