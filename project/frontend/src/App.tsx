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
  const [searchSecondhandQuery, setSearchSecondhandQuery] = useState('');
  const [searchSecondhandTrigger, setSearchSecondhandTrigger] = useState(0);
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

  const handleSearchSecondhandFromFeed = (query: string) => {
    setSearchSecondhandQuery(query);
    setSearchSecondhandTrigger((prev) => prev + 1);
    setCurrentTab('search');
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
                searchSecondhandQuery={searchSecondhandQuery}
                searchSecondhandTrigger={searchSecondhandTrigger}
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
                onSearchSecondhand={handleSearchSecondhandFromFeed}
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
      <div className="min-h-screen bg-background font-sans">
        {/* Header */}
        <header className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-4 sm:px-6 lg:px-12 h-14 sm:h-16 bg-background/95 backdrop-blur-sm">
          <span className="text-lg sm:text-xl font-display font-bold tracking-tight text-foreground">PoSe</span>
          <nav className="hidden md:flex items-center gap-6 lg:gap-8 text-xs sm:text-sm font-medium text-muted-foreground">
            <span className="cursor-pointer hover:text-primary transition-colors">ABOUT</span>
            <span className="cursor-pointer hover:text-primary transition-colors">PROJECTS</span>
            <span className="cursor-pointer hover:text-primary transition-colors">SERVICES</span>
          </nav>
        </header>

        {/* Hero Section */}
        <main className="relative min-h-screen flex flex-col">
          {/* Main Content */}
          <div className="flex-1 flex flex-col lg:flex-row">
            {/* Left - Typography */}
            <div className="flex-1 flex flex-col justify-center px-4 sm:px-6 lg:px-12 pt-20 sm:pt-24 lg:pt-0 pb-8 lg:pb-0">
              <div className="max-w-2xl">
                <h1 className="editorial-heading text-4xl sm:text-5xl md:text-6xl lg:text-7xl xl:text-8xl text-foreground">
                  discover
                  <br />
                  <span className="text-primary">your</span>
                  <br />
                  style
                </h1>
                
                <div className="mt-6 sm:mt-8 lg:mt-12 space-y-3 sm:space-y-4 max-w-md">
                  <p className="text-sm sm:text-base text-muted-foreground leading-relaxed">
                    PoSe is your personal curation platform.
                    <br className="hidden sm:block" />
                    Discover, collect, and define your unique taste.
                  </p>
                  
                  <div className="flex flex-col gap-3 pt-2 sm:pt-4">
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span className="w-6 sm:w-8 h-px bg-primary"></span>
                      <span className="font-display">AI. SEARCH. DISCOVER.</span>
                    </div>
                  </div>
                </div>

                {/* Login Buttons */}
                <div className="mt-8 sm:mt-10 lg:mt-14 flex flex-col gap-3 sm:gap-4 max-w-xs">
                  <div className="w-full flex justify-start">
                    <GoogleLoginButton
                      onSuccess={(userData) => setUser(userData)}
                      onError={(msg) => alert(msg)}
                    />
                  </div>
                  <button
                    type="button"
                    onClick={handleGuestLogin}
                    className="w-full h-10 sm:h-11 rounded-full border border-border bg-background text-sm font-medium text-foreground transition hover:bg-muted hover:border-primary"
                  >
                    Continue as Guest
                  </button>
                </div>
              </div>
            </div>

            {/* Right - Image Grid */}
            <div className="flex-1 relative h-[50vh] sm:h-[60vh] lg:h-screen overflow-hidden">
              <div className="absolute inset-0 grid grid-cols-2 gap-2 p-3 sm:p-4 lg:p-6">
                <div className="space-y-2">
                  <div className="aspect-[3/4] bg-muted rounded-xl sm:rounded-2xl overflow-hidden">
                    <img 
                      src="https://images.unsplash.com/photo-1509631179647-0177331693ae?w=600&q=80" 
                      alt="Fashion inspiration"
                      className="w-full h-full object-cover hover:scale-105 transition-transform duration-700"
                    />
                  </div>
                  <div className="aspect-square bg-muted rounded-xl sm:rounded-2xl overflow-hidden">
                    <img 
                      src="https://images.unsplash.com/photo-1558171813-4c088753af8f?w=600&q=80" 
                      alt="Style inspiration"
                      className="w-full h-full object-cover hover:scale-105 transition-transform duration-700"
                    />
                  </div>
                </div>
                <div className="space-y-2 pt-6 sm:pt-8">
                  <div className="aspect-square bg-muted rounded-xl sm:rounded-2xl overflow-hidden">
                    <img 
                      src="https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=600&q=80" 
                      alt="Design inspiration"
                      className="w-full h-full object-cover hover:scale-105 transition-transform duration-700"
                    />
                  </div>
                  <div className="aspect-[3/4] bg-muted rounded-xl sm:rounded-2xl overflow-hidden">
                    <img 
                      src="https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&q=80" 
                      alt="Product inspiration"
                      className="w-full h-full object-cover hover:scale-105 transition-transform duration-700"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Bottom Features */}
          <div className="border-t border-border bg-background">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-12 py-6 sm:py-8 lg:py-12">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 sm:gap-8 lg:gap-12">
                <div className="space-y-2 sm:space-y-3">
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded-full bg-primary flex items-center justify-center">
                      <span className="text-xs font-bold text-primary-foreground">01</span>
                    </div>
                    <h3 className="text-sm font-display font-bold text-foreground">discover</h3>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    AI-powered search finds items that match your unique aesthetic and style preferences.
                  </p>
                </div>
                <div className="space-y-2 sm:space-y-3">
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded-full bg-primary flex items-center justify-center">
                      <span className="text-xs font-bold text-primary-foreground">02</span>
                    </div>
                    <h3 className="text-sm font-display font-bold text-foreground">collect</h3>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Save and organize your inspirations. Build a personal collection that reflects your taste.
                  </p>
                </div>
                <div className="space-y-2 sm:space-y-3">
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded-full bg-primary flex items-center justify-center">
                      <span className="text-xs font-bold text-primary-foreground">03</span>
                    </div>
                    <h3 className="text-sm font-display font-bold text-foreground">define</h3>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Get AI-generated insights about your style DNA. Understand and share your unique taste profile.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    );
  }

  return <MainApp user={user} onLogout={() => setUser(null)} />;
}
