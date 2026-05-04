import { useState, useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { GoogleLoginButton } from './components/GoogleLoginButton';
import { Header } from './components/Header';
import { FeedTabContent } from './components/FeedTabContent';
import { ItemDetailDialog } from './components/ItemDetailDialog';
import { SearchTabContent } from './components/SearchTabContent';
import { ProfileTabContent } from './components/ProfileTabContent';
import { useItems } from './hooks/useItems';
import { useTaste } from './hooks/useTaste';
import type { SavedItem } from './types/item';
import type { AppUser } from './types/user';

function MainApp({ user, onLogout }: { user: AppUser; onLogout: () => void }) {
  const [selectedItem, setSelectedItem] = useState<SavedItem | null>(null);
  const [currentTab, setCurrentTab] = useState<'feed' | 'search' | 'profile'>('search');
  const [isLogoutModalOpen, setIsLogoutModalOpen] = useState(false);

  const { items, setItems, refreshItems } = useItems(user);
  const { taste, setTaste, refreshTaste } = useTaste(user);

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    setIsLogoutModalOpen(false);
    onLogout();
  };

  const handleLogoutClick = () => {
    setIsLogoutModalOpen(true);
  };

  return (
    <div className="min-h-screen bg-background font-sans">
      <Header
        user={user}
        onLogout={handleLogoutClick}
        currentTab={currentTab}
        onTabChange={setCurrentTab}
      />

      <main>
        <AnimatePresence mode="wait">
          {currentTab === 'search' && (
            <motion.div
              key="search"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="max-w-[1400px] mx-auto px-4 lg:px-8 py-8"
            >
              <SearchTabContent
                onItemsChange={setItems}
                refreshItems={refreshItems}
                refreshTaste={refreshTaste}
                user={user}
              />
            </motion.div>
          )}

          {currentTab === 'feed' && (
            <motion.div
              key="feed"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="max-w-[1400px] mx-auto px-4 lg:px-8 py-8"
            >
              <FeedTabContent
                items={items}
                onItemsChange={setItems}
                onSelectItem={setSelectedItem}
                refreshItems={refreshItems}
                refreshTaste={refreshTaste}
                user={user}
              />
            </motion.div>
          )}

          {currentTab === 'profile' && (
            <motion.div
              key="profile"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="max-w-[1400px] mx-auto px-4 lg:px-8 py-8"
            >
              <ProfileTabContent
                items={items}
                onGoToFeed={() => setCurrentTab('feed')}
                onSelectItem={setSelectedItem}
                onTasteChange={setTaste}
                taste={taste}
                user={user}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      <ItemDetailDialog
        item={selectedItem}
        onOpenChange={(open) => {
          if (!open) setSelectedItem(null);
        }}
      />

      {/* Logout Confirmation Modal */}
      <AnimatePresence>
        {isLogoutModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-sm rounded-2xl bg-background p-6 shadow-2xl"
            >
              <h3 className="mb-2 text-center text-lg font-bold text-foreground">
                로그아웃
              </h3>
              <p className="mb-6 text-center text-sm text-muted-foreground">
                정말 로그아웃 하시겠습니까?
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => setIsLogoutModalOpen(false)}
                  className="flex-1 rounded-lg bg-muted py-3 text-sm font-medium text-foreground transition-colors hover:bg-muted/80"
                >
                  취소
                </button>
                <button
                  onClick={handleLogout}
                  className="flex-1 rounded-lg bg-red-500 py-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-red-600"
                >
                  로그아웃
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

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
          localStorage.removeItem('access_token');
        }
      } catch (error) {
        console.error('Auto login failed:', error);
        localStorage.removeItem('access_token');
      } finally {
        setIsInitializing(false);
      }
    };

    checkAuth();
  }, []);

  const handleGuestLogin = async () => {
    try {
      const res = await fetch('/api/auth/guest', {
        method: 'POST',
      });

      if (!res.ok) {
        throw new Error('게스트 로그인에 실패했습니다.');
      }

      const data = await res.json();
      localStorage.setItem('access_token', data.access_token);
      setUser(data.user);
    } catch (error: any) {
      console.error('Guest Login Error:', error);
      alert(error.message || '게스트 로그인 중 오류가 발생했습니다.');
    }
  };

  if (isInitializing) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background font-sans">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-muted border-t-accent" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted font-sans">
        <div className="flex flex-col items-center gap-8 p-10 bg-background rounded-2xl shadow-xl border border-border">
          <div className="text-center space-y-2">
            <h1 className="text-4xl font-black text-foreground">POSE</h1>
            <p className="text-muted-foreground font-medium">
              당신의 취향에서 시작되는 새로운 발견
            </p>
          </div>
          <div className="flex w-full flex-col items-center gap-4">
            <div className="w-full flex justify-center min-h-[44px]">
              <GoogleLoginButton
                onSuccess={(userData) => setUser(userData)}
                onError={(msg) => alert(msg)}
              />
            </div>
            <button
              type="button"
              onClick={handleGuestLogin}
              className="w-full max-w-[320px] rounded-2xl border border-border bg-muted px-6 py-3 text-sm font-semibold text-foreground transition hover:bg-muted/80"
            >
              게스트 로그인
            </button>
          </div>
        </div>
      </div>
    );
  }

  return <MainApp user={user} onLogout={() => setUser(null)} />;
}
