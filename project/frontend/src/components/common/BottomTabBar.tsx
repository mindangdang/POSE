import { motion } from 'framer-motion';
import { Search, LayoutGrid, Vote } from 'lucide-react';
import type { TabKey } from './Header';

type BottomTabBarProps = {
  currentTab: TabKey;
  onTabChange: (tab: TabKey) => void;
};

const tabs: { id: TabKey; label: string; icon: typeof Search }[] = [
  { id: 'search', label: 'Window', icon: Search },
  { id: 'feed', label: 'Closet', icon: LayoutGrid },
  { id: 'vote', label: 'Vote', icon: Vote },
];

export function BottomTabBar({ currentTab, onTabChange }: BottomTabBarProps) {
  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-50 flex justify-center px-4 pb-[calc(env(safe-area-inset-bottom)+0.75rem)]"
    >
      <div className="glass-panel flex items-center gap-1 rounded-[1.75rem] p-1.5 shadow-2xl">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = currentTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => onTabChange(tab.id)}
              aria-current={isActive ? 'page' : undefined}
              aria-label={tab.label}
              className={`relative flex min-w-[4.5rem] flex-col items-center justify-center gap-1 rounded-[1.4rem] px-4 py-2.5 transition-colors duration-300 ${
                isActive
                  ? 'text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {isActive && (
                <motion.span
                  layoutId="bottom-tab-pill"
                  transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                  className="absolute inset-0 rounded-[1.4rem] bg-primary shadow-[0_6px_18px_rgba(13,148,136,0.35)]"
                />
              )}
              <Icon
                className="relative z-10 h-5 w-5"
                strokeWidth={isActive ? 2.4 : 2}
              />
              <span className="relative z-10 text-[10px] font-bold uppercase tracking-[0.12em]">
                {tab.label}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
