import { AnimatePresence, motion } from 'framer-motion';
import { Bookmark, Heart, MessageCircle, Plus, RotateCcw, Send, Sparkles, ThumbsDown, ThumbsUp, X } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { apiJson } from '../../../lib/api';
import { trackEvent } from '../../../lib/analytics';
import { getDisplayImageUrl } from '../../../lib/imageUrl';
import type { SavedItem } from '../../../types/item';
import { useAuth } from '../../../hooks/useAuth';

type VoteItem = SavedItem;
type VoteDirection = 'like' | 'dislike';
type VotePost =
  | { type: 'vote'; id: string; item: VoteItem; topic: string; owner: string; mood: string }
  | { type: 'brand'; id: string; label: string; title: string; description: string; imageUrl: string; cta: string; tags: string[] };

const questionPrompts = [
  '이 가격이면 살만한가여?',
  '디자인이 너무 여성스러운가요?',
  '출근룩으로 입어도 과하지 않을까요?',
  '오래 입을 수 있는 클래식템 같나요?',
  '지금 위시로 저장해둘 만한 실루엣인가요?',
];

const brandPosts: VotePost[] = [
  {
    type: 'brand',
    id: 'brand-lookbook-01',
    label: 'POSE LOOKBOOK',
    title: 'Liquid tailoring for late summer',
    description: '차가운 실버, 투명한 레이어, 은은한 새틴으로 만드는 8월의 데일리 룩북.',
    imageUrl: 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=1200&q=80',
    cta: '룩북 저장하기',
    tags: ['Lookbook', 'Tailoring', 'Silver mood'],
  },
  {
    type: 'brand',
    id: 'brand-cardnews-01',
    label: 'STYLE CARD',
    title: '위시 구매 전 체크할 3가지',
    description: '핏의 반복 착용 가능성, 가진 옷과의 컬러 연결성, 중고 리세일 가능성을 빠르게 확인해보세요.',
    imageUrl: 'https://images.unsplash.com/photo-1496747611176-843222e1e57c?auto=format&fit=crop&w=1200&q=80',
    cta: '카드뉴스 읽기',
    tags: ['Guide', 'Wishlist', 'Shopping tip'],
  },
];

const formatPrice = (price: number | null) => (price ? `${price.toLocaleString()}원` : '가격 미정');

export function VoteTabContent() {
  const { user, isInitializing, loginAsGuest } = useAuth();
  const [feedItems, setFeedItems] = useState<VoteItem[]>([]);
  const [wishlistItems, setWishlistItems] = useState<VoteItem[]>([]);
  const [statusMessage, setStatusMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [votingItemId, setVotingItemId] = useState<number | null>(null);

  const loadVoteFeed = useCallback(async () => {
    if (!user) {
      setFeedItems([]);
      return;
    }

    setIsLoading(true);
    try {
      const items = await apiJson<VoteItem[]>('/api/items');
      setFeedItems(items.filter((item) => item.title !== 'PROCESSING'));
      if (!items.length) setStatusMessage('아직 피드에 올릴 위시 아이템이 없습니다.');
    } catch (error) {
      console.error('Failed to load vote feed:', error);
      setStatusMessage('투표 피드를 불러오지 못했습니다.');
    } finally {
      setIsLoading(false);
    }
  }, [user]);

  useEffect(() => {
    void loadVoteFeed();
  }, [loadVoteFeed]);

  const posts = useMemo<VotePost[]>(() => {
    const votePosts = feedItems.map<VotePost>((item, index) => ({
      type: 'vote',
      id: `vote-${item.item_id}`,
      item,
      topic: questionPrompts[index % questionPrompts.length],
      owner: `room_${String(item.item_id).slice(-3)}`,
      mood: item.category || 'Wishlist',
    }));

    return votePosts.flatMap((post, index) => (index === 1 ? [post, brandPosts[0]] : index === 3 ? [post, brandPosts[1]] : [post]));
  }, [feedItems]);

  const handleVote = async (item: VoteItem, direction: VoteDirection) => {
    if (!user || votingItemId) return;

    setVotingItemId(item.item_id);
    try {
      const votedItem = await apiJson<VoteItem>(`/api/vote/${item.item_id}/vote`, {
        method: 'POST',
        body: JSON.stringify({ direction }),
      });
      setFeedItems((prev) => prev.map((feedItem) => (feedItem.item_id === item.item_id ? votedItem : feedItem)));
      void trackEvent({
        action: direction === 'like' ? 'VOTE_PRETTY' : 'VOTE_UGLY',
        entityType: 'VOTING_ITEM',
        entityId: item.item_id,
        metadata: { title: item.title },
      });
      setStatusMessage(direction === 'like' ? '예뻐요 의견을 남겼습니다.' : '별로에요 의견을 남겼습니다.');
    } catch (error) {
      console.error('Vote failed:', error);
      setStatusMessage('투표 처리 중 오류가 발생했습니다.');
    } finally {
      setVotingItemId(null);
    }
  };

  const handleAddToWishlist = (item: VoteItem) => {
    setWishlistItems((prev) => (prev.some((wishlistItem) => wishlistItem.item_id === item.item_id) ? prev : [item, ...prev]));
    void trackEvent({ action: 'SAVE_WISHLIST', entityType: 'VOTING_ITEM', entityId: item.item_id, metadata: { title: item.title } });
    setStatusMessage('내 위시리스트에 추가했습니다.');
  };

  const handleRemoveFromWishlist = (item: VoteItem) => {
    setWishlistItems((prev) => prev.filter((wishlistItem) => wishlistItem.item_id !== item.item_id));
    setStatusMessage('위시리스트에서 삭제했습니다.');
  };

  if (!isInitializing && !user) {
    return (
      <div className="liquid-shell flex min-h-[620px] items-center justify-center rounded-[2.5rem] p-6 text-center">
        <div className="max-w-md rounded-[2rem] border border-white/50 bg-white/55 p-8 shadow-2xl backdrop-blur-3xl">
          <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-full bg-black text-white shadow-xl"><Heart className="h-7 w-7" /></div>
          <h2 className="editorial-heading text-3xl text-foreground">로그인이 필요합니다</h2>
          <p className="mt-3 text-sm leading-7 text-muted-foreground">게스트 로그인으로 위시 아이템 투표 피드와 브랜드 콘텐츠를 바로 확인할 수 있습니다.</p>
          <button type="button" onClick={() => void loginAsGuest()} className="mt-6 rounded-full bg-black px-6 py-3 text-sm font-bold text-white transition hover:-translate-y-0.5 hover:bg-black/85">게스트로 시작하기</button>
        </div>
      </div>
    );
  }

  return (
    <div className="liquid-shell relative overflow-hidden rounded-[2.5rem] px-4 py-6 sm:px-6 lg:px-8">
      <div className="pointer-events-none absolute -left-24 top-10 h-72 w-72 rounded-full bg-cyan-200/40 blur-3xl" />
      <div className="pointer-events-none absolute -right-24 top-40 h-96 w-96 rounded-full bg-fuchsia-200/40 blur-3xl" />

      <div className="relative grid gap-8 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section className="mx-auto w-full max-w-[720px] space-y-6">
          <div className="rounded-[2rem] border border-white/60 bg-white/45 p-6 shadow-[0_24px_80px_rgba(15,23,42,0.10)] backdrop-blur-3xl">
            <p className="text-[11px] font-black uppercase tracking-[0.36em] text-black/45">Vote Feed</p>
            <h1 className="editorial-heading mt-3 text-4xl leading-tight text-foreground sm:text-6xl">위시 고민을 넘겨보는 소셜 패션 피드</h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-muted-foreground">아이템 하나가 하나의 게시물이 됩니다. 위아래로 스크롤하며 예뻐요, 별로에요, 위시에 저장하기 반응을 남기고 룩북과 카드뉴스도 함께 발견하세요.</p>
          </div>

          {statusMessage && <p className="rounded-full border border-white/60 bg-white/60 px-4 py-2 text-center text-sm font-semibold text-foreground shadow-sm backdrop-blur-2xl">{statusMessage}</p>}

          <div className="feed-scroll-area space-y-7">
            <AnimatePresence>
              {posts.map((post) =>
                post.type === 'vote' ? (
                  <motion.article key={post.id} layout initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} className="overflow-hidden rounded-[2.25rem] border border-white/60 bg-white/55 shadow-[0_30px_100px_rgba(15,23,42,0.14)] backdrop-blur-3xl">
                    <div className="flex items-center justify-between px-5 py-4">
                      <div><p className="text-sm font-black text-foreground">@{post.owner}</p><p className="text-xs font-semibold text-muted-foreground">{post.mood} 고민 투표</p></div>
                      <Sparkles className="h-5 w-5 text-black/40" />
                    </div>
                    <div className="relative aspect-[4/5] bg-neutral-100">
                      <img src={getDisplayImageUrl(post.item.image_url, null)} alt={post.item.title} className="h-full w-full object-cover" referrerPolicy="no-referrer" />
                      <div className="absolute inset-x-4 bottom-4 rounded-[1.5rem] border border-white/30 bg-black/35 p-4 text-white backdrop-blur-2xl">
                        <p className="text-[11px] font-bold uppercase tracking-[0.28em] text-white/70">Question</p>
                        <h2 className="mt-1 text-2xl font-black leading-tight">{post.topic}</h2>
                      </div>
                    </div>
                    <div className="space-y-4 p-5">
                      <div className="flex items-start justify-between gap-4"><div><p className="text-[11px] font-black uppercase tracking-[0.26em] text-black/40">{post.item.brand || post.item.shop}</p><h3 className="mt-1 text-xl font-extrabold text-foreground">{post.item.title}</h3></div><p className="rounded-2xl bg-black px-3 py-2 text-sm font-bold text-white">{formatPrice(post.item.price)}</p></div>
                      <div className="flex flex-wrap gap-2 text-xs font-bold text-foreground/70"><span className="rounded-full bg-black/5 px-3 py-1.5">예뻐요 {post.item.likes ?? 0}</span><span className="rounded-full bg-black/5 px-3 py-1.5">별로에요 {post.item.dislikes ?? 0}</span><span className="rounded-full bg-black/5 px-3 py-1.5">{post.item.category}</span></div>
                      <div className="grid grid-cols-3 gap-2">
                        <button onClick={() => void handleVote(post.item, 'dislike')} disabled={votingItemId === post.item.item_id} className="rounded-2xl border border-rose-200/80 bg-rose-50/80 px-3 py-3 text-sm font-black text-rose-600 transition hover:-translate-y-0.5 disabled:opacity-50"><ThumbsDown className="mx-auto mb-1 h-4 w-4" />별로에요</button>
                        <button onClick={() => handleAddToWishlist(post.item)} className="rounded-2xl border border-black/10 bg-black px-3 py-3 text-sm font-black text-white transition hover:-translate-y-0.5"><Plus className="mx-auto mb-1 h-4 w-4" />위시에 저장</button>
                        <button onClick={() => void handleVote(post.item, 'like')} disabled={votingItemId === post.item.item_id} className="rounded-2xl border border-emerald-200/80 bg-emerald-50/80 px-3 py-3 text-sm font-black text-emerald-700 transition hover:-translate-y-0.5 disabled:opacity-50"><ThumbsUp className="mx-auto mb-1 h-4 w-4" />예뻐요</button>
                      </div>
                    </div>
                  </motion.article>
                ) : (
                  <motion.article key={post.id} initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} className="overflow-hidden rounded-[2.25rem] border border-white/60 bg-slate-950 text-white shadow-[0_30px_100px_rgba(15,23,42,0.22)]">
                    <div className="relative aspect-[16/10]"><img src={post.imageUrl} alt={post.title} className="h-full w-full object-cover opacity-80" /><div className="absolute inset-0 bg-gradient-to-t from-black via-black/20 to-transparent" /><div className="absolute bottom-0 p-6"><p className="text-[11px] font-black uppercase tracking-[0.35em] text-white/55">{post.label}</p><h3 className="mt-2 text-3xl font-black">{post.title}</h3><p className="mt-3 max-w-lg text-sm leading-6 text-white/75">{post.description}</p></div></div>
                    <div className="flex flex-wrap items-center justify-between gap-3 p-5"><div className="flex flex-wrap gap-2">{post.tags.map((tag) => <span key={tag} className="rounded-full bg-white/10 px-3 py-1.5 text-xs font-bold">#{tag}</span>)}</div><button className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-black text-black"><Bookmark className="h-4 w-4" />{post.cta}</button></div>
                  </motion.article>
                ),
              )}
            </AnimatePresence>
          </div>

          {!isLoading && posts.length === 0 && <div className="rounded-[2rem] border border-dashed border-black/15 bg-white/60 p-10 text-center backdrop-blur-2xl"><Heart className="mx-auto h-10 w-10" /><h2 className="mt-4 text-2xl font-black">표시할 게시물이 없습니다</h2><button onClick={() => void loadVoteFeed()} className="mt-5 inline-flex items-center gap-2 rounded-full bg-black px-5 py-3 text-sm font-bold text-white"><RotateCcw className="h-4 w-4" />다시 불러오기</button></div>}
        </section>

        <aside className="space-y-4 xl:sticky xl:top-24">
          <div className="rounded-[2rem] border border-white/60 bg-white/50 p-5 shadow-[0_24px_80px_rgba(15,23,42,0.10)] backdrop-blur-3xl">
            <p className="text-[11px] font-black uppercase tracking-[0.32em] text-black/40">My Wishlist</p>
            <h3 className="mt-2 text-2xl font-black text-foreground">저장한 반응 {wishlistItems.length}</h3>
            <div className="mt-4 space-y-3">
              {wishlistItems.length ? wishlistItems.map((item) => <article key={item.item_id} className="flex gap-3 rounded-2xl bg-white/70 p-3"><img src={getDisplayImageUrl(item.image_url, null)} alt={item.title} className="h-20 w-16 rounded-xl object-cover" referrerPolicy="no-referrer" /><div className="min-w-0 flex-1"><p className="truncate text-xs font-black text-black/45">{item.brand}</p><h4 className="truncate text-sm font-bold">{item.title}</h4><button onClick={() => handleRemoveFromWishlist(item)} className="mt-2 inline-flex items-center gap-1 text-xs font-bold text-black/55"><X className="h-3 w-3" />삭제</button></div></article>) : <p className="rounded-2xl border border-dashed border-black/10 bg-white/60 px-4 py-8 text-center text-sm text-muted-foreground">피드에서 마음에 드는 위시를 저장해보세요.</p>}
            </div>
          </div>
          <div className="rounded-[2rem] bg-black p-5 text-white shadow-2xl"><p className="text-[11px] font-black uppercase tracking-[0.32em] text-white/45">Feed Mix</p><p className="mt-3 text-sm leading-7 text-white/75">위시 고민 투표 게시물 사이에 브랜드 룩북, 패션 정보 카드뉴스가 자연스럽게 섞이는 구조로 리팩토링했습니다.</p><div className="mt-4 flex gap-3 text-white/60"><MessageCircle className="h-5 w-5" /><Send className="h-5 w-5" /><Bookmark className="h-5 w-5" /></div></div>
        </aside>
      </div>
    </div>
  );
}
