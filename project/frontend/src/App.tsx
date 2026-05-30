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

// Add Logo Font
const fontStyles = `
  @import url('https://api.fontshare.com/v2/css?f[]=comico@400&display=swap');
  .font-logo { font-family: 'comico', sans-serif; }
  body { font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif; font-weight: 500; background-color: #ffffff; }
`;

function MainApp({ user, onLogout }: { user: AppUser; onLogout: () => void }) {
  const [selectedItem, setSelectedItem] = useState<SavedItem | null>(null);
  const [currentTab, setCurrentTab] = useState<'feed' | 'search' | 'profile'>('search');
  const [searchSecondhandQuery, setSearchSecondhandQuery] = useState('');
  const [searchSecondhandTrigger, setSearchSecondhandTrigger] = useState(0);
  const [isLogoutModalOpen, setIsLogoutModalOpen] = useState(false);
  const [isAboutModalOpen, setIsAboutModalOpen] = useState(false);

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
        onAboutClick={() => setIsAboutModalOpen(true)}
      />

      <style>{fontStyles}</style>

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

      {/* About Modal */}
      <AnimatePresence>
        {isAboutModalOpen && (
          <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4 backdrop-blur-md">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 20 }}
              className="w-full max-w-lg rounded-3xl bg-background p-8 shadow-2xl border border-border"
            >
              <div className="flex justify-between items-center mb-6">
                <h3 className="text-2xl font-bold font-logo text-foreground">PoSe 사용 방법</h3>
                <button onClick={() => setIsAboutModalOpen(false)} className="p-2 hover:bg-muted rounded-full">
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              </div>
              <div className="space-y-6 text-foreground">
                <div className="flex gap-3 items-start">
                  <span className="text-lg leading-none mt-1.5">•</span>
                  <p className="text-sm leading-relaxed"><span className="font-bold">피드 수집:</span> 웹사이트 URL을 입력하여 나만의 스타일 아이템을 분석하고 보관하세요.</p>
                </div>
                <div className="flex gap-3 items-start">
                  <span className="text-lg leading-none mt-1.5">•</span>
                  <p className="text-sm leading-relaxed"><span className="font-bold">AI 스타일 검색:</span> "디스트로이드 데님", "미니멀한 무드" 등 텍스트로 원하는 아이템을 찾아보세요.</p>
                </div>
                <div className="flex gap-3 items-start">
                  <span className="text-lg leading-none mt-1.5">•</span>
                  <p className="text-sm leading-relaxed"><span className="font-bold">취향 DNA:</span> 수집된 아이템을 바탕으로 AI가 당신의 패션 철학을 분석해 드립니다.</p>
                </div>
              </div>
              
              <div className="mt-8 border-t border-foreground" />
              <button 
                onClick={() => setIsAboutModalOpen(false)} 
                className="w-full py-4 text-[10px] sm:text-xs font-bold uppercase tracking-[0.2em] text-foreground hover:opacity-70 transition-opacity bg-transparent border-none outline-none"
              >
                시작하기
              </button>
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
  const [isAboutModalOpen, setIsAboutModalOpen] = useState(false);

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
      <div className="min-h-screen bg-background font-sans relative">
        <style>{fontStyles}</style>

        {/* Header */}
        <header className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-4 sm:px-6 lg:px-12 h-14 sm:h-16 bg-background/80 backdrop-blur-sm">
          <span className="text-2xl font-logo tracking-tight text-foreground">PoSe</span>
          <nav className="flex items-center gap-6 text-xs sm:text-sm font-bold text-muted-foreground">
            <span onClick={() => setIsAboutModalOpen(true)} className="cursor-pointer font-logo text-xl hover:text-primary transition-colors uppercase tracking-widest">ABOUT</span>
          </nav>
        </header>

        {/* Hero Section */}
        <main className="relative min-h-screen flex flex-col">
          {/* Main Content */}
          <div className="flex-1 flex flex-col lg:flex-row">
            {/* Left - Typography */}
            <div className="flex-1 flex flex-col justify-center px-4 sm:px-6 lg:px-12 pt-20 sm:pt-24 lg:pt-0 pb-8 lg:pb-0">
              <div className="max-w-2xl">
                <h1 className="font-logo text-6xl sm:text-7xl md:text-8xl lg:text-9xl text-foreground tracking-tighter leading-[0.85]">
                  Digg yourself
                  <br />
                  with PoSe
                </h1>
                
                <div className="mt-8 sm:mt-10 max-w-xl border-t-4 border-foreground pt-6">
                  <p className="font-logo text-lg sm:text-xl md:text-2xl text-foreground leading-tight">
                    Life is beautiful! If music be the food of love, play on. Be not afraid of greatness: some are born great, some achieve greatness and some have greatness thrust upon them.
                  </p>
                </div>

                {/* Login Buttons */}
                <div className="mt-8 sm:mt-10 lg:mt-14 flex flex-col gap-2 items-start">
                  <GoogleLoginButton
                    onSuccess={(userData) => setUser(userData)}
                    onError={(msg) => alert(msg)}
                  />
                  <button
                    type="button"
                    onClick={handleGuestLogin}
                    className="text-[10px] sm:text-xs font-bold uppercase tracking-[0.2em] text-foreground hover:opacity-70 transition-opacity py-1 bg-transparent border-none outline-none"
                  >
                    Continue as Guest
                  </button>
                </div>
              </div>
            </div>

            {/* Right - Logo Photo Section */}
            <div className="flex-1 relative bg-muted/10 flex items-center justify-center overflow-hidden min-h-[40vh] lg:min-h-screen border-l border-border">
              <div className="absolute inset-0 flex items-center justify-center p-12">
                {/* Placeholder for the PoSe logo photo */}
                <div className="w-full max-w-md aspect-square rounded-3xl bg-background shadow-2xl flex items-center justify-center relative group">
                  <span className="font-logo text-[120px] sm:text-[160px] text-foreground/5 group-hover:text-primary/10 transition-colors duration-500">
                    PoSe
                  </span>
                  <div className="absolute inset-0 border-2 border-foreground/5 rounded-3xl m-4" />
                </div>
              </div>
            </div>
          </div>
        </main>

        {/* About Modal for Landing Page */}
        <AnimatePresence>
          {isAboutModalOpen && (
            <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4 backdrop-blur-md">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 20 }}
                className="w-full max-w-lg rounded-3xl bg-background p-8 shadow-2xl border border-border"
              >
                <div className="flex justify-between items-center mb-6">
                  <h3 className="text-2xl font-bold font-logo text-foreground">PoSe 사용 방법</h3>
                  <button onClick={() => setIsAboutModalOpen(false)} className="p-2 hover:bg-muted rounded-full">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                  </button>
                </div>
                <div className="space-y-6 text-foreground font-semibold">
                  <div className="flex gap-3 items-start">
                    <span className="text-lg leading-none mt-1.5">•</span>
                    <p className="text-sm leading-relaxed"><span className="font-bold">피드 수집:</span> 웹사이트 URL을 입력하여 나만의 스타일 아이템을 분석하고 보관하세요.</p>
                  </div>
                  <div className="flex gap-3 items-start">
                    <span className="text-lg leading-none mt-1.5">•</span>
                    <p className="text-sm leading-relaxed"><span className="font-bold">AI 스타일 검색:</span> "디스트로이드 데님", "미니멀한 무드" 등 텍스트로 원하는 아이템을 찾아보세요.</p>
                  </div>
                  <div className="flex gap-3 items-start">
                    <span className="text-lg leading-none mt-1.5">•</span>
                    <p className="text-sm leading-relaxed"><span className="font-bold">취향 DNA:</span> 수집된 아이템을 바탕으로 AI가 당신의 패션 철학을 분석해 드립니다.</p>
                  </div>
                </div>
                
                <div className="mt-8 border-t border-foreground" />
                <button 
                  onClick={() => setIsAboutModalOpen(false)} 
                  className="w-full py-4 text-[10px] sm:text-xs font-bold uppercase tracking-[0.2em] text-foreground hover:opacity-70 transition-opacity bg-transparent border-none outline-none"
                >
                  확인
                </button>
              </motion.div>
            </div>
          )}
        </AnimatePresence>
      </div>
    );
  }

  return <MainApp user={user} onLogout={() => setUser(null)} />;
}
