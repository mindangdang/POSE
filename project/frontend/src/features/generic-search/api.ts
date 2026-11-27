import { apiFetch, apiJson } from '../../lib/api';
import { getAccessToken } from '../../lib/token';
import type { Criterion, Preference, Result, SearchState } from './types';

export type SearchOverrides = {
  criteria?: Criterion[];
  exclusions?: Criterion[];
};

export async function listPreferences(): Promise<Preference[]> {
  return apiJson<Preference[]>('/api/v2/preferences');
}

export async function getSearchState(searchId: string): Promise<SearchState> {
  return apiJson<SearchState>('/api/v2/search/' + searchId);
}

export async function createSearch(input: {
  query: string;
  personalizationEnabled: boolean;
  sessionId: string;
  location?: string;
  overrides?: SearchOverrides;
}): Promise<{ search_id: string; status: string }> {
  const context: Record<string, unknown> = { session_id: input.sessionId };
  if (input.location) context.location = input.location;
  if (input.overrides) {
    context.criteria_overrides = input.overrides.criteria ?? [];
    context.exclusion_overrides = input.overrides.exclusions ?? [];
  }
  return apiJson('/api/v2/search', {
    method: 'POST',
    body: JSON.stringify({
      query: input.query,
      personalization_enabled: input.personalizationEnabled,
      limit: 10,
      context,
    }),
  });
}

export async function cancelSearch(searchId: string): Promise<void> {
  await apiJson('/api/v2/search/' + searchId + '/cancel', { method: 'POST' });
}

export async function clarifySearch(searchId: string, location: string): Promise<{ search_id: string }> {
  return apiJson('/api/v2/search/' + searchId + '/clarify', {
    method: 'POST',
    body: JSON.stringify({ answers: { location } }),
  });
}

export async function sendResultFeedback(
  searchId: string,
  result: Result,
  type: 'RESULT_LIKE' | 'RESULT_DISLIKE' | 'RESULT_SAVE' | 'RESULT_DISMISS',
  reason: string,
  scope: 'session' | 'related_searches',
): Promise<void> {
  await apiJson('/api/v2/feedback', {
    method: 'POST',
    body: JSON.stringify({
      idempotency_key: crypto.randomUUID(),
      search_id: searchId,
      document_id: result.document.document_id,
      original_rank: result.rank,
      feedback_type: type,
      feedback_reason: type === 'RESULT_DISLIKE' || type === 'RESULT_DISMISS' ? reason : null,
      feedback_scope: scope,
    }),
  });
}

export async function createPreference(attribute: string, value: string): Promise<void> {
  await apiJson('/api/v2/preferences', {
    method: 'POST',
    body: JSON.stringify({
      attribute,
      value,
      polarity: 'positive',
      weight: 0.7,
      confidence: 1,
      scope: 'global',
      source: 'explicit',
    }),
  });
}

export async function updatePreference(preference: Preference, patch: Partial<Preference>): Promise<void> {
  await apiJson('/api/v2/preferences/' + preference.id, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });
}

export async function deletePreference(preference: Preference): Promise<void> {
  const response = await apiFetch('/api/v2/preferences/' + preference.id, { method: 'DELETE' });
  if (!response.ok) throw new Error('선호를 삭제하지 못했습니다.');
}

export function openSearchSocket(searchId: string, onMessage: (event: MessageEvent<string>) => void): WebSocket | null {
  const token = getAccessToken();
  if (!token) return null;
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const socket = new WebSocket(
    protocol + '//' + window.location.host + '/api/v2/ws/' + searchId + '?token=' + encodeURIComponent(token),
  );
  socket.onmessage = onMessage;
  return socket;
}
