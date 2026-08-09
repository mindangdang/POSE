import { Menu, X } from 'lucide-react';
import { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';

export type TabKey = 'feed' | 'search' | 'vote';

type HeaderProps = {
  onLogout: () => void;
  currentTab: TabKey;
  onTabChange: (tab: TabKey) => void;
  onAboutClick?: () => void;
};

export function Header({
  onLogout,
  onAboutClick,
}: HeaderProps) {
  const { user } = useAuth();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 bg-black border-b border-white/10">
      {/* Main Header */}
      <div className="flex items-center justify-between h-14 sm:h-16 px-4 lg:px-8 max-w-[1400px] mx-auto">
        {/* Logo */}
        <a href="/" className="flex items-center gap-2 shrink-0">
          <span className="text-2xl font-logo tracking-wide text-white transition-colors duration-1000">RoomShow</span>
        </a>

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
              <span className="text-xl font-logo text-white/40 mr-4 transition-all duration-1000">
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
