import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { GoogleLoginButton, Header, ItemDetailDialog } from './components/common';
import { FeedTabContent } from './components/tabs/Feed';
import { ProfileTabContent } from './components/tabs/Profile';
import { SearchTabContent } from './components/tabs/Search';
import { useItems } from './hooks/useItems';
import { useTaste } from './hooks/useTaste';
import { useAuth } from './hooks/useAuth';
import type { SavedItem } from './types/item';
import { setAnalyticsUser, trackEvent } from './analytics';

// Add Logo Font
const fontStyles = `
  @import url('https://api.fontshare.com/v2/css?f[]=new-title@400,700,800&display=swap');
  @font-face {
    font-family: 'Pretendard-Regular';
    src: url('https://fastly.jsdelivr.net/gh/Project-Noonnu/noonfonts_2107@1.1/Pretendard-Regular.woff') format('woff');
    font-weight: 400;
    font-style: normal;
  }
  .font-logo { font-family: 'New Title', 'Pretendard-Regular', ui-sans-serif, system-ui, sans-serif; font-weight: 700; letter-spacing: 0.02em; }
  .editorial-heading { font-family: 'New Title', 'Pretendard-Regular', ui-sans-serif, system-ui, sans-serif; font-weight: 800; letter-spacing: -0.01em; }
  body { font-family: 'Pretendard-Regular', ui-sans-serif, system-ui, -apple-system, sans-serif; font-weight: 500; background-color: #ffffff; color: #000000; }
  .leather-header {
    background-color: #080808;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E");
    background-blend-mode: overlay;
  }
`;

function MainApp() {
  const { logout, user } = useAuth();
  const [selectedItem, setSelectedItem] = useState<SavedItem | null>(null);
  const [currentTab, setCurrentTab] = useState<'feed' | 'search' | 'profile'>('search');
  const [searchSecondhandQuery, setSearchSecondhandQuery] = useState('');
  const [searchSecondhandTrigger, setSearchSecondhandTrigger] = useState(0);
  const [isLogoutModalOpen, setIsLogoutModalOpen] = useState(false);
  const [isAboutModalOpen, setIsAboutModalOpen] = useState(false);
  
  // Ambient Light State
  const [ambientColor, setAmbientColor] = useState('#000000');
  const [isAmbientActive, setIsAmbientActive] = useState(false);

  // 입력값이 없거나 기본값일 때 조명을 켜면 베이지색을 적용하는 로직
  const effectiveAmbientColor = isAmbientActive && (ambientColor.trim() === '' || ambientColor === '#000000') 
    ? '#F5F5DC' 
    : ambientColor;

  const { items, setItems, refreshItems } = useItems();
  const { taste, setTaste, refreshTaste } = useTaste();

  useEffect(() => {
    setAnalyticsUser(user?.id);
  }, [user?.id]);

  useEffect(() => {
    trackEvent('page_view', { tab: currentTab });
  }, [currentTab]);

  const handleLogout = () => {
    trackEvent('logout_confirmed');
    setIsLogoutModalOpen(false);
    logout();
  };

  const handleLogoutClick = () => {
    setIsLogoutModalOpen(true);
  };

  const handleSearchSecondhandFromFeed = (query: string) => {
    trackEvent('feed_search_secondhand_clicked', { query });
    setSearchSecondhandQuery(query);
    setSearchSecondhandTrigger((prev) => prev + 1);
    setCurrentTab('search');
  };

  return (
    <div className="min-h-screen bg-background font-sans">
      <Header
        onLogout={handleLogoutClick}
        currentTab={currentTab}
        onTabChange={setCurrentTab}
        onAboutClick={() => setIsAboutModalOpen(true)}
        ambientColor={effectiveAmbientColor}
        isAmbientActive={isAmbientActive}
      />

      {/* Ambient Light Background Layer */}
      <div className={`fixed inset-0 z-0 pointer-events-none transition-all duration-1000 ease-in-out ${isAmbientActive ? 'opacity-100' : 'opacity-0'}`}>
        {/* Main Light Source - Radial Bloom */}
        <div 
          className="absolute inset-0"
          style={{
            background: `radial-gradient(circle at 50% -10%, ${effectiveAmbientColor} 0%, transparent 70%)`,
            opacity: 0.2,
          }}
        />
        {/* Soft Ambient Wash - Linear */}
        <div 
          className="absolute inset-0"
          style={{
            background: `linear-gradient(to bottom, ${effectiveAmbientColor} 0%, transparent 100%)`,
            opacity: 0.1,
          }}
        />
        {/* Premium Noise Texture Layer */}
        <div 
          className="absolute inset-0 opacity-[0.04] mix-blend-overlay"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
          }}
        />
        {/* Soft Glow Shadow */}
        <div className="absolute inset-x-0 top-0 h-40" style={{ boxShadow: `0 -20px 100px 40px ${effectiveAmbientColor}22 inset` }} />
      </div>

      <style>{fontStyles}</style>

      <main className="relative z-10">
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
                ambientColor={ambientColor}
                onAmbientColorChange={setAmbientColor}
                isAmbientActive={isAmbientActive}
                onAmbientToggle={() => setIsAmbientActive(!isAmbientActive)}
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
            <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/80 p-4 backdrop-blur-md">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 20 }}
              className="w-full max-w-lg rounded-3xl bg-background p-8 shadow-2xl border border-border"
            >
              <div className="flex justify-between items-center mb-6">
                  <h3 className="text-2xl font-bold font-logo text-foreground">Welcome to RoomShow</h3>
                <button onClick={() => setIsAboutModalOpen(false)} className="p-2 hover:bg-muted rounded-full">
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              </div>
              <div className="space-y-6 text-foreground">
                  <p className="text-sm font-medium text-muted-foreground italic mb-4">"내 방은 나의 취향이 가장 온전히 머무는 우주입니다."</p>
                <div className="flex gap-3 items-start">
                    <span className="text-lg leading-none mt-1.5"></span>
                    <p className="text-sm leading-relaxed"><span className="font-bold">Window (창문):</span> 방 안에서 세상을 바라보며 새로운 영감을 찾습니다. AI 검색을 통해 당신이 꿈꾸는 스타일을 발견하세요.</p>
                </div>
                <div className="flex gap-3 items-start">
                    <span className="text-lg leading-none mt-1.5"></span>
                    <p className="text-sm leading-relaxed"><span className="font-bold">Closet (책장):</span> 당신이 발견한 소중한 조각들을 서재에 차곡차곡 쌓아둡니다. 나를 형용하는 것들로 채워진 당신만의 컬렉션입니다.</p>
                </div>
                <div className="flex gap-3 items-start">
                    <span className="text-lg leading-none mt-1.5"></span>
                    <p className="text-sm leading-relaxed"><span className="font-bold">Notebook (공책):</span> 수집된 취향을 분석하여 당신의 스타일 철학을 기록합니다. AI가 분석한 당신만의 스타일 DNA를 확인하세요.</p>
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
  const [isAboutModalOpen, setIsAboutModalOpen] = useState(false);
  const { user, isInitializing, login, loginAsGuest } = useAuth();

  const handleGuestLogin = async () => {
    try {
      await loginAsGuest();
    } catch (error: any) {
      console.error('Guest Login Error:', error);
      alert(error.message || '게스트 로그인 중 오류가 발생했습니다.');
    }
  };

  if (isInitializing) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background font-sans">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-muted border-t-foreground" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-white font-sans relative">
        <style>{fontStyles}</style>

        {/* Header */}
        <header className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-4 sm:px-6 lg:px-12 h-14 sm:h-16 bg-black border-b border-white/10">
          <span className="text-2xl font-logo tracking-wide text-white">RoomShow</span>
          <nav className="flex items-center gap-6 text-xs sm:text-sm font-bold text-white/60">
            <span onClick={() => setIsAboutModalOpen(true)} className="cursor-pointer font-logo text-xl hover:text-white transition-colors uppercase tracking-widest">ABOUT</span>
          </nav>
        </header>

        {/* Hero Section */}
        <main className="relative min-h-screen flex flex-col">
          {/* Main Content */}
          <div className="flex-1 flex flex-col lg:flex-row">
            {/* Left - Typography */}
            <div className="flex-1 flex flex-col justify-center px-4 sm:px-6 lg:px-12 pt-20 sm:pt-24 lg:pt-0 pb-8 lg:pb-0">
              <div className="max-w-2xl">
                <h1 className="font-logo text-7xl sm:text-8xl md:text-9xl lg:text-[10rem] text-foreground tracking-tight leading-[0.8] transition-all">
                <br />
                Digg yourself 
                <br />
                in RoomShow
                </h1>
                
                {/* Login Buttons */}
                <div className="mt-8 sm:mt-10 lg:mt-14 flex flex-col gap-2 items-start">
                  <GoogleLoginButton
                    onSuccess={login}
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
                    RoomShow
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
                  <h3 className="text-2xl font-bold font-logo text-foreground">About RoomShow</h3>
                  <button onClick={() => setIsAboutModalOpen(false)} className="p-2 hover:bg-muted rounded-full">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                  </button>
                </div>
                <div className="space-y-6 text-foreground font-semibold">
                  <p className="text-sm font-medium text-muted-foreground italic mb-4">"내 방은 나의 취향이 가장 온전히 머무는 우주입니다."</p>
                  <div className="flex gap-3 items-start">
                    <span className="text-lg leading-none mt-1.5">🪟</span>
                    <p className="text-sm leading-relaxed"><span className="font-bold">Window (창문):</span> 방 안에서 세상을 바라보며 새로운 영감을 찾습니다. AI 검색을 통해 당신이 꿈꾸는 스타일을 발견하세요.</p>
                  </div>
                  <div className="flex gap-3 items-start">
                    <span className="text-lg leading-none mt-1.5">📚</span>
                    <p className="text-sm leading-relaxed"><span className="font-bold">Closet (책장):</span> 당신이 발견한 소중한 조각들을 서재에 차곡차곡 쌓아둡니다. 나를 형용하는 것들로 채워진 당신만의 컬렉션입니다.</p>
                  </div>
                  <div className="flex gap-3 items-start">
                    <span className="text-lg leading-none mt-1.5">📓</span>
                    <p className="text-sm leading-relaxed"><span className="font-bold">Notebook (공책):</span> 수집된 취향을 분석하여 당신의 스타일 철학을 기록합니다. AI가 분석한 당신만의 스타일 DNA를 확인하세요.</p>
                  </div>
                </div>
                
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

  return <MainApp />;
}
