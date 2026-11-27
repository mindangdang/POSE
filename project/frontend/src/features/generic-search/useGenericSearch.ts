import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent } from 'react';

import {
  cancelSearch as cancelSearchRequest,
  clarifySearch as clarifySearchRequest,
  createPreference as createPreferenceRequest,
  createSearch,
  deletePreference as deletePreferenceRequest,
  getSearchState,
  listPreferences,
  openSearchSocket,
  sendResultFeedback,
  updatePreference as updatePreferenceRequest,
} from './api';
import { FEEDBACK_REASONS } from './types';
import type { Criterion, Preference, Result, SearchState } from './types';

function errorMessage(cause: unknown, fallback: string): string {
  return cause instanceof Error ? cause.message : fallback;
}

export function useGenericSearch() {
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
  const generation = useRef(0);
  const activeSearch = useRef<string | null>(null);
  const results = useMemo(
    () => [...(searchState?.verified_results ?? []), ...(searchState?.unverified_results ?? [])],
    [searchState],
  );

  const loadPreferences = useCallback(async () => {
    try {
      const items = await listPreferences();
      setPreferences(items);
    } catch (cause) {
      setError(errorMessage(cause, '선호를 불러오지 못했습니다.'));
    }
  }, []);

  const pollSearch = useCallback(async (id: string) => {
    const requestGeneration = generation.current;
    try {
      const state = await getSearchState(id);
      if (generation.current !== requestGeneration || activeSearch.current !== id) return;
      setSearchState(state);
      if (state.intent && loadedIntentFor.current !== id) {
        setCriteria(state.intent.criteria);
        setExclusions(state.intent.exclusions);
        loadedIntentFor.current = id;
      }
      if (['completed', 'partial', 'failed', 'cancelled', 'clarification_required'].includes(state.status)) {
        setBusy(false);
        if (timer.current !== undefined) window.clearInterval(timer.current);
        timer.current = undefined;
      }
    } catch (cause) {
      if (generation.current !== requestGeneration || activeSearch.current !== id) return;
      setBusy(false);
      setError(errorMessage(cause, '검색 상태를 불러오지 못했습니다.'));
    }
  }, []);

  useEffect(() => {
    if (!searchId) return;
    let socketConnected = false;
    let disposed = false;
    const stopPolling = () => {
      if (timer.current !== undefined) window.clearInterval(timer.current);
      timer.current = undefined;
    };
    const startPolling = () => {
      if (!disposed && !socketConnected && timer.current === undefined) {
        timer.current = window.setInterval(() => void pollSearch(searchId), 1200);
      }
    };
    void pollSearch(searchId);
    const socket = openSearchSocket(searchId, (event) => {
      try {
        const data = JSON.parse(event.data) as { type?: string; search_id?: string };
        if (data.search_id === searchId && data.type && activeSearch.current === searchId) {
          setEvents((current) => [...current.slice(-5), data.type!]);
          void pollSearch(searchId);
        }
      } catch {
        // GET polling remains the recovery path if a socket frame is malformed.
      }
    });
    if (socket) {
      socket.addEventListener('open', () => {
        socketConnected = true;
        stopPolling();
      });
      socket.addEventListener('close', () => {
        socketConnected = false;
        startPolling();
      });
      socket.addEventListener('error', () => startPolling());
    } else {
      startPolling();
    }
    return () => {
      disposed = true;
      stopPolling();
      socket?.close();
    };
  }, [searchId, pollSearch]);

  useEffect(() => {
    if (showPreferences) void loadPreferences();
  }, [showPreferences, loadPreferences]);

  const submitSearch = useCallback(async (event?: FormEvent) => {
    event?.preventDefault();
    if (!query.trim()) return;
    const requestGeneration = ++generation.current;
    activeSearch.current = null;
    setError('');
    setFeedbackNotice('');
    setBusy(true);
    setSearchState(null);
    setSearchId(null);
    loadedIntentFor.current = null;
    setEvents([]);
    try {
      const created = await createSearch({
        query: query.trim(),
        personalizationEnabled: personalization,
        sessionId,
        location: location.trim() || undefined,
        overrides: criteriaEdited ? { criteria, exclusions } : undefined,
      });
      if (generation.current !== requestGeneration) return;
      activeSearch.current = created.search_id;
      setSearchId(created.search_id);
      setCriteriaEdited(false);
    } catch (cause) {
      if (generation.current !== requestGeneration) return;
      setBusy(false);
      setError(errorMessage(cause, '검색을 시작하지 못했습니다.'));
    }
  }, [query, sessionId, location, criteriaEdited, criteria, exclusions, personalization]);

  const cancelSearch = async () => {
    if (!searchId) return;
    try {
      await cancelSearchRequest(searchId);
      setBusy(false);
      if (timer.current !== undefined) window.clearInterval(timer.current);
      timer.current = undefined;
      await pollSearch(searchId);
    } catch (cause) {
      setError(errorMessage(cause, '검색을 취소하지 못했습니다.'));
    }
  };

  const sendFeedback = async (result: Result, type: 'RESULT_LIKE' | 'RESULT_DISLIKE' | 'RESULT_SAVE' | 'RESULT_DISMISS') => {
    if (!searchId) return;
    setFeedbackNotice('');
    try {
      await sendResultFeedback(searchId, result, type, feedbackReason, feedbackScope);
      setFeedbackNotice('피드백을 저장했습니다.');
    } catch (cause) {
      setError(errorMessage(cause, '피드백을 저장하지 못했습니다.'));
    }
  };

  const clarify = async () => {
    if (!searchId || !location.trim()) return;
    const requestGeneration = ++generation.current;
    activeSearch.current = null;
    setBusy(true);
    try {
      const created = await clarifySearchRequest(searchId, location.trim());
      if (generation.current !== requestGeneration) return;
      activeSearch.current = created.search_id;
      setSearchId(created.search_id);
      setSearchState(null);
    } catch (cause) {
      if (generation.current !== requestGeneration) return;
      setBusy(false);
      setError(errorMessage(cause, '추가 정보를 반영하지 못했습니다.'));
    }
  };

  const updateCriterion = (id: string, patch: Partial<Criterion>, isExclusion: boolean) => {
    setCriteriaEdited(true);
    const setter = isExclusion ? setExclusions : setCriteria;
    setter((current) => current.map((item) => item.id === id ? { ...item, ...patch } : item));
  };

  const removeCriterion = (id: string, isExclusion: boolean) => {
    setCriteriaEdited(true);
    const setter = isExclusion ? setExclusions : setCriteria;
    setter((items) => items.filter((item) => item.id !== id));
  };

  const addPreference = async (event: FormEvent) => {
    event.preventDefault();
    if (!newAttribute.trim() || !newValue.trim()) return;
    try {
      await createPreferenceRequest(newAttribute.trim(), newValue.trim());
      setNewAttribute('');
      setNewValue('');
      await loadPreferences();
    } catch (cause) {
      setError(errorMessage(cause, '선호를 저장하지 못했습니다.'));
    }
  };

  const updatePreference = async (preference: Preference, patch: Partial<Preference>) => {
    try {
      await updatePreferenceRequest(preference, patch);
      await loadPreferences();
    } catch (cause) {
      setError(errorMessage(cause, '선호를 수정하지 못했습니다.'));
    }
  };

  const deletePreference = async (preference: Preference) => {
    try {
      await deletePreferenceRequest(preference);
      await loadPreferences();
    } catch (cause) {
      setError(errorMessage(cause, '선호를 삭제하지 못했습니다.'));
    }
  };

  return {
    query, setQuery, personalization, setPersonalization, searchId, searchState,
    criteria, exclusions, criteriaEdited, location, setLocation, busy, error,
    feedbackReason, setFeedbackReason, feedbackScope, setFeedbackScope,
    feedbackNotice, showPreferences, setShowPreferences, preferences,
    newAttribute, setNewAttribute, newValue, setNewValue, events, results,
    loadPreferences, submitSearch, cancelSearch, sendFeedback, clarify,
    updateCriterion, removeCriterion, addPreference, updatePreference, deletePreference,
  };
}
