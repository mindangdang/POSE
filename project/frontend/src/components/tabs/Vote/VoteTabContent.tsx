import { AnimatePresence, motion } from 'framer-motion';
import { Heart, ImagePlus, MessageCircle, Plus, Send, ThumbsDown, ThumbsUp, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { trackEvent } from '../../../lib/analytics';
import { getDisplayImageUrl } from '../../../lib/imageUrl';
import type { SavedItem } from '../../../types/item';
import { useAuth } from '../../../hooks/useAuth';

type VoteDirection = 'like' | 'dislike';
type CommunityPost = {
  id: string;
  type: 'vote' | 'story';
  title: string;
  body: string;
  author: string;
  imageUrl?: string;
  item?: SavedItem;
  comments: string[];
  likes: number;
  dislikes: number;
};

type VoteTabContentProps = {
  items: SavedItem[];
  userPosts: CommunityPost[];
  onCreatePost: (post: Omit<CommunityPost, 'id' | 'author' | 'comments' | 'likes' | 'dislikes'>) => void;
  composerSignal?: number;
};

const inspirationPosts: CommunityPost[] = [
  {
    id: 'sample-lookbook',
    type: 'story',
    title: '주말 룩북 아이디어',
    body: '블랙 재킷에 차분한 데님을 맞추고 작은 실버 액세서리로 포인트를 주면 좋을 것 같아요.',
    author: 'RoomShow',
    imageUrl: 'https://images.unsplash.com/photo-1496747611176-843222e1e57c?auto=format&fit=crop&w=900&q=80',
    comments: ['실버 포인트 좋네요!', '데님 워싱도 궁금해요.'],
    likes: 0,
    dislikes: 0,
  },
  {
    id: 'sample-review',
    type: 'story',
    title: '빈티지 가방 후기',
    body: '수납은 작지만 룩 완성도가 확 올라가요. 비슷한 무드의 신발을 찾는 중입니다.',
    author: 'Editor',
    imageUrl: 'https://images.unsplash.com/photo-1594223274512-ad4803739b7c?auto=format&fit=crop&w=900&q=80',
    comments: ['착샷도 보고 싶어요.'],
    likes: 0,
    dislikes: 0,
  },
];

export type { CommunityPost };

export function VoteTabContent({ items, userPosts, onCreatePost, composerSignal = 0 }: VoteTabContentProps) {
  const { user, isInitializing, loginAsGuest } = useAuth();
  const [wishlistIds, setWishlistIds] = useState<number[]>([]);
  const [votedPosts, setVotedPosts] = useState<Record<string, VoteDirection>>({});
  const [commentDrafts, setCommentDrafts] = useState<Record<string, string>>({});
  const [comments, setComments] = useState<Record<string, string[]>>({});
  const [composerOpen, setComposerOpen] = useState(false);
  const [newPost, setNewPost] = useState({ title: '', body: '', imageUrl: '' });

  useEffect(() => {
    if (composerSignal > 0) setComposerOpen(true);
  }, [composerSignal]);

  const votePosts = useMemo<CommunityPost[]>(
    () => items.map((item) => ({
      id: `wish-${item.product_id}`,
      type: 'vote',
      title: item.title || '위시템 투표',
      body: '이 위시템이 나에게 어울릴지, 객관적으로 어떤지 투표해주세요.',
      author: 'Wishlist',
      imageUrl: item.image_url,
      item,
      comments: [],
      likes: item.likes ?? 0,
      dislikes: item.dislikes ?? 0,
    })),
    [items],
  );

  const posts = useMemo(() => [...userPosts, ...votePosts, ...inspirationPosts], [userPosts, votePosts]);

  const handleVote = (post: CommunityPost, direction: VoteDirection) => {
    if (votedPosts[post.id]) return;
    setVotedPosts((prev) => ({ ...prev, [post.id]: direction }));
    void trackEvent({
      action: direction === 'like' ? 'VOTE_PRETTY' : 'VOTE_UGLY',
      entityType: 'VOTING_ITEM',
      entityId: post.item?.product_id ?? post.id,
      metadata: { title: post.title },
    });
  };

  const handleWishlist = (post: CommunityPost) => {
    if (!post.item) return;
    setWishlistIds((prev) => (prev.includes(post.item!.product_id) ? prev : [post.item!.product_id, ...prev]));
    void trackEvent({ action: 'SAVE_WISHLIST', entityType: 'VOTING_ITEM', entityId: post.item.product_id, metadata: { title: post.title } });
  };

  const handleComment = (postId: string) => {
    const draft = commentDrafts[postId]?.trim();
    if (!draft) return;
    setComments((prev) => ({ ...prev, [postId]: [...(prev[postId] || []), draft] }));
    setCommentDrafts((prev) => ({ ...prev, [postId]: '' }));
  };

  const handleSubmitPost = () => {
    if (!newPost.title.trim() || !newPost.body.trim()) return;
    onCreatePost({ type: 'story', title: newPost.title.trim(), body: newPost.body.trim(), imageUrl: newPost.imageUrl.trim() || undefined });
    setNewPost({ title: '', body: '', imageUrl: '' });
    setComposerOpen(false);
  };

  if (!isInitializing && !user) {
    return (
      <div className="rounded-[2rem] border border-black/10 bg-[#f7f1e6] p-8 text-center">
        <Heart className="mx-auto mb-4 h-10 w-10" />
        <h2 className="text-2xl font-semibold">로그인이 필요합니다</h2>
        <p className="mt-3 text-sm text-muted-foreground">피드형 Vote 탭은 로그인 후 확인할 수 있습니다.</p>
        <button type="button" onClick={() => void loginAsGuest()} className="mt-6 rounded-full bg-black px-5 py-3 text-sm font-semibold text-white">게스트로 시작하기</button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl pb-36">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.35em] text-black/45">Vote Feed</p>
          <h1 className="editorial-heading text-4xl text-foreground">Scroll and share style opinions.</h1>
        </div>
        <button onClick={() => setComposerOpen(true)} className="hidden rounded-full bg-black px-4 py-2 text-sm font-bold text-white sm:inline-flex">게시물 올리기</button>
      </div>

      <div className="space-y-8">
        {posts.map((post) => {
          const isWishlisted = post.item ? wishlistIds.includes(post.item.product_id) : false;
          const mergedComments = [...post.comments, ...(comments[post.id] || [])];
          const vote = votedPosts[post.id];
          return (
            <article key={post.id} className="overflow-hidden rounded-[2rem] border border-black/10 bg-white shadow-[0_20px_70px_rgba(17,24,39,0.08)]">
              <div className="flex items-center justify-between px-5 py-4">
                <div>
                  <p className="text-xs font-bold text-black/45">@{post.author}</p>
                  <h2 className="text-lg font-bold text-foreground">{post.title}</h2>
                </div>
                <span className="rounded-full bg-[#f7f1e6] px-3 py-1 text-[10px] font-bold uppercase tracking-widest">{post.type === 'vote' ? '투표' : '게시물'}</span>
              </div>
              {post.imageUrl && <img src={getDisplayImageUrl(post.imageUrl, null)} alt={post.title} className="max-h-[680px] w-full bg-muted object-cover" referrerPolicy="no-referrer" />}
              <div className="space-y-4 p-5">
                <p className="text-sm leading-7 text-foreground">{post.body}</p>
                {post.type === 'vote' && (
                  <div className="grid grid-cols-3 gap-2">
                    <button onClick={() => handleVote(post, 'dislike')} disabled={Boolean(vote)} className={`rounded-full border px-3 py-2 text-xs font-bold ${vote === 'dislike' ? 'bg-rose-500 text-white' : 'bg-white'}`}><ThumbsDown className="mr-1 inline h-3 w-3" />별로에요</button>
                    <button onClick={() => handleVote(post, 'like')} disabled={Boolean(vote)} className={`rounded-full border px-3 py-2 text-xs font-bold ${vote === 'like' ? 'bg-emerald-600 text-white' : 'bg-white'}`}><ThumbsUp className="mr-1 inline h-3 w-3" />예뻐요</button>
                    <button onClick={() => handleWishlist(post)} className={`rounded-full px-3 py-2 text-xs font-bold ${isWishlisted ? 'bg-pink-500 text-white' : 'bg-black text-white'}`}><Plus className="mr-1 inline h-3 w-3" />{isWishlisted ? '저장됨' : '위시에 저장'}</button>
                  </div>
                )}
                <div className="border-t border-border pt-4">
                  <div className="mb-3 flex items-center gap-2 text-xs font-bold text-muted-foreground"><MessageCircle className="h-4 w-4" />댓글 {mergedComments.length}</div>
                  <div className="space-y-2">{mergedComments.map((comment, index) => <p key={index} className="rounded-xl bg-muted px-3 py-2 text-sm">{comment}</p>)}</div>
                  <div className="mt-3 flex gap-2">
                    <input value={commentDrafts[post.id] || ''} onChange={(e) => setCommentDrafts((prev) => ({ ...prev, [post.id]: e.target.value }))} placeholder="댓글 달기" className="min-w-0 flex-1 rounded-full border border-border px-4 py-2 text-sm outline-none" />
                    <button onClick={() => handleComment(post.id)} className="rounded-full bg-black p-2 text-white"><Send className="h-4 w-4" /></button>
                  </div>
                </div>
              </div>
            </article>
          );
        })}
      </div>

      <AnimatePresence>
        {composerOpen && (
          <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 20 }} className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-2xl">
              <div className="mb-5 flex items-center justify-between"><h3 className="text-xl font-bold">게시물 올리기</h3><button onClick={() => setComposerOpen(false)}><X className="h-5 w-5" /></button></div>
              <input value={newPost.title} onChange={(e) => setNewPost((prev) => ({ ...prev, title: e.target.value }))} placeholder="게시물 제목" className="mb-3 w-full rounded-xl border border-border px-4 py-3 text-sm outline-none" />
              <textarea value={newPost.body} onChange={(e) => setNewPost((prev) => ({ ...prev, body: e.target.value }))} placeholder="글 내용" rows={6} className="mb-3 w-full rounded-xl border border-border px-4 py-3 text-sm outline-none" />
              <label className="mb-4 flex items-center gap-2 rounded-xl border border-dashed border-border px-4 py-3 text-sm text-muted-foreground"><ImagePlus className="h-4 w-4" /><input value={newPost.imageUrl} onChange={(e) => setNewPost((prev) => ({ ...prev, imageUrl: e.target.value }))} placeholder="사진 URL 첨부" className="min-w-0 flex-1 outline-none" /></label>
              <button onClick={handleSubmitPost} className="w-full rounded-full bg-black py-3 text-sm font-bold text-white">작성 완료</button>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
