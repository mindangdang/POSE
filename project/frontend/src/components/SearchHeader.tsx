import { motion, AnimatePresence } from 'framer-motion';
import { Search, Loader2, Sparkles, BrainCircuit, Zap, X, Plus } from 'lucide-react';
import React, { useEffect, useState, useCallback } from 'react';

import type { AppUser } from '../types/user';
import { SearchState } from '../hooks/searchUtils';

type ModeOptionValue = "digging" | "ai";

type SearchHeaderProps = {
  user: AppUser | null;
  searchMode: ModeOptionValue;
  setSearchMode: React.Dispatch<React.SetStateAction<ModeOptionValue>>;
  searchQuery: string;
  setSearchQuery: React.Dispatch<React.SetStateAction<string>>;
  isDetailedSearch: boolean;
  setIsDetailedSearch: React.Dispatch<React.SetStateAction<boolean>>;
  detailedSearchQuery: { mood: string; color: string; fit: string; category: string; brand: string };
  setDetailedSearchQuery: React.Dispatch<React.SetStateAction<{ mood: string; color: string; fit: string; category: string; brand: string }>>;
  pastedFile: File | null;
  previewUrl: string | null;
  handlePaste: (event: React.ClipboardEvent<HTMLInputElement>) => void;
  clearImage: () => void;
  status: SearchState;
  quotaCountdown: number | null;
  generatedImage: string | null;
  displayActivity: boolean;
  handleSearch: (event: React.FormEvent<HTMLFormElement>) => Promise<void>;
  selectedShopNames: Set<string>;
  setSelectedShopNames: React.Dispatch<React.SetStateAction<Set<string>>>;
  randomSuggestions: string[]; // Add randomSuggestions to props
};

const SUGGESTION_POOL = [
  "빈티지 리바이스", "폴로 카라티", "아카이브 헬무트랭", "슬림핏 반팔", "유니폼",
  "아크테릭스 바람막이", "와이드 팬츠", "디스트로이드 데님", "빈티지 돌체 앤 가바나",
  "테크웨어", "웨스턴 셔츠", "그런지 팬츠", "올드머니 룩", "가죽 자켓", "포엣코어",
  "Y2K", "버버리 트렌치 코트", "헤비 스웨트셔츠", "팀버랜드 부츠", "펜던트 목걸이"
];


export function SearchHeader({
  user,
  searchMode,
  setSearchMode,
  searchQuery,
  setSearchQuery,
  isDetailedSearch,
  setIsDetailedSearch,
  detailedSearchQuery,
  setDetailedSearchQuery,
  pastedFile,
  previewUrl,
  handlePaste,
  clearImage,
  status,
  quotaCountdown,
  generatedImage,
  displayActivity,
  handleSearch,
  selectedShopNames,
  setSelectedShopNames,
  randomSuggestions, // Destructure randomSuggestions
}: SearchHeaderProps) {
  const [isModeMenuOpen, setIsModeMenuOpen] = useState(false);
  const [showDetailedSuggestions, setShowDetailedSuggestions] = useState(false);

  const modeOptions = [
    { value: "digging", label: "일반 검색", icon: Plus, activeClass: "text-black cursor-pointer hover:bg-gray-200", hoverClass: "hover:text-black hover:cursor-pointer" },
    { value: "ai", label: "이미지 검색 모드", icon: BrainCircuit, activeClass: "text-black cursor-pointer hover:bg-gray-200", hoverClass: "hover:text-black hover:cursor-pointer" },
  ] as const;
  const ActiveModeIcon = modeOptions.find(opt => opt.value === searchMode)?.icon ?? Plus;

  const detailFields = [
    { key: "mood", placeholder: "무드", suggestions: ["빈티지", "미니멀", "스트릿"] },
    { key: "color", placeholder: "색상", suggestions: ["블랙", "연청", "아이보리"] },
    { key: "fit", placeholder: "핏", suggestions: ["오버핏", "크롭", "와이드"] },
    { key: "category", placeholder: "카테고리", suggestions: ["티셔츠", "자켓", "팬츠"] },
    { key: "brand", placeholder: "브랜드", suggestions: ["리바이스", "엘무드", "노이어"] },
  ] as const;

  useEffect(() => {
    if (searchMode !== "digging" || !isDetailedSearch || displayActivity) {
      setShowDetailedSuggestions(false);
      return;
    }
    const timer = window.setTimeout(() => setShowDetailedSuggestions(true), 100);
    return () => window.clearTimeout(timer);
  }, [displayActivity, isDetailedSearch, searchMode]);

  const applySelectedMode = useCallback((mode: ModeOptionValue) => {
    setSearchMode(mode);
    if (mode !== "digging") {
      setIsDetailedSearch(false);
    }
  }, [setSearchMode, setIsDetailedSearch]);

  const handleSelectMode = useCallback((mode: ModeOptionValue) => {
    setIsModeMenuOpen(false);
    if (showDetailedSuggestions) {
      setShowDetailedSuggestions(false);
      window.setTimeout(() => applySelectedMode(mode), 110);
      return;
    }
    applySelectedMode(mode);
  }, [applySelectedMode, showDetailedSuggestions]);

  return (
    <div className={`${displayActivity ? 'sticky top-0 z-40 bg-background/95 backdrop-blur-xl -mx-4 px-4 py-6 border-b border-border/50 shadow-sm mb-12' : 'relative w-full mb-0'}`}>
      <motion.div
        className="flex w-full flex-col items-center gap-8"
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        <AnimatePresence>
          {!displayActivity && (
            <motion.div
              key="search-brand"
              initial={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20, height: 0, marginBottom: 0 }}
              transition={{ duration: 0.3 }}
              className="flex w-full max-w-3xl flex-col items-start gap-4 sm:gap-6 overflow-hidden"
            >
              <h1 className="font-bold text-2xl sm:text-3xl md:text-4xl lg:text-5xl text-foreground text-left leading-tight tracking-tight">
                네 자신을 찾는 일을 목표로
                <br />
                하는 인생은 재밌어.
                <br />
                그렇지 않아?
              </h1>
            </motion.div>
          )}
        </AnimatePresence>

        <form onSubmit={handleSearch} className="relative group max-w-3xl w-full flex flex-col gap-4 z-50">
          <motion.div
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            className="relative w-full"
          >
            <div className="absolute left-3 top-1/2 z-30 -translate-y-1/2 flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => setIsModeMenuOpen((open) => !open)}
                className={`flex h-10 w-10 items-center justify-center rounded-full transition-colors ${modeOptions.find(opt => opt.value === searchMode)?.activeClass}`}
              >
                <ActiveModeIcon className="h-5 w-5" />
              </button>

              {searchMode === "digging" && !displayActivity && !previewUrl && (
                <button
                  type="button"
                  onClick={() => setIsDetailedSearch(!isDetailedSearch)}
                  className={`flex h-10 w-10 items-center justify-center rounded-full transition-all ${isDetailedSearch ? "bg-black text-white shadow-md" : "text-muted-foreground hover:bg-muted"}`}
                >
                  <Zap className={`h-4 w-4 ${isDetailedSearch ? "fill-current" : ""}`} />
                </button>
              )}

              {previewUrl && (
                <motion.div initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} className="flex items-center gap-1 bg-black/5 p-1 rounded-lg border border-border">
                  <img src={previewUrl} className="w-8 h-8 object-cover rounded-md" />
                  <button
                    type="button"
                    onClick={() => {
                      clearImage();
                      setSearchQuery("");
                    }}
                    className="p-0.5 hover:bg-black/10 rounded-full"
                  >
                    <X className="w-3 h-3 text-muted-foreground" />
                  </button>
                </motion.div>
              )}

              <AnimatePresence>
                {isModeMenuOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: -8, scale: 0.98 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -8, scale: 0.98 }}
                    className="absolute left-0 top-12 flex w-44 flex-col gap-1 rounded-2xl bg-background p-1.5 shadow-2xl border border-border z-[100]"
                  >
                    {modeOptions.map((opt) => (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => handleSelectMode(opt.value)}
                        className={`flex h-11 items-center gap-3 rounded-xl px-3 text-left text-sm font-bold transition-all hover:bg-muted ${searchMode === opt.value ? opt.activeClass : `text-muted-foreground ${opt.hoverClass}`}`}
                      >
                        <opt.icon className="h-4 w-4" />
                        <span className="whitespace-nowrap">{opt.label}</span>
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <AnimatePresence mode="wait">
              {searchMode === "digging" && isDetailedSearch && !displayActivity ? (
                <motion.div
                  key="detail-search-panel"
                  layout
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                  className="overflow-hidden flex w-full flex-col justify-center border-b-2 border-foreground bg-transparent pl-28 pr-16"
                >
                  {detailFields.map(({ key, placeholder, suggestions }, index) => (
                    <div key={key} className={`flex min-h-14 items-center gap-3 ${index < detailFields.length - 1 ? "border-b border-border" : ""}`}>
                      <input
                        type="text"
                        placeholder={placeholder}
                        value={detailedSearchQuery[key]}
                        onChange={(e) => setDetailedSearchQuery((prev) => ({ ...prev, [key]: e.target.value }))}
                        className="h-full min-w-0 flex-1 bg-transparent text-sm font-bold placeholder:text-muted-foreground focus:outline-none"
                      />
                      <div className="flex max-w-[14rem] gap-1.5 flex-wrap justify-end">
                        {suggestions.map((suggestion) => (
                          <button
                            key={suggestion}
                            type="button"
                            onClick={() => setDetailedSearchQuery(prev => ({ ...prev, [key]: prev[key] === suggestion ? "" : suggestion }))}
                            className={`shrink-0 rounded-full border px-3 py-1.5 text-xs font-bold transition-colors ${detailedSearchQuery[key] === suggestion ? "border-black bg-black text-white" : "border-border text-muted-foreground hover:border-black hover:text-black"}`}
                          >
                            {suggestion}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </motion.div>
              ) : (
                <motion.div
                  key="search-input-panel"
                  layout
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                  className="overflow-hidden relative w-full"
                >
                  <div className="relative h-14 w-full border-b-2 border-foreground">
                    <input
                      type="text"
                      placeholder={searchMode === "digging" ? "머릿속에 생각나는 그대로 검색해보세요." : "원하는 이미지를 붙여넣거나 생성하고 싶은 의류 이미지를 묘사해보세요."}
                      value={previewUrl ? "" : searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      onPaste={handlePaste}
                      className={`h-full w-full bg-transparent ${previewUrl ? 'pl-32' : 'pl-28'} pr-24 text-base font-bold placeholder:text-muted-foreground outline-none`}
                    />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <button
              disabled={status === SearchState.LOADING || quotaCountdown !== null}
              className="absolute right-2 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full text-foreground hover:bg-muted disabled:opacity-50"
            >
              {status === SearchState.LOADING ? <Loader2 className="w-5 h-5 animate-spin" /> : quotaCountdown !== null ? <span className="text-xs font-bold">{quotaCountdown}s</span> : <Search className="w-5 h-5" />}
            </button>
          </motion.div>

          {/* Selected Shops Badges Inside Form for Layout Stability */}
          <div className={`mt-2 ${selectedShopNames.size > 0 ? 'min-h-[2.25rem]' : 'min-h-0'}`}>
            <AnimatePresence>
              {selectedShopNames.size > 0 && (
                <motion.div initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} className="flex flex-wrap gap-2">
                  {Array.from(selectedShopNames).map((name) => (
                    <div key={name} className="flex items-center gap-1.5 px-3 py-1 bg-black text-white rounded-full text-[10px] font-bold uppercase">
                      {name}
                      <button type="button" onClick={() => {
                        setSelectedShopNames(prev => {
                          const next = new Set(prev);
                          next.delete(name);
                          return next;
                        });
                      }} className="hover:text-red-400">
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                  <button type="button" onClick={() => setSelectedShopNames(new Set())} className="text-[10px] font-bold text-muted-foreground hover:text-black uppercase underline">Clear All</button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </form>

        {/* 추천 검색어 영역 */}
        {!displayActivity && !isDetailedSearch && randomSuggestions.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            className="w-full max-w-3xl mx-auto flex flex-wrap gap-x-4 gap-y-2 px-1 mb-2"
          >
            {randomSuggestions.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => setSearchQuery(suggestion)} // Directly set search query
                className="text-xs sm:text-sm text-muted-foreground hover:text-black border-b border-transparent hover:border-black transition-all pb-0.5"
              >
                {suggestion}
              </button>
            ))}
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}