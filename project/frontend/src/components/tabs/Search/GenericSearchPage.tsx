import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { apiFetch, apiJson } from '../../../lib/api';
import { getAccessToken } from '../../../lib/token';

type Criterion = {
  id: string;
  attribute: string;
  operator: string;
  value: string | number | boolean | string[];
  weight: number;
  confidence: number;
  is_hard_constraint: boolean;
  source: 'explicit' | 'inferred' | 'user_memory' | 'session_context';
};

type Preference = {
  id: string;
  attribute: string;
  value: string;
  polarity: 'positive' | 'negative';
  weight: number;
  confidence: number;
  scope: 'session' | 'domain' | 'global';
  domain?: string | null;
  source: 'explicit' | 'inferred';
};

type Result = {
  document: {
    document_id: string;
    canonical_url: string;
    title: string;
    snippet: string;
    content: string;
    source: string;
    metadata: Record<string, unknown>;
  };
  rank: number;
  score: number;
  verified: boolean;
  reason: string;
  satisfied_criteria: string[];
  uncertain_criteria: string[];
  evaluations: Array<{
    criterion_id: string;
    status: 'satisfied' | 'violated' | 'unknown';
    evidence_excerpt?: string | null;
  }>;
};

type SearchState = {
  search_id: string;
  status: string;
  intent?: {
    objective: string;
    rewritten_query: string;
    criteria: Criterion[];
    exclusions: Criterion[];
    unresolved_information: string[];
    clarification_required: boolean;
  };
  preferences_used?: string[];
  verified_results?: Result[];
  unverified_results?: Result[];
  excluded_result_count?: number;
  errors?: string[];
  events?: Array<{ type: string; search_id: string; sequence: number }>;
};

const FEEDBACK_REASONS = [
  '검색 목적과 맞지 않음',
  '특정 조건 불충족',
  '이미 알고 있는 정보',
  '신뢰하기 어려운 정보',
  '개인 취향과 맞지 않음',
  '기타',
];

export function GenericSearchPage({ onUseLegacy }: { onUseLegacy: () => void }) {
  const [query, setQuery] = useState('');
  const [personalization, setPersonalization] = useState(true);
  const [sessionId] = useState(() => crypto.randomUUID());
  const [searchId, setSearchId] = useState<string | null>(null);
  const [searchState, setSearchState] = useState<SearchState | null>(null);
  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [exclusions, setExclusions] = useState<Criterion[]>([]);
  const [criteriaEdited, setCriteriaEdited] = useState(false);
  const [location, setLocation] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [feedbackReason, setFeedbackReason] = useState(FEEDBACK_REASONS[0]);
  const [feedbackScope, setFeedbackScope] = useState<'session' | 'related_searches'>('session');
  const [feedbackNotice, setFeedbackNotice] = useState('');
  const [showPreferences, setShowPreferences] = useState(false);
  const [preferences, setPreferences] = useState<Preference[]>([]);
  const [newAttribute, setNewAttribute] = useState('');
  const [newValue, setNewValue] = useState('');
  const [events, setEvents] = useState<string[]>([]);
  const timer = useRef<number | undefined>(undefined);
  const loadedIntentFor = useRef<string | null>(null);
  const results = useMemo(
    () => [...(searchState?.verified_results ?? []), ...(searchState?.unverified_results ?? [])],
    [searchState],
  );

  const loadPreferences = useCallback(async () => {
    try {
      const items = await apiJson<Preference[]>('/api/v2/preferences');
      setPreferences(items);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '선호를 불러오지 못했습니다.');
    }
  }, []);

  const pollSearch = useCallback(async (id: string) => {
    try {
      const state = await apiJson<SearchState>('/api/v2/search/' + id);
      setSearchState(state);
      if (state.intent && loadedIntentFor.current !== id) {
        setCriteria(state.intent.criteria);
        setExclusions(state.intent.exclusions);
        loadedIntentFor.current = id;
      }
      if (['completed', 'partial', 'failed', 'cancelled', 'clarification_required'].includes(state.status)) {
        setBusy(false);
        if (timer.current) window.clearInterval(timer.current);
      }
    } catch (cause) {
      setBusy(false);
      setError(cause instanceof Error ? cause.message : '검색 상태를 불러오지 못했습니다.');
    }
  }, []);

  useEffect(() => {
    if (!searchId) return;
    void pollSearch(searchId);
    timer.current = window.setInterval(() => void pollSearch(searchId), 1200);
    const token = getAccessToken();
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = token
      ? new WebSocket(protocol + '//' + window.location.host + '/api/v2/ws/' + searchId + '?token=' + encodeURIComponent(token))
      : null;
    if (socket) {
      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as { type?: string; search_id?: string };
          if (data.search_id === searchId && data.type) {
            setEvents((current) => [...current.slice(-5), data.type!]);
            void pollSearch(searchId);
          }
        } catch {
          // GET polling remains the recovery path if a socket frame is malformed.
        }
      };
    }
    return () => {
      if (timer.current) window.clearInterval(timer.current);
      socket?.close();
    };
  }, [searchId, pollSearch]);

  useEffect(() => {
    if (showPreferences) void loadPreferences();
  }, [showPreferences, loadPreferences]);

  const submitSearch = useCallback(async (event?: React.FormEvent) => {
    event?.preventDefault();
    if (!query.trim()) return;
    setError('');
    setFeedbackNotice('');
    setBusy(true);
    setSearchState(null);
    setSearchId(null);
    loadedIntentFor.current = null;
    setEvents([]);
    try {
      const context: Record<string, unknown> = { session_id: sessionId };
      if (location.trim()) context.location = location.trim();
      if (criteriaEdited) {
        context.criteria_overrides = criteria;
        context.exclusion_overrides = exclusions;
      }
      const created = await apiJson<{ search_id: string; status: string }>('/api/v2/search', {
        method: 'POST',
        body: JSON.stringify({
          query: query.trim(),
          personalization_enabled: personalization,
          limit: 10,
          context,
        }),
      });
      setSearchId(created.search_id);
      setCriteriaEdited(false);
    } catch (cause) {
      setBusy(false);
      setError(cause instanceof Error ? cause.message : '검색을 시작하지 못했습니다.');
    }
  }, [query, sessionId, location, criteriaEdited, criteria, exclusions, personalization]);

  const cancelSearch = async () => {
    if (!searchId) return;
    try {
      await apiJson('/api/v2/search/' + searchId + '/cancel', { method: 'POST' });
      setBusy(false);
      if (timer.current) window.clearInterval(timer.current);
      await pollSearch(searchId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '검색을 취소하지 못했습니다.');
    }
  };

  const sendFeedback = async (result: Result, type: string) => {
    if (!searchId) return;
    setFeedbackNotice('');
    try {
      await apiJson('/api/v2/feedback', {
        method: 'POST',
        body: JSON.stringify({
          idempotency_key: crypto.randomUUID(),
          search_id: searchId,
          document_id: result.document.document_id,
          original_rank: result.rank,
          feedback_type: type,
          feedback_reason: type === 'RESULT_DISLIKE' || type === 'RESULT_DISMISS' ? feedbackReason : null,
          feedback_scope: feedbackScope,
        }),
      });
      setFeedbackNotice('피드백을 저장했습니다.');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '피드백을 저장하지 못했습니다.');
    }
  };

  const clarify = async () => {
    if (!searchId || !location.trim()) return;
    setBusy(true);
    try {
      const created = await apiJson<{ search_id: string }>('/api/v2/search/' + searchId + '/clarify', {
        method: 'POST',
        body: JSON.stringify({ answers: { location: location.trim() } }),
      });
      setSearchId(created.search_id);
      setSearchState(null);
    } catch (cause) {
      setBusy(false);
      setError(cause instanceof Error ? cause.message : '추가 정보를 반영하지 못했습니다.');
    }
  };

  const updateCriterion = (id: string, patch: Partial<Criterion>, isExclusion: boolean) => {
    setCriteriaEdited(true);
    const setter = isExclusion ? setExclusions : setCriteria;
    setter((current) => current.map((item) => item.id === id ? { ...item, ...patch } : item));
  };

  const addPreference = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!newAttribute.trim() || !newValue.trim()) return;
    try {
      await apiJson('/api/v2/preferences', {
        method: 'POST',
        body: JSON.stringify({
          attribute: newAttribute.trim(),
          value: newValue.trim(),
          polarity: 'positive',
          weight: 0.7,
          confidence: 1,
          scope: 'global',
          source: 'explicit',
        }),
      });
      setNewAttribute('');
      setNewValue('');
      await loadPreferences();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '선호를 저장하지 못했습니다.');
    }
  };

  const updatePreference = async (preference: Preference, patch: Partial<Preference>) => {
    try {
      await apiJson('/api/v2/preferences/' + preference.id, {
        method: 'PATCH',
        body: JSON.stringify(patch),
      });
      await loadPreferences();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '선호를 수정하지 못했습니다.');
    }
  };

  const deletePreference = async (preference: Preference) => {
    try {
      const response = await apiFetch('/api/v2/preferences/' + preference.id, { method: 'DELETE' });
      if (!response.ok) throw new Error('선호를 삭제하지 못했습니다.');
      await loadPreferences();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '선호를 삭제하지 못했습니다.');
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-8 py-10 text-black">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.25em] text-black/45">POSE v2 · Universal search</p>
          <h1 className="mt-2 text-4xl font-extrabold tracking-tight sm:text-5xl">무엇을 찾고 있나요?</h1>
          <p className="mt-3 max-w-2xl text-sm text-black/60">검색 조건과 근거를 확인하고, 원하는 기준으로 결과를 다시 정렬해 보세요.</p>
        </div>
        <button className="rounded-full border border-black/15 px-4 py-2 text-sm hover:bg-black/5" onClick={onUseLegacy}>
          패션 검색 열기
        </button>
      </header>

      <form onSubmit={(event) => void submitSearch(event)} className="rounded-3xl border border-black/10 bg-white p-4 shadow-sm sm:p-6">
        <label className="sr-only" htmlFor="pose-query">검색어</label>
        <textarea
          id="pose-query"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="예: 조용하고 콘센트가 있는 공부하기 좋은 카페"
          rows={3}
          className="w-full resize-y border-0 bg-transparent text-lg outline-none placeholder:text-black/35"
        />
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-black/10 pt-4">
          <label className="inline-flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={personalization}
              onChange={(event) => setPersonalization(event.target.checked)}
              className="accent-black"
            />
            내 선호 반영
          </label>
          <div className="flex gap-2">
            <button type="button" onClick={() => setShowPreferences((current) => !current)} className="rounded-full px-4 py-2 text-sm hover:bg-black/5">
              {showPreferences ? '선호 닫기' : '선호 관리'}
            </button>
            {busy ? (
              <button type="button" onClick={() => void cancelSearch()} className="rounded-full bg-black px-5 py-2 text-sm font-semibold text-white">검색 취소</button>
            ) : (
              <button type="submit" disabled={!query.trim()} className="rounded-full bg-black px-5 py-2 text-sm font-semibold text-white disabled:opacity-40">검색</button>
            )}
          </div>
        </div>
      </form>

      {showPreferences && (
        <section className="rounded-3xl border border-black/10 bg-white p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold">내 검색 선호</h2>
              <p className="text-sm text-black/55">명시적·추론된 선호와 적용 범위를 확인하고 관리합니다.</p>
            </div>
            <button onClick={() => void loadPreferences()} className="text-sm underline">새로고침</button>
          </div>
          <form onSubmit={(event) => void addPreference(event)} className="mt-4 grid gap-2 sm:grid-cols-[1fr_2fr_auto]">
            <input value={newAttribute} onChange={(event) => setNewAttribute(event.target.value)} placeholder="속성 (예: 소음)" className="rounded-xl border border-black/15 px-3 py-2 text-sm" />
            <input value={newValue} onChange={(event) => setNewValue(event.target.value)} placeholder="선호 내용 (예: 조용한 공간)" className="rounded-xl border border-black/15 px-3 py-2 text-sm" />
            <button className="rounded-xl bg-black px-4 py-2 text-sm font-semibold text-white">추가</button>
          </form>
          <div className="mt-4 divide-y divide-black/10">
            {preferences.map((item) => (
              <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div>
                  <p className="font-semibold">{item.attribute}: {item.value}</p>
                  <p className="text-xs text-black/50">{item.source === 'explicit' ? '직접 설정' : '행동에서 추론'} · {item.scope} · 중요도 {item.weight.toFixed(2)}</p>
                </div>
                <div className="flex items-center gap-2">
                  <input aria-label={item.attribute + ' 중요도'} type="range" min="0" max="1" step="0.05" value={item.weight} onChange={(event) => void updatePreference(item, { weight: Number(event.target.value) })} />
                  <button onClick={() => void deletePreference(item)} className="rounded-full px-3 py-1 text-sm text-red-700 hover:bg-red-50">삭제</button>
                </div>
              </div>
            ))}
            {preferences.length === 0 && <p className="py-4 text-sm text-black/50">저장된 선호가 없습니다.</p>}
          </div>
        </section>
      )}

      {(busy || events.length > 0) && (
        <div className="flex flex-wrap items-center gap-2 text-sm text-black/55" aria-live="polite">
          <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-emerald-500" />
          <span>{searchState?.status ?? '검색 준비 중'}</span>
          {[...new Set(events)].slice(-3).map((item) => <span key={item} className="rounded-full bg-black/5 px-2 py-1 text-xs">{item}</span>)}
        </div>
      )}

      {error && <div role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</div>}
      {feedbackNotice && <p role="status" className="text-sm text-emerald-700">{feedbackNotice}</p>}

      {searchState?.intent && (
        <section className="rounded-3xl border border-black/10 bg-stone-50 p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold">검색 의도</h2>
              <p className="mt-1 text-sm text-black/60">{searchState.intent.objective}</p>
              <p className="mt-1 text-xs text-black/45">검색어: {searchState.intent.rewritten_query}</p>
            </div>
            <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold">{searchState.preferences_used?.length ?? 0}개 선호 반영</span>
          </div>
          {searchState.intent.clarification_required && (
            <div className="mt-4 flex flex-wrap gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3">
              <div className="min-w-[220px] flex-1">
                <p className="text-sm font-semibold">추가 정보가 필요합니다</p>
                <p className="text-xs text-black/60">{searchState.intent.unresolved_information.join(' · ')}</p>
              </div>
              <input value={location} onChange={(event) => setLocation(event.target.value)} placeholder="검색할 위치" className="rounded-lg border border-black/15 px-3 py-2 text-sm" />
              <button onClick={() => void clarify()} disabled={!location.trim()} className="rounded-lg bg-black px-4 py-2 text-sm text-white disabled:opacity-40">위치 반영</button>
            </div>
          )}
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <CriterionEditor title="명시적 조건 및 추론 조건" items={criteria} onChange={(id, patch) => updateCriterion(id, patch, false)} onRemove={(id) => { setCriteriaEdited(true); setCriteria((items) => items.filter((item) => item.id !== id)); }} />
            <CriterionEditor title="제외 조건" items={exclusions} onChange={(id, patch) => updateCriterion(id, patch, true)} onRemove={(id) => { setCriteriaEdited(true); setExclusions((items) => items.filter((item) => item.id !== id)); }} />
          </div>
          {(criteriaEdited || exclusions.length > 0) && (
            <button onClick={() => void submitSearch()} disabled={busy} className="mt-4 rounded-full border border-black/20 px-4 py-2 text-sm font-semibold hover:bg-white disabled:opacity-40">
              수정한 조건으로 다시 검색
            </button>
          )}
        </section>
      )}

      {searchState?.errors?.map((item, index) => <p key={index} className="text-sm text-amber-700">{item}</p>)}
      {searchState && searchState.excluded_result_count ? <p className="text-sm text-black/55">필수 조건 위반으로 제외한 결과 {searchState.excluded_result_count}개</p> : null}

      <div className="space-y-4">
        {results.map((result) => (
          <article key={result.document.document_id} className="rounded-3xl border border-black/10 bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-xs text-black/50">
                  <span>#{result.rank}</span>
                  <span>·</span>
                  <span>{result.document.source}</span>
                  <span className={result.verified ? 'rounded-full bg-emerald-50 px-2 py-0.5 text-emerald-800' : 'rounded-full bg-amber-50 px-2 py-0.5 text-amber-800'}>{result.verified ? '근거 확인됨' : '확인 필요'}</span>
                </div>
                <h3 className="mt-2 text-xl font-bold">
                  <a href={result.document.canonical_url} target="_blank" rel="noreferrer" className="underline decoration-black/20 underline-offset-4 hover:decoration-black">{result.document.title || result.document.canonical_url}</a>
                </h3>
              </div>
              <span className="rounded-full bg-stone-100 px-3 py-1 text-xs">검색 점수 {result.score.toFixed(2)}</span>
            </div>
            <p className="mt-3 text-sm leading-6 text-black/70">{result.document.snippet || result.document.content.slice(0, 280)}</p>
            <p className="mt-2 text-sm"><strong>추천 이유:</strong> {result.reason}</p>
            {result.evaluations.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {result.evaluations.map((item) => (
                  <span key={item.criterion_id} className={item.status === 'satisfied' ? 'rounded-full bg-emerald-50 px-3 py-1 text-xs text-emerald-800' : item.status === 'violated' ? 'rounded-full bg-red-50 px-3 py-1 text-xs text-red-800' : 'rounded-full bg-amber-50 px-3 py-1 text-xs text-amber-800'}>
                    {item.status === 'satisfied' ? '충족' : item.status === 'violated' ? '위반' : '확인 안 됨'}
                    {item.evidence_excerpt ? ' · ' + item.evidence_excerpt : ''}
                  </span>
                ))}
              </div>
            )}
            <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-black/10 pt-3">
              <button onClick={() => void sendFeedback(result, 'RESULT_LIKE')} className="rounded-full border border-black/10 px-3 py-1.5 text-xs hover:bg-black/5">좋아요</button>
              <button onClick={() => void sendFeedback(result, 'RESULT_DISLIKE')} className="rounded-full border border-black/10 px-3 py-1.5 text-xs hover:bg-black/5">싫어요</button>
              <button onClick={() => void sendFeedback(result, 'RESULT_SAVE')} className="rounded-full border border-black/10 px-3 py-1.5 text-xs hover:bg-black/5">저장</button>
              <button onClick={() => void sendFeedback(result, 'RESULT_DISMISS')} className="rounded-full border border-black/10 px-3 py-1.5 text-xs hover:bg-black/5">제외</button>
              <select aria-label="피드백 이유" value={feedbackReason} onChange={(event) => setFeedbackReason(event.target.value)} className="max-w-[220px] rounded-full border border-black/10 bg-white px-3 py-1.5 text-xs">
                {FEEDBACK_REASONS.map((reason) => <option key={reason}>{reason}</option>)}
              </select>
              <select aria-label="피드백 적용 범위" value={feedbackScope} onChange={(event) => setFeedbackScope(event.target.value as 'session' | 'related_searches')} className="rounded-full border border-black/10 bg-white px-3 py-1.5 text-xs">
                <option value="session">이번 검색에만</option>
                <option value="related_searches">관련 검색에 반영</option>
              </select>
            </div>
          </article>
        ))}
        {searchState && !busy && results.length === 0 && searchState.status !== 'clarification_required' && (
          <div className="rounded-3xl border border-dashed border-black/20 p-10 text-center">
            <h2 className="font-bold">조건에 맞는 결과를 찾지 못했습니다.</h2>
            <p className="mt-2 text-sm text-black/55">필수 조건을 완화하거나 검색어를 바꾸어 다시 시도해 보세요.</p>
          </div>
        )}
      </div>
    </div>
  );
}

function CriterionEditor({
  title,
  items,
  onChange,
  onRemove,
}: {
  title: string;
  items: Criterion[];
  onChange: (id: string, patch: Partial<Criterion>) => void;
  onRemove: (id: string) => void;
}) {
  return (
    <div className="rounded-2xl border border-black/10 bg-white p-4">
      <h3 className="text-sm font-bold">{title}</h3>
      {items.length === 0 && <p className="mt-2 text-xs text-black/45">표시할 조건이 없습니다.</p>}
      <div className="mt-2 space-y-2">
        {items.map((item) => (
          <div key={item.id} className="rounded-xl bg-stone-50 p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[11px] text-black/50">{item.source === 'explicit' ? '명시적' : item.source === 'user_memory' ? '사용자 선호' : '추론'} · {item.attribute}</span>
              <button onClick={() => onRemove(item.id)} className="text-xs text-red-700">삭제</button>
            </div>
            <input
              value={Array.isArray(item.value) ? item.value.join(', ') : String(item.value)}
              onChange={(event) => onChange(item.id, { value: event.target.value })}
              aria-label={item.attribute + ' 조건'}
              className="mt-1 w-full rounded-lg border border-black/10 bg-white px-2 py-1.5 text-sm"
            />
            <label className="mt-2 inline-flex items-center gap-2 text-xs">
              <input type="checkbox" checked={item.is_hard_constraint} onChange={(event) => onChange(item.id, { is_hard_constraint: event.target.checked })} className="accent-black" />
              필수 조건
            </label>
          </div>
        ))}
      </div>
    </div>
  );
}
