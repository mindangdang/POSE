import { Info, LogOut } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';

export type TabKey = 'feed' | 'search' | 'vote';

type HeaderProps = {
  onLogout: () => void;
  currentTab: TabKey;
  onTabChange: (tab: TabKey) => void;
  onAboutClick?: () => void;
};

export function Header({ onLogout, onAboutClick }: HeaderProps) {
  const { user } = useAuth();

  return (
    <header className="glass-strong sticky top-0 z-40 w-full border-b border-[var(--glass-hairline)]">
      <div className="mx-auto flex h-14 w-full max-w-[1400px] items-center justify-between px-4 sm:h-16 lg:px-8">
        {/* Logo */}
        <a href="/" className="flex items-center gap-2 shrink-0">
          <span className="font-logo text-xl text-foreground sm:text-2xl">
            RoomShow
          </span>
        </a>

        {/* Right actions */}
        <div className="flex items-center gap-1 sm:gap-2">
          {user && (
            <span className="mr-1 hidden text-sm font-semibold text-muted-foreground sm:inline">
              @{user.name || user.username || 'user'}
            </span>
          )}

          <button
            onClick={onAboutClick}
            aria-label="About RoomShow"
            className="flex h-9 w-9 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-foreground/5 hover:text-foreground"
          >
            <Info className="h-5 w-5" />
          </button>

          {user && (
            <button
              onClick={onLogout}
              aria-label="Logout"
              className="flex h-9 w-9 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-foreground/5 hover:text-foreground"
            >
              <LogOut className="h-5 w-5" />
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
