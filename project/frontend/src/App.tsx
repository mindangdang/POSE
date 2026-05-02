import { useState, useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import * as Tabs from '@radix-ui/react-tabs';
import {
  Grid,
  Menu,
  LogOut,
  Search,
  User,
} from 'lucide-react';
import { GoogleLoginButton } from './components/GoogleLoginButton';
import { FeedTabContent } from './components/FeedTabContent';
import { ItemDetailDialog } from './components/ItemDetailDialog';
import { NavItem } from './components/NavItem';
import { ProfileTabContent } from './components/ProfileTabContent';
import { SearchTabContent } from './components/SearchTabContent';
import { useItems } from './hooks/useItems';
import { useTaste } from './hooks/useTaste';
import type { SavedItem } from './types/item';
import type { AppUser } from './types/user';

// 유저가 로그인되었을 때만 렌더링될 메인 앱 컴포넌트
function MainApp({ user, onLogout }: { user: AppUser; onLogout: () => void }) {
  const [selectedItem, setSelectedItem] = useState<SavedItem | null>(null);
  const [currentTab, setCurrentTab] = useState<'feed' | 'search' | 'profile'>('search');
  const [isNavExpanded, setIsNavExpanded] = useState(true);
  const [isLogoutModalOpen, setIsLogoutModalOpen] = useState(false);
  
  // MainApp은 user가 반드시 존재할 때만 렌더링되므로, Null 에러가 발생하지 않습니다.
  const { items, setItems, refreshItems } = useItems(user);
  const { taste, setTaste, refreshTaste } = useTaste(user);

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    setIsLogoutModalOpen(false);
    onLogout();
  };

  return (
    <>
      <Tabs.Root
        value={currentTab}
        onValueChange={(value: string) => setCurrentTab(value as 'feed' | 'search' | 'profile')}
        orientation="vertical"
        className="relative h-screen overflow-hidden bg-white text-black font-sans selection:bg-yellow-300 selection:text-black"
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

            <div className="mb-4 flex flex-col gap-1 w-full">
              <div className="flex h-12 w-full items-center overflow-hidden rounded-xl text-left text-white/80">
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
                  {/* 백엔드에서 넘겨주는 이름(name)을 우선적으로 사용하도록 처리 */}
                  @{user.name || user.username || 'user'}
                </span>
              </div>

              <button
                onClick={() => setIsLogoutModalOpen(true)}
                title="로그아웃"
                className="flex h-10 w-full items-center overflow-hidden rounded-xl text-left text-red-400/80 transition-colors hover:bg-white/10 hover:text-red-400"
              >
                <span className="flex h-10 w-17 shrink-0 items-center justify-center">
                  <LogOut className="h-5 w-5" />
                </span>
                <span
                  className={[
                    "block overflow-hidden whitespace-nowrap text-xs font-bold transition-[max-width,opacity,transform] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
                    isNavExpanded ? "max-w-28 translate-x-0 opacity-100 delay-75" : "max-w-0 -translate-x-1 opacity-0",
                  ].join(" ")}
                >
                  로그아웃
                </span>
              </button>
            </div>
          </div>
        </div>

        <main
          className={[
            "mx-auto flex h-screen w-full max-w-5xl justify-center overflow-x-hidden p-4 md:p-8",
            currentTab === 'feed' ? "items-stretch overflow-hidden" : "items-center overflow-y-auto",
          ].join(" ")}
        >
          <AnimatePresence mode="wait">
            {currentTab === 'feed' && (
              <Tabs.Content value="feed" forceMount className="h-full w-full">
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
                  refreshItems={refreshItems}
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

      {/* 로그아웃 확인 모달 */}
      <AnimatePresence>
        {isLogoutModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-sm rounded-3xl bg-white p-6 shadow-2xl"
            >
              <h3 className="mb-2 text-center text-lg font-black text-gray-900">로그아웃</h3>
              <p className="mb-6 text-center text-sm font-medium text-gray-500">정말 로그아웃 하시겠습니까?</p>
              <div className="flex gap-3">
                <button
                  onClick={() => setIsLogoutModalOpen(false)}
                  className="flex-1 rounded-xl bg-gray-100 py-3 text-sm font-bold text-gray-700 transition-colors hover:bg-gray-200"
                >
                  취소
                </button>
                <button
                  onClick={handleLogout}
                  className="flex-1 rounded-xl bg-red-500 py-3 text-sm font-bold text-white transition-colors hover:bg-red-600"
                >
                  로그아웃
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </>
  );
}

// 로그인 상태와 화면 분기를 관리하는 진입점
export default function App() {
  const [user, setUser] = useState<AppUser | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);

  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('access_token');
      if (!token) {
        setIsInitializing(false);
        return;
      }

      try {
        const res = await fetch('/api/auth/me', {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (res.ok) {
          const data = await res.json();
          setUser(data.user);
        } else {
          // 토큰이 만료되었거나 조작된 경우 강제 로그아웃
          localStorage.removeItem('access_token');
        }
      } catch (error) {
        console.error("Auto login failed:", error);
        localStorage.removeItem('access_token');
      } finally {
        setIsInitializing(false);
      }
    };

    checkAuth();
  }, []);

  if (isInitializing) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 font-sans">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-gray-200 border-t-blue-500" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 font-sans">
        <div className="flex flex-col items-center gap-8 p-10 bg-white rounded-3xl shadow-xl border border-gray-100">
          <div className="text-center space-y-2">
            <h1 className="text-5xl font-black text-transparent bg-clip-text bg-linear-to-r from-blue-500 via-yellow-400 to-purple-500">POSE!</h1>
            <p className="text-gray-500 font-medium">당신의 취향에서 시작되는 새로운 발견</p>
          </div>
          {/* 구글 로그인 버튼에 강제된 레이아웃 공간(div)을 확보하여 Flex 깨짐을 방지합니다. */}
          <div className="flex w-full justify-center min-h-[44px]">
            <GoogleLoginButton
              onSuccess={(userData) => setUser(userData)}
              onError={(msg) => alert(msg)}
            />
          </div>
        </div>
      </div>
    );
  }

  return <MainApp user={user} onLogout={() => setUser(null)} />;
}
