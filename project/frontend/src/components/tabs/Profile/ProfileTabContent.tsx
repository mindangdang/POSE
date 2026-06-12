import { motion } from 'framer-motion';
import { User, Zap, Heart, Compass, Loader2, Sparkles, Instagram, Lightbulb } from 'lucide-react';
import { useState } from 'react';

import { apiJson } from '../../../lib/api';
import type { SavedItem } from '../../../types/item';
import { useAuth } from '../../../hooks/useAuth';

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
  ambientColor: string;
  onAmbientColorChange: (color: string) => void;
  isAmbientActive: boolean;
  onAmbientToggle: () => void;
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
  'from-sky-500/8 via-blue-500/4 to-transparent border-sky-100',
  'from-blue-500/8 via-cyan-500/4 to-transparent border-blue-100',
  'from-indigo-500/8 via-sky-500/4 to-transparent border-indigo-100',
  'from-cyan-500/8 via-teal-500/4 to-transparent border-cyan-100',
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

function ProfileHeader() {
  const { user } = useAuth();

  return (
    <div className="flex flex-col md:flex-row items-start md:items-end justify-between gap-8 pb-10">
      <div className="space-y-2">
        <h2 className="font-sans font-bold text-4xl md:text-5xl lg:text-6xl text-foreground">
          {user?.username || 'Anonymous'}
        </h2>
      </div>
    </div>
  );
}

function TasteSectionCard({ section }: TasteSectionCardProps) {
  const paragraphs = parseTasteBodyParagraphs(section.body);
  const [openParagraphs, setOpenParagraphs] = useState<Record<number, boolean>>(
    Object.fromEntries(paragraphs.map((_, index) => [index, true])),
  );

  const toggleParagraph = (index: number) => {
    setOpenParagraphs((current) => ({
      ...current,
      [index]: !current[index],
    }));
  };

  return (
    <div className="rounded-2xl border border-border bg-muted/50 p-6">
      <div className="flex items-start justify-between gap-3">
        <h5 className="text-lg font-bold text-foreground capitalize">
          {section.title}
        </h5>
        <Compass className="h-5 w-5 text-muted-foreground" />
      </div>
      <div className="mt-4 space-y-3">
        {paragraphs.map((paragraph, lineIndex) => (
          <div
            key={`${section.title}-${lineIndex}`}
            className="rounded-xl border border-border bg-background px-4 py-4"
          >
            {paragraph.title ? (
              <button
                type="button"
                onClick={() => toggleParagraph(lineIndex)}
                className="inline-flex items-center rounded-full bg-muted px-3 py-1.5 text-xs font-bold uppercase tracking-wider text-foreground transition-all hover:bg-muted/80"
              >
                #{paragraph.title}
              </button>
            ) : null}
            {openParagraphs[lineIndex] !== false ? (
              <p className="mt-3 text-sm font-bold leading-relaxed text-muted-foreground">
                {paragraph.description}
              </p>
            ) : null}
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
}: TasteSummaryCardProps) {
  const { user } = useAuth();

  return (
    <div className="relative overflow-hidden rounded-3xl border border-border bg-background">
      <div className="p-8 md:p-10 space-y-8">
        <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
          <div className="space-y-4">
            <span className="inline-flex items-center gap-2 rounded-full border border-border px-4 py-2 text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">
              <Zap className="w-3.5 h-3.5" fill="currentColor" />
              Taste Analysis
            </span>
            <div>
              <h4 className="editorial-heading text-3xl md:text-4xl text-foreground">
                {user?.username || 'Anonymous'}&apos;s
                <br />
                <span className="text-muted-foreground">Style DNA</span>
              </h4>
              <p className="mt-3 text-sm font-medium text-muted-foreground max-w-md">
                AI-curated insights about your aesthetic preferences, mood patterns, and style inspirations.
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

        <div className="rounded-2xl bg-muted p-5 text-sm font-medium text-muted-foreground">
          <span className="mr-2 inline-flex rounded-full bg-foreground px-3 py-1 text-[10px] font-bold uppercase tracking-[0.15em] text-background">
            Share Tip
          </span>
          Click share to copy your profile text and open Instagram.
        </div>

        <div className="flex flex-wrap items-center justify-end gap-3 border-t border-border pt-6">
          <button
            onClick={onGenerateTaste}
            disabled={isGeneratingTaste}
            className="flex items-center gap-2 rounded-full border border-border bg-background px-6 py-3 text-xs font-bold uppercase tracking-wider text-foreground transition-all hover:bg-muted"
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
            className="flex items-center gap-2 rounded-full bg-foreground px-6 py-3 text-xs font-bold uppercase tracking-wider text-background transition-all hover:opacity-90"
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
    <div className="py-24 flex flex-col items-center justify-center text-center">
      {hasItems ? (
        <div className="space-y-6 flex flex-col items-center">
          <div>
            <h3 className="editorial-heading text-3xl text-foreground mb-3">넌 어떤 사람이고 싶어</h3>
          </div>
          <button
            onClick={onGenerateTaste}
            disabled={isGeneratingTaste}
            className="pb-1 px-1 border-b-2 border-black text-black text-sm font-bold uppercase tracking-wider hover:opacity-70 transition-opacity disabled:opacity-50"
          >
            {isGeneratingTaste ? 'Analyzing...' : "Let's findout"}
          </button>
        </div>
      ) : (
        <div className="space-y-6 flex flex-col items-center">
          <div>
            <h3 className="editorial-heading text-3xl text-foreground mb-3">네가 적어가는 나는 어떻게 변할까</h3>
          </div>
          <button
            type="button"
            onClick={onGoToFeed}
            className="pb-1 px-1 border-b-2 border-black text-black text-sm font-bold uppercase tracking-wider hover:opacity-70 transition-opacity"
          >
            창문열기
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
    <div className="space-y-6 pt-10">
      <div className="flex items-center justify-between pb-4 border-b border-border">
        <h4 className="text-lg font-bold text-foreground">
          My Closet
        </h4>
        <span className="text-xs font-medium text-muted-foreground">
          {items.length} 개
        </span>
      </div>
      <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
        {items.slice(0, 12).map((item) => (
          <div
            key={item.id}
            className="aspect-square bg-muted overflow-hidden cursor-pointer group relative rounded-xl"
            onClick={() => onSelectItem(item)}
          >
            <img
              src={getProfileImageUrl(item)}
              className="w-full h-full object-cover group-hover:scale-[1.02] transition-all duration-500"
              referrerPolicy="no-referrer"
              onError={(e) => {
                const target = e.target as HTMLImageElement;
                let localUrl: string | undefined;
                try {
                  const facts = typeof item.facts === 'string' ? JSON.parse(item.facts) : (item.facts || {});
                  localUrl = facts?.local_image_url;
                } catch (err) {
                  // parsing error ignored
                }
                if (localUrl && !target.src.includes(localUrl)) {
                  target.src = `/api/images/${localUrl}`;
                } else {
                  target.src = 'https://via.placeholder.com/400x500?text=No+Image';
                }
              }}
            />
            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors duration-300" />
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
  ambientColor,
  onAmbientColorChange,
  isAmbientActive,
  onAmbientToggle,
}: ProfileTabContentProps) {
  const { user } = useAuth();
  const tasteSections = buildTasteProfileSections(taste);
  const [isGeneratingTaste, setIsGeneratingTaste] = useState(false);
  const [isSharingProfile, setIsSharingProfile] = useState(false);

  const handleGenerateTaste = async () => {
    setIsGeneratingTaste(true);
    onTasteChange('');
    try {
      const data = await apiJson<{ success?: boolean; summary?: string; message?: string }>('/api/generate-taste', {
        method: 'POST',
      });

      if (data.success) {
        onTasteChange(data.summary ?? '');
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
      className="max-w-4xl mx-auto space-y-10 pb-40"
    >
      <ProfileHeader />

      {/* Ambient Color Switcher Section */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-6 py-6 border-b border-border">
        <div className="flex-1 w-full max-w-xs">
          <div className="relative">
            <input
              type="text"
              value={ambientColor}
              onChange={(e) => onAmbientColorChange(e.target.value)}
              placeholder="좋아하는 색상의 hex 코드를 넣고 조명을 켜보세요!"
              className="w-full bg-transparent border-b-2 border-black py-2 text-sm font-bold focus:outline-none placeholder:text-muted-foreground/50"
            />
            <div 
              className="absolute right-0 bottom-3 w-4 h-4 rounded-full border border-black/10"
              style={{ backgroundColor: ambientColor }}
            />
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={onAmbientToggle}
            className={`relative w-14 h-7 rounded-full transition-all duration-300 flex items-center px-1 ${isAmbientActive ? 'bg-black' : 'bg-muted border border-border'}`}
          >
            <motion.div
              animate={{ x: isAmbientActive ? 28 : 0 }}
              className={`w-5 h-5 rounded-full flex items-center justify-center shadow-sm ${isAmbientActive ? 'bg-white' : 'bg-white'}`}
            >
              <Lightbulb className={`w-3 h-3 ${isAmbientActive ? 'text-black' : 'text-muted-foreground'}`} />
            </motion.div>
          </button>
        </div>
      </div>

      <div className="flex gap-10 flex-col">
        <div className="lg:col-span-8">
          {taste
            ? (
              <TasteSummaryCard
                isGeneratingTaste={isGeneratingTaste}
                isSharingProfile={isSharingProfile}
                onGenerateTaste={handleGenerateTaste}
                onShareProfile={handleShareProfile}
                tasteSections={tasteSections}
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
