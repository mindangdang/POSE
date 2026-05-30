import { ChevronDown, Menu, X } from 'lucide-react';
import { useState } from 'react';
import type { AppUser } from '../types/user';

type HeaderProps = {
  user: AppUser | null;
  onLogout: () => void;
  currentTab: string;
  onTabChange: (tab: 'feed' | 'search' | 'profile') => void;
  onAboutClick?: () => void;
  ambientColor?: string;
  isAmbientActive?: boolean;
};

const categories = [
  { id: 'search', label: 'Window', hasDropdown: false },
  { id: 'feed', label: 'Bookcase', hasDropdown: false },
  { id: 'profile', label: 'Notebook', hasDropdown: false },
];

export function Header({
  user,
  onLogout,
  currentTab,
  onTabChange,
  onAboutClick,
  ambientColor,
  isAmbientActive,
}: HeaderProps) {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // 조명 모드 시 텍스트에 적용할 미세한 색상 변조 스타일
  const ambientTextStyle = isAmbientActive ? { color: ambientColor, filter: 'brightness(1.5) saturate(1.2)' } : {};

  return (
    <header className="sticky top-0 z-50 bg-black border-b border-white/10">
      {/* Main Header */}
      <div className="flex items-center justify-between h-14 sm:h-16 px-4 lg:px-8 max-w-[1400px] mx-auto">
        {/* Logo */}
        <a href="/" className="flex items-center gap-2 shrink-0">
          <span className="text-2xl font-logo tracking-tight text-white transition-colors duration-1000" style={ambientTextStyle}>Demian's room</span>
        </a>

        {/* Center Navigation - Desktop */}
        <nav className="hidden md:flex items-center gap-6 lg:gap-8">
          {categories.map((category) => (
            <button
              key={category.id}
              onClick={() => onTabChange(category.id as 'feed' | 'search' | 'profile')}
              className={`relative text-lg font-logo tracking-widest uppercase transition-all duration-1000 ${
                currentTab === category.id
                  ? 'text-white'
                  : 'text-white/60 hover:text-white'
              }`}
              style={currentTab === category.id ? ambientTextStyle : {}}
            >
              {category.label}
              {currentTab === category.id && (
                <span 
                  className="absolute -bottom-[19px] sm:-bottom-[21px] left-0 right-0 h-0.5 bg-white rounded-full transition-all duration-1000" 
                  style={isAmbientActive ? { backgroundColor: ambientColor } : {}}
                />
              )}
            </button>
          ))}
        </nav>

        {/* Right Navigation - Desktop */}
        <nav className="hidden md:flex items-center gap-4 lg:gap-6">
          {user ? (
            <>
              <button
                onClick={onAboutClick}
                className="text-xl font-logo text-white/60 hover:text-white transition-all duration-1000 tracking-widest uppercase mr-4"
              >
                ABOUT
              </button>
              <span className="text-xl font-logo text-white/40 mr-4 transition-all duration-1000" style={isAmbientActive ? { color: ambientColor, opacity: 0.6 } : {}}>
                @{user.name || user.username || 'user'}
              </span>
              <button
                onClick={onLogout}
                className="text-xl font-logo text-white/60 hover:text-white transition-all duration-1000 uppercase tracking-widest"
              >
                Logout
              </button>
            </>
          ) : (
            <>
              <button onClick={onAboutClick} className="text-xl font-logo text-white/60 hover:text-white transition-colors tracking-widest uppercase">ABOUT</button>
            </>
          )}
        </nav>

        {/* Mobile Menu Button */}
        <button
          onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          className="md:hidden p-2 text-white"
          aria-label="Toggle menu"
        >
          {isMobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile Menu */}
      {isMobileMenuOpen && (
        <div className="md:hidden absolute top-16 left-0 right-0 bg-black border-b border-white/10 shadow-lg">
          {/* Mobile Categories */}
          <nav className="py-2">
            {categories.map((category) => (
              <button
                key={category.id}
                onClick={() => {
                  onTabChange(category.id as 'feed' | 'search' | 'profile');
                  setIsMobileMenuOpen(false);
                }}
                className={`w-full flex items-center justify-between px-4 py-3 font-logo text-lg uppercase tracking-widest ${
                  currentTab === category.id
                    ? 'text-white bg-white/10'
                    : 'text-white/60'
                }`}
              >
                {category.label}
                {category.hasDropdown && <ChevronDown className="w-4 h-4" />}
              </button>
            ))}
          </nav>

          {/* Mobile User Actions */}
          <div className="border-t border-border p-4 space-y-2">
            {user ? (
              <>
                <div className="text-sm font-medium text-foreground py-2">
                  @{user.name || user.username || 'user'}
                </div>
                <button
                  onClick={() => {
                    onLogout();
                    setIsMobileMenuOpen(false);
                  }}
                  className="w-full text-left text-sm font-medium text-muted-foreground py-2"
                >
                  Logout
                </button>
              </>
            ) : (
              <>
                <button className="w-full text-left text-sm font-medium text-muted-foreground py-2">
                  Sign Up
                </button>
                <button className="w-full text-left text-sm font-medium text-muted-foreground py-2">
                  Login
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
