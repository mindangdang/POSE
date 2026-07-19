import { Search } from 'lucide-react';
import { trackEvent } from '../../../analytics';

type FeedToolbarProps = {
  categories: string[];
  selectedCategory: string;
  searchQuery: string;
  onSelectCategory: (category: string) => void;
  onSearchQueryChange: (query: string) => void;
};

function getCategoryLabel(category: string) {
  if (category.toUpperCase() === 'ALL') return 'All';
  return category.charAt(0).toUpperCase() + category.slice(1).toLowerCase();
}

export function FeedToolbar({
  categories,
  selectedCategory,
  searchQuery,
  onSelectCategory,
  onSearchQueryChange,
}: FeedToolbarProps) {
  return (
    <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 sm:gap-4 mb-6 sm:mb-8 pb-4 sm:pb-6 border-b border-border">
      <nav className="flex items-center gap-1.5 sm:gap-2 overflow-x-auto pb-2 md:pb-0 category-nav">
        {categories.map((category) => {
          const label = getCategoryLabel(category);
          const isSelected = selectedCategory === category;

          return (
            <button
              key={category}
              onClick={() => onSelectCategory(category)}
              className={`flex items-center pb-2 px-1 text-xs sm:text-sm font-bold uppercase tracking-widest whitespace-nowrap transition-all border-b-2 ${
                isSelected
                  ? 'border-black text-black'
                  : 'border-transparent text-muted-foreground hover:text-black hover:border-black/20'
              }`}
            >
              {label}
            </button>
          );
        })}
      </nav>

      <div className="relative w-full md:w-64 lg:w-72 shrink-0">
        <Search className="absolute left-0 top-1/2 -translate-y-1/2 w-3.5 h-3.5 sm:w-4 sm:h-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="제목"
          value={searchQuery}
          onChange={(e) => onSearchQueryChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && searchQuery.trim()) {
              trackEvent('feed_search_submitted', { query: searchQuery });
            }
          }}
          className="w-full h-9 sm:h-10 pl-7 pr-2 bg-transparent border-b-2 border-black rounded-none text-xs sm:text-sm font-bold focus:outline-none placeholder:text-muted-foreground"
        />
      </div>
    </div>
  );
}
