import { ChevronDown, Menu, X } from 'lucide-react';
import { useState } from 'react';
import type { AppUser } from '../types/user';

type HeaderProps = {
  user: AppUser | null;
  onLogout: () => void;
  currentTab: string;
  onTabChange: (tab: 'feed' | 'search' | 'profile') => void;
};

const categories = [
  { id: 'search', label: 'search', hasDropdown: false },
  { id: 'feed', label: 'feed', hasDropdown: false },
  { id: 'profile', label: 'tasting', hasDropdown: false },
];

export function Header({
  user,
  onLogout,
  currentTab,
  onTabChange,
}: HeaderProps) {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 bg-background/95 backdrop-blur-sm border-b border-border">
      {/* Main Header */}
      <div className="flex items-center justify-between h-14 sm:h-16 px-4 lg:px-8 max-w-[1400px] mx-auto">
        {/* Logo */}
        <a href="/" className="flex items-center gap-2 shrink-0">
          <span className="text-lg sm:text-xl font-display font-bold tracking-tight text-foreground">PoSe</span>
        </a>

        {/* Center Navigation - Desktop */}
        <nav className="hidden md:flex items-center gap-6 lg:gap-8">
          {categories.map((category) => (
            <button
              key={category.id}
              onClick={() => onTabChange(category.id as 'feed' | 'search' | 'profile')}
              className={`relative text-xs sm:text-sm font-display font-medium tracking-wide transition-colors ${
                currentTab === category.id
                  ? 'text-primary'
                  : 'text-muted-foreground hover:text-primary'
              }`}
            >
              {category.label}
              {currentTab === category.id && (
                <span className="absolute -bottom-[19px] sm:-bottom-[21px] left-0 right-0 h-0.5 bg-primary rounded-full" />
              )}
            </button>
          ))}
        </nav>

        {/* Right Navigation - Desktop */}
        <nav className="hidden md:flex items-center gap-4 lg:gap-6">
          {user ? (
            <>
              <span className="text-xs font-medium text-muted-foreground">
                @{user.name || user.username || 'user'}
              </span>
              <button
                onClick={onLogout}
                className="text-xs font-medium text-muted-foreground hover:text-primary transition-colors"
              >
                Logout
              </button>
            </>
          ) : (
            <>
              <button className="text-xs font-medium text-muted-foreground hover:text-primary transition-colors">
                Sign Up
              </button>
              <button className="text-xs font-medium text-muted-foreground hover:text-primary transition-colors">
                Login
              </button>
            </>
          )}
        </nav>

        {/* Mobile Menu Button */}
        <button
          onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          className="md:hidden p-2 text-foreground"
          aria-label="Toggle menu"
        >
          {isMobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile Menu */}
      {isMobileMenuOpen && (
        <div className="md:hidden absolute top-16 left-0 right-0 bg-background border-b border-border shadow-lg">
          {/* Mobile Categories */}
          <nav className="py-2">
            {categories.map((category) => (
              <button
                key={category.id}
                onClick={() => {
                  onTabChange(category.id as 'feed' | 'search' | 'profile');
                  setIsMobileMenuOpen(false);
                }}
                className={`w-full flex items-center justify-between px-4 py-3 text-sm font-medium ${
                  currentTab === category.id
                    ? 'text-foreground bg-muted'
                    : 'text-muted-foreground'
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
