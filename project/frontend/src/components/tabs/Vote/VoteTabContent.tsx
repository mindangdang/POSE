import { AnimatePresence, motion } from 'framer-motion';
import { ChevronLeft, ChevronRight, Heart, Plus, RotateCcw, ThumbsDown, ThumbsUp } from 'lucide-react';
import { useMemo, useState } from 'react';

import { getDisplayImageUrl } from '../../../lib/imageUrl';
import type { SavedItem } from '../../../types/item';

type VoteItem = SavedItem & {
  likeCount: number;
  dislikeCount: number;
};

const buildImage = (title: string) =>
  `https://placehold.co/900x1200/f3efe8/171717?text=${encodeURIComponent(title)}`;

const initialVoteItems: VoteItem[] = [
  {
    item_id: 901,
    title: 'Soft Line Trench Coat',
    price: 189000,
    brand: 'MUSE ROOM',
    category: 'OUTER',
    is_available: true,
    image_url: buildImage('Soft Line Trench Coat'),
    image_vector: null,
    shop: 'demo',
    source_url: 'https://example.com/items/901',
    created_at: '2026-07-01T00:00:00.000Z',
    likeCount: 24,
    dislikeCount: 3,
  },
  {
    item_id: 902,
    title: 'Cream Utility Jacket',
    price: 156000,
    brand: 'NEAR STUDIO',
    category: 'JACKET',
    is_available: true,
    image_url: buildImage('Cream Utility Jacket'),
    image_vector: null,
    shop: 'demo',
    source_url: 'https://example.com/items/902',
    created_at: '2026-07-02T00:00:00.000Z',
    likeCount: 18,
    dislikeCount: 5,
  },
  {
    item_id: 903,
    title: 'Wide Denim Slacks',
    price: 84000,
    brand: 'MONO FORM',
    category: 'BOTTOM',
    is_available: true,
    image_url: buildImage('Wide Denim Slacks'),
    image_vector: null,
    shop: 'demo',
    source_url: 'https://example.com/items/903',
    created_at: '2026-07-03T00:00:00.000Z',
    likeCount: 31,
    dislikeCount: 2,
  },
  {
    item_id: 904,
    title: 'Glossy Ballet Sneakers',
    price: 121000,
    brand: 'SOFT STEP',
    category: 'SHOES',
    is_available: true,
    image_url: buildImage('Glossy Ballet Sneakers'),
    image_vector: null,
    shop: 'demo',
    source_url: 'https://example.com/items/904',
    created_at: '2026-07-04T00:00:00.000Z',
    likeCount: 12,
    dislikeCount: 7,
  },
  {
    item_id: 905,
    title: 'Archive Shoulder Bag',
    price: 143000,
    brand: 'OBJECTIVE',
    category: 'BAG',
    is_available: true,
    image_url: buildImage('Archive Shoulder Bag'),
    image_vector: null,
    shop: 'demo',
    source_url: 'https://example.com/items/905',
    created_at: '2026-07-05T00:00:00.000Z',
    likeCount: 27,
    dislikeCount: 6,
  },
  {
    item_id: 906,
    title: 'Gloss Knit Cardigan',
    price: 98000,
    brand: 'SUNDAY ATELIER',
    category: 'TOP',
    is_available: true,
    image_url: buildImage('Gloss Knit Cardigan'),
    image_vector: null,
    shop: 'demo',
    source_url: 'https://example.com/items/906',
    created_at: '2026-07-06T00:00:00.000Z',
    likeCount: 20,
    dislikeCount: 4,
  },
];

type VoteDirection = -1 | 1;

export function VoteTabContent() {
  const [voteItems, setVoteItems] = useState<VoteItem[]>(initialVoteItems);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [swipeDirection, setSwipeDirection] = useState<VoteDirection>(1);
  const [wishlistIds, setWishlistIds] = useState<Set<number>>(() => new Set([902, 905]));
  const [statusMessage, setStatusMessage] = useState('');

  const currentItem = currentIndex < voteItems.length ? voteItems[currentIndex] : null;

  const wishlistItems = useMemo(
    () => voteItems.filter((item) => wishlistIds.has(item.item_id)),
    [voteItems, wishlistIds],
  );

  const handleVote = (direction: VoteDirection) => {
    if (!currentItem) return;

    setSwipeDirection(direction);
    setVoteItems((prev) =>
      prev.map((item) => {
        if (item.item_id !== currentItem.item_id) return item;

        return direction === 1
          ? { ...item, likeCount: item.likeCount + 1 }
          : { ...item, dislikeCount: item.dislikeCount + 1 };
      }),
    );
    setStatusMessage(direction === 1 ? '예뻐요로 투표했습니다.' : '별로에요로 투표했습니다.');
    setCurrentIndex((prev) => prev + 1);
  };

  const handleAddToWishlist = () => {
    if (!currentItem) return;

    setWishlistIds((prev) => {
      if (prev.has(currentItem.item_id)) return prev;
      const next = new Set(prev);
      next.add(currentItem.item_id);
      return next;
    });
    setStatusMessage('내 위시리스트에 추가했습니다.');
  };

  const handleRestart = () => {
    setCurrentIndex(0);
    setSwipeDirection(1);
    setStatusMessage('카드 덱을 처음부터 다시 봅니다.');
  };

  return (
    <div className="relative overflow-hidden rounded-[2rem] border border-black/10 bg-[#f7f1e6] px-4 py-6 shadow-[0_30px_120px_rgba(17,24,39,0.08)] sm:px-6 sm:py-8 lg:px-8">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(255,255,255,0.95),_transparent_42%),radial-gradient(circle_at_bottom_right,_rgba(240,232,218,0.85),_transparent_38%)]" />

      <div className="relative grid gap-8 lg:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)] lg:items-start">
        <section className="space-y-5">
          <div className="max-w-2xl space-y-3">
            <p className="text-[10px] font-bold uppercase tracking-[0.35em] text-black/45">Vote</p>
            <h1 className="editorial-heading text-3xl leading-tight text-foreground sm:text-4xl lg:text-5xl">
              위시리스트 카드를 넘기며,
              <br />
              취향에 투표하는 화면입니다.
            </h1>
            <p className="max-w-xl text-sm leading-7 text-muted-foreground sm:text-base">
              다른 유저의 카드 로딩은 아직 연결하지 않았습니다. 대신 현재 탭에서 스와이프, 예뻐요, 별로에요, 위시리스트 추가 흐름만 먼저 확인할 수 있습니다.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3 text-xs font-semibold uppercase tracking-[0.24em] text-foreground/70">
            <span className="rounded-full border border-black/10 bg-white/70 px-3 py-2">남은 카드 {Math.max(voteItems.length - currentIndex, 0)}개</span>
            <span className="rounded-full border border-black/10 bg-white/70 px-3 py-2">위시리스트 {wishlistItems.length}개</span>
            <span className="rounded-full border border-black/10 bg-white/70 px-3 py-2">데모 데이터</span>
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

                    {wishlistIds.has(currentItem.item_id) && (
                      <div className="absolute left-4 top-4 rounded-full bg-white/90 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.24em] text-black shadow-sm backdrop-blur-sm">
                        위시리스트에 있음
                      </div>
                    )}

                    <div className="absolute bottom-0 left-0 right-0 p-5 sm:p-6 text-white">
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
                        <span className="rounded-full bg-white/10 px-3 py-1 backdrop-blur-sm">{currentIndex + 1} / {voteItems.length}</span>
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
                  <h2 className="text-2xl font-semibold text-foreground">모든 카드를 확인했습니다</h2>
                  <p className="mt-3 max-w-sm text-sm leading-7 text-muted-foreground">
                    다시 보기를 누르면 카드 덱을 처음부터 다시 스와이프할 수 있습니다.
                  </p>
                  <button
                    type="button"
                    onClick={handleRestart}
                    className="mt-6 inline-flex items-center gap-2 rounded-full bg-black px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-black/85"
                  >
                    <RotateCcw className="h-4 w-4" />
                    다시 보기
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <div className="mx-auto flex max-w-[520px] flex-wrap items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => handleVote(-1)}
              disabled={!currentItem}
              className="inline-flex min-w-[132px] items-center justify-center gap-2 rounded-full border border-black/10 bg-white/80 px-4 py-3 text-sm font-semibold text-foreground shadow-sm transition-all hover:-translate-y-0.5 hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              <ThumbsDown className="h-4 w-4 text-rose-500" />
              별로에요
            </button>
            <button
              type="button"
              onClick={handleAddToWishlist}
              disabled={!currentItem || wishlistIds.has(currentItem.item_id)}
              className="inline-flex min-w-[176px] items-center justify-center gap-2 rounded-full bg-black px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-black/10 transition-all hover:-translate-y-0.5 hover:bg-black/85 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Plus className="h-4 w-4" />
              {currentItem && wishlistIds.has(currentItem.item_id) ? '위시리스트에 있음' : '내 위시 리스트에 추가하기'}
            </button>
            <button
              type="button"
              onClick={() => handleVote(1)}
              disabled={!currentItem}
              className="inline-flex min-w-[132px] items-center justify-center gap-2 rounded-full border border-black/10 bg-white/80 px-4 py-3 text-sm font-semibold text-foreground shadow-sm transition-all hover:-translate-y-0.5 hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              <ThumbsUp className="h-4 w-4 text-emerald-600" />
              예뻐요
            </button>
          </div>

          <div className="mx-auto flex max-w-[520px] items-center justify-center gap-2 text-xs text-muted-foreground">
            <ChevronLeft className="h-4 w-4" />
            버튼을 누를 때마다 카드가 다음 아이템으로 넘어갑니다.
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
                          <Heart className="mt-0.5 h-4 w-4 shrink-0 text-black" />
                        </div>

                        <div className="mt-3 flex flex-wrap gap-2 text-[11px] font-semibold">
                          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-1 text-emerald-700">
                            <ThumbsUp className="h-3 w-3" />
                            예뻐요 {item.likeCount}
                          </span>
                          <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/10 px-2.5 py-1 text-rose-700">
                            <ThumbsDown className="h-3 w-3" />
                            별로에요 {item.dislikeCount}
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
              이 화면은 프론트엔드 전용 데모입니다. 실제 다른 유저 카드 피드는 이후 API가 연결되면 이 구조를 그대로 확장하면 됩니다.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}