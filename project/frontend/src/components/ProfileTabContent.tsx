import { motion } from 'framer-motion';
import { User, Zap, Heart, Compass, Loader2, Sparkles, Instagram } from 'lucide-react';
import { useState } from 'react';

import type { SavedItem } from '../types/item';
import type { AppUser } from '../types/user';

type TasteProfileSection = {
  title: string;
  body: string[];
  accent: string;
};

type TasteBodyParagraph = {
  description: string;
  title?: string;
};

type ProfileTabContentProps = {
  items: SavedItem[];
  onGoToFeed: () => void;
  onSelectItem: (item: SavedItem) => void;
  onTasteChange: React.Dispatch<React.SetStateAction<string>>;
  taste: string;
  user: AppUser | null;
};

type ProfileHeaderProps = {
  user: AppUser | null;
};

type TasteAnalysisHeaderProps = {
  user: AppUser | null;
};

type TasteSectionCardProps = {
  section: TasteProfileSection;
};

type TasteSummaryCardProps = {
  isGeneratingTaste: boolean;
  isSharingProfile: boolean;
  onGenerateTaste: () => Promise<void>;
  onShareProfile: () => Promise<void>;
  tasteSections: TasteProfileSection[];
  user: AppUser | null;
};

type EmptyTasteStateProps = {
  hasItems: boolean;
  isGeneratingTaste: boolean;
  onGenerateTaste: () => Promise<void>;
  onGoToFeed: () => void;
};

type RecentInspirationsGridProps = {
  items: SavedItem[];
  onSelectItem: (item: SavedItem) => void;
};

const tasteSectionAccents = [
  'from-purple-500/15 via-pink-500/10 to-transparent border-purple-200/70',
  'from-blue-500/15 via-cyan-500/10 to-transparent border-blue-200/70',
  'from-yellow-400/20 via-orange-400/10 to-transparent border-yellow-200/70',
  'from-emerald-500/15 via-teal-500/10 to-transparent border-emerald-200/70',
];

function normalizeTasteValue(value: unknown): string[] {
  if (value == null) return [];
  if (Array.isArray(value)) {
    return value.flatMap((entry) => normalizeTasteValue(entry));
  }
  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>).map(([key, nested]) => {
      const nestedText = normalizeTasteValue(nested).join(' · ');
      return nestedText ? `${key.replace(/_/g, ' ')}: ${nestedText}` : key.replace(/_/g, ' ');
    });
  }
  return String(value)
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);
}

function cleanTasteParagraph(text: string) {
  return text
    .split('\n')
    .map((line) => line.replace(/^[-*]\s*/, '').trim())
    .filter(Boolean)
    .join(' ');
}

function cleanTasteHeading(text: string) {
  return text.replace(/^\*+/, '').replace(/\*+$/, '').trim();
}

function parseTasteBodyParagraphs(body: string[]): TasteBodyParagraph[] {
  const rawText = body.join('\n\n').trim();
  if (!rawText) return [];

  const headingRegex = /\*+[^*]+?\*+/g;
  const headingMatches = Array.from(rawText.matchAll(headingRegex));

  if (headingMatches.length > 0) {
    const paragraphs = headingMatches
      .map((match, index) => {
        const matchText = match[0] ?? '';
        const title = cleanTasteHeading(matchText);
        const start = (match.index ?? 0) + matchText.length;
        const end = index < headingMatches.length - 1
          ? (headingMatches[index + 1].index ?? rawText.length)
          : rawText.length;
        const description = cleanTasteParagraph(rawText.slice(start, end));

        return {
          title: title || undefined,
          description,
        };
      })
      .filter((paragraph) => paragraph.title || paragraph.description);

    if (paragraphs.length > 0) {
      return paragraphs;
    }
  }

  const lines = rawText
    .split('\n')
    .map((line) => line.trim());
  const starredHeadingRegex = /^\*+\s*(.+?)\s*\*+$/;
  const paragraphs: TasteBodyParagraph[] = [];
  let currentTitle: string | undefined;
  let currentLines: string[] = [];

  const flushParagraph = () => {
    const description = cleanTasteParagraph(currentLines.join('\n'));
    if (!currentTitle && !description) return;

    paragraphs.push({
      title: currentTitle,
      description,
    });

    currentTitle = undefined;
    currentLines = [];
  };

  lines.forEach((line) => {
    if (!line) {
      return;
    }

    const headingMatch = line.match(starredHeadingRegex);
    if (headingMatch) {
      flushParagraph();
      currentTitle = headingMatch[1].trim();
      currentLines = [];
      return;
    }

    currentLines.push(line);
  });

  flushParagraph();

  if (paragraphs.length > 0) {
    return paragraphs;
  }

  return body
    .map((entry) => cleanTasteParagraph(entry))
    .filter(Boolean)
    .map((description) => ({ description }));
}

function buildTasteProfileSections(taste: string): TasteProfileSection[] {
  const trimmed = taste.trim();
  if (!trimmed) return [];

  try {
    const parsed = JSON.parse(trimmed);
    if (parsed && typeof parsed === 'object') {
      const entries = Object.entries(parsed as Record<string, unknown>)
        .map(([key, value], index) => ({
          title: key.replace(/_/g, ' '),
          body: normalizeTasteValue(value),
          accent: tasteSectionAccents[index % tasteSectionAccents.length],
        }))
        .filter((section) => section.body.length > 0);
      if (entries.length > 0) return entries;
    }
  } catch {
    // Fallback to markdown/text parsing below.
  }

  const markdownSections = trimmed
    .split(/\n(?=#{1,3}\s|[-*]\s|\d+\.\s)/)
    .map((block) => block.trim())
    .filter(Boolean)
    .map((block, index) => {
      const lines = block
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean);
      const [first, ...rest] = lines;
      const headingMatch = first?.match(/^#{1,3}\s+(.*)$/);
      const title = headingMatch ? headingMatch[1] : `Taste Point ${index + 1}`;
      const contentSource = headingMatch ? rest : lines;
      const body = contentSource
        .join('\n')
        .split(/\n{2,}/)
        .map((paragraph) => cleanTasteParagraph(paragraph))
        .filter(Boolean);
      return {
        title,
        body,
        accent: tasteSectionAccents[index % tasteSectionAccents.length],
      };
    })
    .filter((section) => section.body.length > 0);

  return markdownSections.length > 0
    ? markdownSections
    : [{ title: 'Taste Profile', body: [trimmed], accent: tasteSectionAccents[0] }];
}

function ProfileHeader({ user }: ProfileHeaderProps) {
  return (
    <div className="flex flex-col md:flex-row items-start md:items-end justify-between gap-8 border-b border-black/10 pb-12">
      <div className="space-y-5">
        <div className="w-28 h-28 rounded-full bg-gradient-to-tr from-blue-600 via-yellow-300 to-purple-600 p-[3px] shadow-2xl">
          <div className="w-full h-full bg-white rounded-full flex items-center justify-center overflow-hidden">
            <User className="w-12 h-12 text-black" />
          </div>
        </div>
        <div className="space-y-1">
          <h2 className="text-5xl font-black tracking-tighter text-black uppercase">
            {user?.username || 'Anonymous'}
          </h2>
          <p className="text-xs font-black text-gray-400 uppercase tracking-widest bg-gray-100 inline-block px-3 py-1 rounded-full">
            POSE Creator No. {user?.id || '000'}
          </p>
        </div>
      </div>
      <div className="text-left md:text-right max-w-xs">
        <p className="text-2xl font-black text-black leading-tight tracking-tighter uppercase bg-clip-text text-transparent bg-gradient-to-r from-black to-gray-500">
          "My Vibe is
          <br />
          my POSE."
        </p>
      </div>
    </div>
  );
}

function TasteAnalysisHeader(_: TasteAnalysisHeaderProps) {
  return (
    <div className="lg:col-span-4 space-y-6">
      <div className="flex items-center gap-3 text-[10px] font-black uppercase tracking-[0.3em] text-blue-600">
        <Zap className="w-3.5 h-3.5" fill="currentColor" />
        Taste Analysis
      </div>
      <h3 className="text-3xl font-black tracking-tighter leading-none uppercase">
        The Patterns
        <br />
        of your
        <br />
        Choices.
      </h3>
      <div className="h-2 w-12 bg-black rounded-full" />
    </div>
  );
}

function TasteSectionCard({ section }: TasteSectionCardProps) {
  const paragraphs = parseTasteBodyParagraphs(section.body);

  return (
    <div className={`rounded-[2rem] border bg-gradient-to-br ${section.accent} p-6 backdrop-blur-sm`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h5 className="mt-2 text-xl font-black tracking-tight text-black capitalize">
            {section.title}
          </h5>
        </div>
        <Compass className="h-5 w-5 text-gray-400" />
      </div>
      <div className="mt-5 space-y-3">
        {paragraphs.map((paragraph, lineIndex) => (
          <div
            key={`${section.title}-${lineIndex}`}
            className="rounded-2xl bg-white/80 px-4 py-4 shadow-sm shadow-black/5"
          >
            {paragraph.title ? (
              <p className="text-xs font-black uppercase tracking-[0.2em] text-gray-500">
                {paragraph.title}
              </p>
            ) : null}
            <p className="mt-2 text-sm font-medium leading-6 text-gray-700">
              {paragraph.description}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function TasteSummaryCard({
  isGeneratingTaste,
  isSharingProfile,
  onGenerateTaste,
  onShareProfile,
  tasteSections,
  user,
}: TasteSummaryCardProps) {
  return (
    <div className="relative overflow-hidden rounded-[3rem] border border-black/5 bg-white shadow-[0_30px_80px_-40px_rgba(0,0,0,0.35)]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(168,85,247,0.18),_transparent_30%),radial-gradient(circle_at_top_right,_rgba(59,130,246,0.12),_transparent_28%),linear-gradient(135deg,_rgba(250,250,250,0.96),_rgba(244,244,245,0.98))]" />
      <div className="relative p-8 md:p-10 space-y-8">
        <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
          <div className="space-y-3">
            <span className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/80 px-4 py-2 text-[10px] font-black uppercase tracking-[0.3em] text-gray-500 backdrop-blur">
              <Heart className="h-3.5 w-3.5 text-pink-500" fill="currentColor" />
              Signature Taste
            </span>
            <div>
              <h4 className="text-3xl md:text-4xl font-black tracking-tighter text-black">
                {user?.username || 'Anonymous'}님의 취향 한 장 요약
              </h4>
              <p className="mt-2 text-sm md:text-base font-medium text-gray-500">
                AI가 모아본 취향의 결, 좋아하는 무드, 다시 찾게 될 영감 포인트예요.
              </p>
            </div>
          </div>
        </div>

        <div className="grid gap-4">
          {tasteSections.map((section, index) => (
            <TasteSectionCard
              key={`${section.title}-${index}`}
              section={section}
            />
          ))}
        </div>

        <div className="rounded-[2rem] border border-dashed border-black/10 bg-white/70 p-5 text-sm font-medium leading-7 text-gray-600">
          <span className="mr-2 inline-flex rounded-full bg-black px-3 py-1 text-[10px] font-black uppercase tracking-[0.25em] text-white">
            Share Tip
          </span>
          공유 버튼을 누르면 프로필 문구를 먼저 클립보드에 복사한 뒤, 인스타그램으로 이동할 수 있게 도와드려요.
        </div>

        <div className="flex flex-wrap items-center justify-end gap-3 border-t border-gray-200/80 pt-6">
          <button
            onClick={onGenerateTaste}
            disabled={isGeneratingTaste}
            className="flex items-center gap-2 rounded-2xl bg-white px-6 py-3 text-xs font-black uppercase tracking-widest text-black shadow-sm transition-all hover:bg-gray-100"
          >
            {isGeneratingTaste ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4" />
            )}
            {isGeneratingTaste ? 'Analyzing...' : 'Re-Analyze'}
          </button>
          <button
            onClick={onShareProfile}
            disabled={isSharingProfile}
            className="flex items-center gap-2 rounded-2xl bg-gradient-to-r from-purple-600 to-blue-600 px-6 py-3 text-xs font-black uppercase tracking-widest text-white shadow-lg shadow-purple-500/30 transition-all hover:from-purple-700 hover:to-blue-700"
          >
            {isSharingProfile ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Instagram className="w-4 h-4" />
            )}
            {isSharingProfile ? 'Preparing...' : 'Share to IG'}
          </button>
        </div>
      </div>
    </div>
  );
}

function EmptyTasteState({
  hasItems,
  isGeneratingTaste,
  onGenerateTaste,
  onGoToFeed,
}: EmptyTasteStateProps) {
  return (
    <div className="py-24 bg-gray-50 rounded-[3rem] flex flex-col items-center justify-center text-center space-y-8 px-4 border-2 border-dashed border-gray-200">
      <div className="w-20 h-20 bg-white rounded-full flex items-center justify-center shadow-sm">
        <Sparkles className="w-8 h-8 text-yellow-400" fill="currentColor" />
      </div>

      {hasItems ? (
        <div className="space-y-6 flex flex-col items-center">
          <p className="text-gray-500 font-bold text-lg max-w-sm">
            충분한 영감이 모였습니다.
            <br />
            당신의 무의식적인 패턴을 꺼내볼까요?
          </p>
          <button
            onClick={onGenerateTaste}
            disabled={isGeneratingTaste}
            className="px-10 py-4 bg-black text-white rounded-full text-sm font-black tracking-widest uppercase hover:bg-gray-800 hover:scale-105 active:scale-95 transition-all flex items-center gap-3 disabled:opacity-50 shadow-xl"
          >
            {isGeneratingTaste ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Zap className="w-5 h-5 text-yellow-400" fill="currentColor" />
            )}
            {isGeneratingTaste ? 'Analyzing POSE...' : 'Analyze My POSE'}
          </button>
        </div>
      ) : (
        <div className="space-y-6 flex flex-col items-center">
          <p className="text-gray-400 font-bold text-lg">아직 수집된 영감이 없습니다.</p>
          <button
            type="button"
            onClick={onGoToFeed}
            className="px-8 py-3 bg-white border-2 border-gray-200 text-black rounded-full text-xs font-black uppercase tracking-widest hover:border-black transition-all"
          >
            Explore Feed
          </button>
        </div>
      )}
    </div>
  );
}

function getProfileImageUrl(item: SavedItem) {
  if (item.image_url?.startsWith('http')) {
    return item.image_url;
  }
  if (item.image_url) {
    return `/api/images/${item.image_url}`;
  }
  return 'https://via.placeholder.com/400x500?text=No+Image';
}

function RecentInspirationsGrid({ items, onSelectItem }: RecentInspirationsGridProps) {
  return (
    <div className="space-y-8 pt-12">
      <div className="flex items-center justify-between border-b border-black/5 pb-6">
        <h4 className="text-xl font-black uppercase tracking-tighter text-black">
          Recent Inspirations
        </h4>
        <div className="text-xs font-bold text-gray-400 uppercase tracking-widest bg-gray-100 px-3 py-1 rounded-full">
          {items.length} Items
        </div>
      </div>
      <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
        {items.slice(0, 12).map((item) => (
          <div
            key={item.id}
            className="aspect-square bg-gray-100 overflow-hidden cursor-pointer group relative rounded-2xl"
            onClick={() => onSelectItem(item)}
          >
            <img
              src={getProfileImageUrl(item)}
              className="w-full h-full object-cover grayscale opacity-80 group-hover:opacity-100 group-hover:grayscale-0 transition-all duration-500 group-hover:scale-110"
              referrerPolicy="no-referrer"
              onError={(e) => {
                (e.target as HTMLImageElement).src =
                  'https://via.placeholder.com/400x500?text=No+Image';
              }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

export function ProfileTabContent({
  items,
  onGoToFeed,
  onSelectItem,
  onTasteChange,
  taste,
  user,
}: ProfileTabContentProps) {
  const tasteSections = buildTasteProfileSections(taste);
  const [isGeneratingTaste, setIsGeneratingTaste] = useState(false);
  const [isSharingProfile, setIsSharingProfile] = useState(false);

  const handleGenerateTaste = async () => {
    setIsGeneratingTaste(true);
    onTasteChange('');
    try {
      const res = await fetch('/api/generate-taste', { method: 'POST' });
      const data = await res.json();

      if (data.success) {
        onTasteChange(data.summary);
      } else {
        alert(data.message || '취향 분석에 실패했습니다.');
      }
    } catch (error) {
      console.error('Taste generation failed:', error);
      alert('취향 분석 중 에러가 발생했습니다.');
    } finally {
      setIsGeneratingTaste(false);
    }
  };

  const handleShareProfile = async () => {
    if (!taste) {
      alert('먼저 취향 프로필을 생성해 주세요.');
      return;
    }

    const shareText = `My POSE! 취향 프로필\n\n닉네임: ${user?.username || 'Anonymous'}\n\n${taste}\n\n#POSE #취향프로필 #Aesthetic`;
    const instagramUrl = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent)
      ? 'instagram://camera'
      : 'https://www.instagram.com/';

    setIsSharingProfile(true);
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(shareText);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = shareText;
        textarea.setAttribute('readonly', 'true');
        textarea.style.position = 'absolute';
        textarea.style.left = '-9999px';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }

      if (navigator.share) {
        try {
          await navigator.share({
            title: '내 취향 프로필',
            text: shareText,
          });
          return;
        } catch (error) {
          if (error instanceof DOMException && error.name === 'AbortError') {
            alert(
              '공유가 취소되었어요. 복사된 텍스트를 인스타그램에 붙여넣어 공유할 수 있어요.',
            );
            return;
          }
          console.error('Native share failed, falling back to Instagram helper:', error);
        }
      }

      window.open(instagramUrl, '_blank', 'noopener,noreferrer');
      alert('취향 프로필이 클립보드에 복사되었어요. 인스타그램에서 붙여넣어 공유해 보세요.');
    } catch (error) {
      console.error('Profile share failed:', error);
      alert('프로필 텍스트 복사에 실패했습니다. 브라우저 권한을 확인해 주세요.');
    } finally {
      setIsSharingProfile(false);
    }
  };

  return (
    <motion.div
      key="profile"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="max-w-4xl mx-auto space-y-16 py-8"
    >
      <ProfileHeader user={user} />

      <div className="flex gap-10 flex-col">
        <TasteAnalysisHeader user={user} />

        <div className="lg:col-span-8">
          {taste
            ? (
              <TasteSummaryCard
                isGeneratingTaste={isGeneratingTaste}
                isSharingProfile={isSharingProfile}
                onGenerateTaste={handleGenerateTaste}
                onShareProfile={handleShareProfile}
                tasteSections={tasteSections}
                user={user}
              />
            )
            : (
              <EmptyTasteState
                hasItems={items.length > 0}
                isGeneratingTaste={isGeneratingTaste}
                onGenerateTaste={handleGenerateTaste}
                onGoToFeed={onGoToFeed}
              />
            )}
        </div>
      </div>

      <RecentInspirationsGrid items={items} onSelectItem={onSelectItem} />
    </motion.div>
  );
}
