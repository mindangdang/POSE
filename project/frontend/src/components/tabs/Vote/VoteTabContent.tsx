import { AnimatePresence, motion } from 'framer-motion';
import { ChevronLeft, ChevronRight, Heart, Plus, RotateCcw, ThumbsDown, ThumbsUp, X } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { apiJson } from '../../../lib/api';
import { trackEvent } from '../../../lib/analytics';
import { getDisplayImageUrl } from '../../../lib/imageUrl';
import type { SavedItem } from '../../../types/item';
import { useAuth } from '../../../hooks/useAuth';

type VoteItem = SavedItem;
type VoteDirection = 'like' | 'dislike';

export function VoteTabContent() {
  const { user, isInitializing, loginAsGuest } = useAuth();
  const [currentItem, setCurrentItem] = useState<VoteItem | null>(null);
  const [swipeDirection, setSwipeDirection] = useState<-1 | 1>(1);
  const [wishlistItems, setWishlistItems] = useState<VoteItem[]>([]);
  const [statusMessage, setStatusMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isVoting, setIsVoting] = useState(false);

  const loadRandomItem = useCallback(async () => {
    if (!user) {
      setCurrentItem(null);
      return;
    }

    setIsLoading(true);
    try {
      const item = await apiJson<VoteItem | null>('/api/vote/random');
      setCurrentItem(item);
      if (!item) {
        setStatusMessage('saved_posts에 투표할 아이템이 없습니다.');
      }
    } catch (error) {
      console.error('Failed to load vote item:', error);
      setCurrentItem(null);
      setStatusMessage('투표 아이템을 불러오지 못했습니다.');
    } finally {
      setIsLoading(false);
    }
  }, [user]);

  useEffect(() => {
    void loadRandomItem();
  }, [loadRandomItem]);

  const handleVote = async (direction: VoteDirection) => {
    if (!currentItem || !user || isVoting) return;

    setSwipeDirection(direction === 'like' ? 1 : -1);
    setIsVoting(true);

    try {
      await apiJson<VoteItem>(`/api/vote/${currentItem.item_id}/vote`, {
        method: 'POST',
        body: JSON.stringify({ direction }),
      });

      void trackEvent({
        action: direction === 'like' ? 'VOTE_PRETTY' : 'VOTE_UGLY',
        entityType: 'VOTING_ITEM',
        entityId: currentItem.item_id,
        metadata: { title: currentItem.title },
      });
      setStatusMessage(direction === 'like' ? '예뻐요로 투표했습니다.' : '별로에요로 투표했습니다.');
      await loadRandomItem();
    } catch (error) {
      console.error('Vote failed:', error);
      setStatusMessage('투표 처리 중 오류가 발생했습니다.');
    } finally {
      setIsVoting(false);
    }
  };

  const handleAddToWishlist = () => {
    if (!currentItem) return;

    setWishlistItems((prev) => {
      if (prev.some((item) => item.item_id === currentItem.item_id)) return prev;
      return [currentItem, ...prev];
    });
    void trackEvent({
      action: 'SAVE_WISHLIST',
      entityType: 'VOTING_ITEM',
      entityId: currentItem.item_id,
      metadata: { title: currentItem.title },
    });
    setStatusMessage('내 위시리스트에 추가했습니다.');
  };

  const handleRemoveFromWishlist = (item: VoteItem) => {
    setWishlistItems((prev) => prev.filter((wishlistItem) => wishlistItem.item_id !== item.item_id));
    void trackEvent({
      action: 'REMOVE_WISHLIST',
      entityType: 'WISHLIST_ITEM',
      entityId: item.item_id,
      metadata: { title: item.title },
    });
    setStatusMessage('위시리스트에서 삭제했습니다.');
  };

  const handleRestart = () => {
    setSwipeDirection(1);
    setStatusMessage('랜덤 카드 덱을 다시 불러옵니다.');
    void loadRandomItem();
  };

  if (!isInitializing && !user) {
    return (
      <div className="relative overflow-hidden rounded-[2rem] border border-black/10 bg-[#f7f1e6] px-4 py-6 shadow-[0_30px_120px_rgba(17,24,39,0.08)] sm:px-6 sm:py-8 lg:px-8">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(255,255,255,0.95),_transparent_42%),radial-gradient(circle_at_bottom_right,_rgba(240,232,218,0.85),_transparent_38%)]" />
        <div className="relative flex min-h-[560px] flex-col items-center justify-center rounded-[2rem] border border-dashed border-black/15 bg-white/70 px-6 text-center">
          <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-black text-white shadow-lg">
            <Heart className="h-7 w-7" />
          </div>
          <h2 className="text-2xl font-semibold text-foreground">로그인이 필요합니다</h2>
          <p className="mt-3 max-w-sm text-sm leading-7 text-muted-foreground">
            투표 탭은 현재 사용자의 saved_posts에서 랜덤 아이템을 불러옵니다. 게스트 로그인으로 바로 확인할 수 있습니다.
          </p>
          <button
            type="button"
            onClick={() => void loginAsGuest()}
            className="mt-6 inline-flex items-center gap-2 rounded-full bg-black px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-black/85"
          >
            게스트로 시작하기
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="relative overflow-hidden rounded-[2rem] border border-black/10 bg-[#f7f1e6] px-4 py-6 shadow-[0_30px_120px_rgba(17,24,39,0.08)] sm:px-6 sm:py-8 lg:px-8">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(255,255,255,0.95),_transparent_42%),radial-gradient(circle_at_bottom_right,_rgba(240,232,218,0.85),_transparent_38%)]" />

      <div className="relative grid gap-8 lg:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)] lg:items-start">
        <section className="space-y-5">
          <div className="max-w-2xl space-y-3">
            <p className="text-[10px] font-bold uppercase tracking-[0.35em] text-black/45">Vote</p>
            <h1 className="editorial-heading text-3xl leading-tight text-foreground sm:text-4xl lg:text-5xl">
              saved_posts에서
              <br />
              랜덤하게 꺼낸 아이템에 투표합니다.
            </h1>
            <p className="max-w-xl text-sm leading-7 text-muted-foreground sm:text-base">
              예뻐요 또는 별로에요를 누를 때마다 해당 아이템의 likes, dislikes 값이 1씩 증가합니다.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3 text-xs font-semibold uppercase tracking-[0.24em] text-foreground/70">
            <span className="rounded-full border border-black/10 bg-white/70 px-3 py-2">위시리스트 {wishlistItems.length}개</span>
            <span className="rounded-full border border-black/10 bg-white/70 px-3 py-2">랜덤 조회</span>
            <span className="rounded-full border border-black/10 bg-white/70 px-3 py-2">likes / dislikes 업데이트</span>
          </div>

          <div className="relative mx-auto w-full max-w-[520px]">
            <div className="absolute inset-x-6 bottom-5 h-14 rounded-full bg-black/10 blur-3xl" />

            <AnimatePresence mode="wait">
              {currentItem ? (
                <motion.div
                  key={currentItem.item_id}
                  initial={{ opacity: 0, y: 24, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{
                    opacity: 0,
                    x: swipeDirection * 240,
                    rotate: swipeDirection * 8,
                    scale: 0.96,
                  }}
                  transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
                  className="relative overflow-hidden rounded-[2rem] border border-black/10 bg-white shadow-[0_30px_80px_rgba(17,24,39,0.16)]"
                >
                  <div className="relative aspect-[4/5] overflow-hidden bg-neutral-100">
                    <img
                      src={getDisplayImageUrl(currentItem.image_url, null)}
                      alt={currentItem.title}
                      className="h-full w-full object-cover"
                      referrerPolicy="no-referrer"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/0 to-black/0" />

                    {wishlistItems.some((item) => item.item_id === currentItem.item_id) && (
                      <div className="absolute left-4 top-4 rounded-full bg-white/90 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.24em] text-black shadow-sm backdrop-blur-sm">
                        위시리스트에 있음
                      </div>
                    )}

                    <div className="absolute bottom-0 left-0 right-0 p-5 text-white sm:p-6">
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.3em] text-white/70">{currentItem.brand}</p>
                          <h2 className="text-2xl font-semibold leading-tight sm:text-3xl">{currentItem.title}</h2>
                        </div>
                        <div className="rounded-2xl border border-white/20 bg-white/10 px-3 py-2 text-right backdrop-blur-sm">
                          <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-white/70">Price</p>
                          <p className="text-sm font-semibold">{currentItem.price?.toLocaleString()}원</p>
                        </div>
                      </div>

                      <div className="mt-4 flex flex-wrap gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-white/80">
                        <span className="rounded-full bg-white/10 px-3 py-1 backdrop-blur-sm">{currentItem.category}</span>
                        <span className="rounded-full bg-white/10 px-3 py-1 backdrop-blur-sm">좋아요 {currentItem.likes ?? 0}</span>
                        <span className="rounded-full bg-white/10 px-3 py-1 backdrop-blur-sm">싫어요 {currentItem.dislikes ?? 0}</span>
                      </div>
                    </div>
                  </div>
                </motion.div>
              ) : (
                <motion.div
                  key="vote-empty"
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="flex min-h-[560px] flex-col items-center justify-center rounded-[2rem] border border-dashed border-black/15 bg-white/70 px-6 text-center"
                >
                  <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-black text-white shadow-lg">
                    <Heart className="h-7 w-7" />
                  </div>
                  <h2 className="text-2xl font-semibold text-foreground">{isLoading ? '카드를 불러오는 중입니다' : '표시할 카드가 없습니다'}</h2>
                  <p className="mt-3 max-w-sm text-sm leading-7 text-muted-foreground">
                    {isLoading
                      ? 'saved_posts에서 랜덤 아이템을 가져오고 있습니다.'
                      : '저장된 아이템이 없거나 현재 계정에 연결된 데이터가 없습니다.'}
                  </p>
                  <button
                    type="button"
                    onClick={handleRestart}
                    className="mt-6 inline-flex items-center gap-2 rounded-full bg-black px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-black/85"
                  >
                    <RotateCcw className="h-4 w-4" />
                    다시 불러오기
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <div className="mx-auto flex max-w-[520px] flex-wrap items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => void handleVote('dislike')}
              disabled={!currentItem || isVoting}
              className="inline-flex min-w-[132px] items-center justify-center gap-2 rounded-full border border-black/10 bg-white/80 px-4 py-3 text-sm font-semibold text-foreground shadow-sm transition-all hover:-translate-y-0.5 hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              <ThumbsDown className="h-4 w-4 text-rose-500" />
              별로에요
            </button>
            <button
              type="button"
              onClick={handleAddToWishlist}
              disabled={!currentItem}
              className="inline-flex min-w-[176px] items-center justify-center gap-2 rounded-full bg-black px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-black/10 transition-all hover:-translate-y-0.5 hover:bg-black/85 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Plus className="h-4 w-4" />
              내 위시 리스트에 추가하기
            </button>
            <button
              type="button"
              onClick={() => void handleVote('like')}
              disabled={!currentItem || isVoting}
              className="inline-flex min-w-[132px] items-center justify-center gap-2 rounded-full border border-black/10 bg-white/80 px-4 py-3 text-sm font-semibold text-foreground shadow-sm transition-all hover:-translate-y-0.5 hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              <ThumbsUp className="h-4 w-4 text-emerald-600" />
              예뻐요
            </button>
          </div>

          <div className="mx-auto flex max-w-[520px] items-center justify-center gap-2 text-xs text-muted-foreground">
            <ChevronLeft className="h-4 w-4" />
            버튼을 누를 때마다 다음 랜덤 아이템을 불러옵니다.
            <ChevronRight className="h-4 w-4" />
          </div>

          {statusMessage && (
            <p className="mx-auto max-w-[520px] rounded-full border border-black/10 bg-white/80 px-4 py-2 text-center text-sm text-foreground shadow-sm">
              {statusMessage}
            </p>
          )}
        </section>

        <aside className="space-y-4 lg:sticky lg:top-24">
          <div className="rounded-[1.75rem] border border-black/10 bg-white/85 p-5 shadow-[0_24px_60px_rgba(17,24,39,0.08)] backdrop-blur-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.3em] text-black/45">Wishlist</p>
                <h3 className="mt-1 text-xl font-semibold text-foreground">내 위시리스트</h3>
              </div>
              <div className="rounded-full bg-black px-3 py-1 text-xs font-bold uppercase tracking-[0.24em] text-white">
                {wishlistItems.length}
              </div>
            </div>

            <div className="mt-4 space-y-3">
              {wishlistItems.length > 0 ? (
                wishlistItems.map((item) => (
                  <article key={item.item_id} className="overflow-hidden rounded-2xl border border-black/10 bg-[#fbf8f2]">
                    <div className="flex gap-3 p-3">
                      <div className="h-20 w-16 shrink-0 overflow-hidden rounded-xl bg-neutral-200">
                        <img
                          src={getDisplayImageUrl(item.image_url, null)}
                          alt={item.title}
                          className="h-full w-full object-cover"
                          referrerPolicy="no-referrer"
                        />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="truncate text-[10px] font-bold uppercase tracking-[0.22em] text-black/45">{item.brand}</p>
                            <h4 className="truncate text-sm font-semibold text-foreground">{item.title}</h4>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleRemoveFromWishlist(item)}
                            className="mt-0.5 rounded-full p-1 text-black/60 transition-colors hover:bg-black/10 hover:text-black"
                            aria-label="위시리스트에서 삭제"
                          >
                            <X className="h-4 w-4" />
                          </button>
                        </div>

                        <div className="mt-3 flex flex-wrap gap-2 text-[11px] font-semibold">
                          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-1 text-emerald-700">
                            <ThumbsUp className="h-3 w-3" />
                            예뻐요 {item.likes ?? 0}
                          </span>
                          <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/10 px-2.5 py-1 text-rose-700">
                            <ThumbsDown className="h-3 w-3" />
                            별로에요 {item.dislikes ?? 0}
                          </span>
                        </div>
                      </div>
                    </div>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl border border-dashed border-black/10 bg-white px-4 py-8 text-center text-sm text-muted-foreground">
                  아직 위시리스트가 비어 있습니다.
                </div>
              )}
            </div>
          </div>

          <div className="rounded-[1.75rem] border border-black/10 bg-black px-5 py-4 text-white shadow-[0_24px_60px_rgba(17,24,39,0.16)]">
            <p className="text-[10px] font-bold uppercase tracking-[0.3em] text-white/55">Notes</p>
            <p className="mt-2 text-sm leading-6 text-white/80">
              랜덤 조회와 투표 카운터 갱신은 모두 backend/app/api/routes/content.py와 saved_posts 저장소를 통해 처리합니다.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}