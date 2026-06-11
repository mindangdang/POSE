import { useEffect, useRef, useCallback } from 'react';

type UseInfiniteScrollProps = {
  enabled: boolean;
  loading: boolean;
  onLoadMore: () => void;
};

export function useInfiniteScroll({ enabled, loading, onLoadMore }: UseInfiniteScrollProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  const observerCallback = useCallback(
    (entries: IntersectionObserverEntry[]) => {
      if (entries[0].isIntersecting && enabled && !loading) {
        onLoadMore();
      }
    },
    [enabled, loading, onLoadMore]
  );

  useEffect(() => {
    const currentBottomRef = bottomRef.current;
    if (!currentBottomRef) return;

    const observer = new IntersectionObserver(observerCallback, { threshold: 0.1, rootMargin: '400px' });
    observer.observe(currentBottomRef);
    return () => observer.disconnect();
  }, [observerCallback]);

  return bottomRef;
}