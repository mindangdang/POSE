import { motion, AnimatePresence } from 'framer-motion';
import { Loader2, Sparkles } from 'lucide-react';
import React from 'react';

import type { SavedItem } from '../types/item';
import { SearchState } from '../hooks/searchUtils';
import { SearchResultCard } from './SearchResultCard';

type SearchResultsProps = {
  displayActivity: boolean;
  searchMode: "digging" | "ai";
  searchResults: SavedItem[];
  status: SearchState;
  isLoadingMore: boolean;
  hasMore: boolean;
  generatedImage: string | null;
  quotaCountdown: number | null;
  loadMore: (query: string) => Promise<void>;
  searchQuery: string;
  bottomRef: (node: HTMLDivElement | null) => void;
  onSelectItem: (item: SavedItem) => void;
  onSaveItem: (e: React.MouseEvent, item: SavedItem) => void | Promise<void>;
  onSearchSecondhand: (title: string) => Promise<void>;
};

export function SearchResults({
  displayActivity,
  searchMode,
  searchResults,
  status,
  isLoadingMore,
  hasMore,
  generatedImage,
  quotaCountdown,
  loadMore,
  searchQuery,
  bottomRef,
  onSelectItem,
  onSaveItem,
  onSearchSecondhand,
}: SearchResultsProps) {
  if (!(displayActivity || searchResults.length > 0)) {
    return null;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 40 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      className="min-h-[60vh]"
    >
      <div className="w-full flex flex-col">
        <AnimatePresence>
          {status === SearchState.LOADING && searchResults.length === 0 && (
            <motion.div
              key="loading-indicator"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="flex flex-col items-center justify-center gap-4 py-8 overflow-hidden"
            >
              <div className="w-12 h-12 rounded-full border-2 border-muted border-t-foreground animate-spin" />
              <p style={{ whiteSpace: 'pre-line' }} className="text-sm font-bold text-muted-foreground text-center">
                {searchMode === "digging"
                  ? "Searching..."
                  : searchMode === "ai"
                  ? "AI가 유저 취향에 맞는 느좋탬들을 디깅하는 중..."
                  : "Analyzing..."}
              </p>
            </motion.div>
          )}

          {(status === SearchState.LOADING || isLoadingMore) && searchResults.length > 0 && (
            <motion.div
              key="loading-inline"
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="mb-4 rounded-2xl border border-border/60 bg-muted/70 px-4 py-3 text-sm font-semibold text-muted-foreground"
            >
              {searchMode === "digging"
                ? `계속 불러오는 중... (${searchResults.length}개 검색됨)`
                : "AI가 추가 결과를 준비하고 있어요..."}
            </motion.div>
          )}
        </AnimatePresence>

        {searchMode === "ai" && generatedImage && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex flex-col items-center bg-muted/50 p-8 rounded-2xl border border-border mb-8"
          >
            <span className="text-[10px] font-bold tracking-[0.2em] uppercase text-muted-foreground mb-4 flex items-center gap-2">
              <Sparkles className="w-4 h-4" /> Generated Vibe
            </span>
            <img
              src={generatedImage}
              alt="AI Generated Vibe"
              className="w-48 md:w-56 aspect-[3/4] object-cover rounded-xl shadow-lg"
            />
            <p className="text-xs text-muted-foreground mt-4 font-bold">Based on your style input</p>
          </motion.div>
        )}

        {/* Orderly Grid Layout: Left to Right, Top to Bottom */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          <AnimatePresence>
            {searchResults.map((item, index) => (
              <SearchResultCard
                key={item.url || item.id}
                delay={0.03 * (index % 20)}
                item={item}
                onClick={() => onSelectItem(item)}
                onSave={onSaveItem}
                onSearchSecondhand={onSearchSecondhand}
              />
            ))}
          </AnimatePresence>
        </div>

        {/* Loading Skeletons */}
        {status === SearchState.LOADING && searchResults.length === 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4 mt-4">
            {Array.from({ length: Math.max(5, 10 - searchResults.length) }).map((_, i) => (
              <div key={`skeleton-${i}`} className="relative">
                <div
                  className="w-full bg-muted rounded-2xl animate-pulse"
                  style={{
                    aspectRatio: '3/4'
                  }}
                />
                <div className="mt-3 space-y-2 px-1">
                  <div className="h-2 bg-muted rounded w-1/3 animate-pulse" />
                  <div className="h-3 bg-muted rounded w-3/4 animate-pulse" />
                </div>
              </div>
            ))}
          </div>
        )}

        <div ref={bottomRef} className="h-4" />

        {searchResults.length > 0 && hasMore && (
          <div className="flex justify-center py-10 w-full">
            <button
              onClick={() => loadMore(searchQuery)}
              disabled={status === SearchState.LOADING || isLoadingMore}
              className="h-12 px-8 bg-foreground text-background rounded-full text-sm font-semibold hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-2"
            >
              {(status === SearchState.LOADING || isLoadingMore) ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              <span>{(status === SearchState.LOADING || isLoadingMore) ? 'Loading...' : 'Load More'}</span>
            </button>
          </div>
        )}
      </div>
    </motion.div>
  );
}