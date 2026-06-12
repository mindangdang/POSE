import { useState, useRef, useCallback } from 'react';
import type { SavedItem } from '../types/item';
import { searchService } from '../hooks/searchService';
import { SearchState, mergeUniqueResults } from '../hooks/searchUtils';
import { useAuth } from './useAuth';

type UseSearchProps = {
  searchMode: "digging" | "ai";
  selectedShopNames: Set<string>;
  shops: any[]; // Define a more specific type if possible
  pastedFile: File | null;
  startQuotaCountdown: (seconds: number) => void;
};

export function useSearch({
  searchMode,
  selectedShopNames,
  shops,
  pastedFile,
  startQuotaCountdown,
}: UseSearchProps) {
  const { user } = useAuth();
  const [searchResults, setSearchResults] = useState<SavedItem[]>([]);
  const [status, setStatus] = useState<SearchState>(SearchState.IDLE);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const pageRef = useRef(1);
  const [hasMore, setHasMore] = useState(true);
  const [generatedImage, setGeneratedImage] = useState<string | null>(null);

  // This is the internal fetch function, not exposed directly
  const _fetchResults = useCallback(async (query: string, page: number, isAppend: boolean) => {
    if (!user) return;

    if (isAppend) setIsLoadingMore(true);
    else setStatus(SearchState.LOADING);

    try {
      const shopNamesArray = Array.from(selectedShopNames);
      
      const res = searchMode === "digging" 
        ? await searchService.searchDigging(query, page, shopNamesArray, shops)
        : await searchService.searchLens(query, pastedFile);

      if (res.status === 429) {
        startQuotaCountdown(60);
        setStatus(SearchState.SUCCESS); // Or IDLE, depending on desired UI after quota hit
        setIsLoadingMore(false);
        return;
      }

      if (!res.ok) throw new Error((await res.json()).detail || "Search failed");
      const data = await res.json();

      if (searchMode === "digging" && data.success && !data.results) {
        // Background task initiated, waiting for WebSocket.
        // Do not change status here, keep it LOADING until WebSocket confirms success/error.
        return;
      }

      if (isAppend) {
        setSearchResults(prev => mergeUniqueResults(prev, data.results || []));
        if (!data.results || data.results.length === 0) setHasMore(false);
      } else {
        const results = data.results || [];
        setSearchResults(results);
        setHasMore(true); // Reset hasMore for new search
        setGeneratedImage(searchMode === "ai" ? data.generated_vibe_image_url : null);
        if (results.length === 0) setStatus(SearchState.EMPTY);
        else setStatus(SearchState.SUCCESS);
      }
      setIsLoadingMore(false);
    } catch (error: any) {
      alert(error.message);
      setStatus(SearchState.ERROR);
      setIsLoadingMore(false);
    }
  }, [user, searchMode, selectedShopNames, shops, pastedFile, startQuotaCountdown]);

  // Public search function
  const search = useCallback(async (query: string) => {
    pageRef.current = 1;
    setSearchResults([]);
    setGeneratedImage(null);
    setHasMore(true);
    await _fetchResults(query, 1, false);
  }, [_fetchResults]);

  // Public loadMore function
  const loadMore = useCallback(async (currentQuery: string) => {
    if (status === SearchState.LOADING || isLoadingMore || !hasMore) return;
    pageRef.current += 1;
    await _fetchResults(currentQuery, pageRef.current, true);
  }, [status, isLoadingMore, hasMore, _fetchResults]);

  // Callbacks for WebSocket updates
  const handleWebSocketSearchSuccess = useCallback((newResults: SavedItem[], isAppend: boolean) => {
    setSearchResults(prev => isAppend ? mergeUniqueResults(prev, newResults) : newResults);
    if (newResults.length === 0 && isAppend) setHasMore(false);
    setStatus(SearchState.SUCCESS);
    setIsLoadingMore(false);
  }, []);

  const handleWebSocketSearchFinished = useCallback(() => {
    if (status === SearchState.LOADING) setStatus(SearchState.SUCCESS); // Only change if still loading
    setIsLoadingMore(false);
  }, [status]);

  const handleWebSocketSearchError = useCallback((message: string) => {
    alert(message);
    setStatus(SearchState.ERROR);
    setIsLoadingMore(false);
  }, []);

  return {
    searchResults,
    status,
    isLoadingMore,
    hasMore,
    generatedImage,
    search,
    loadMore,
    handleWebSocketSearchSuccess,
    handleWebSocketSearchFinished,
    handleWebSocketSearchError,
  };
}
