import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { GenericSearchPage } from './GenericSearchPage';

const result = {
  document: {
    document_id: 'quiet-cafe',
    canonical_url: 'https://example.org/quiet-cafe',
    title: 'Quiet study cafe',
    snippet: 'Quiet seating and power outlets.',
    content: 'Quiet seating and power outlets.',
    source: 'fixture',
    metadata: {},
  },
  rank: 1,
  score: 0.82,
  verified: true,
  reason: 'The page supports the requested features.',
  satisfied_criteria: [],
  uncertain_criteria: [],
  evaluations: [],
};

const completedSearch = {
  search_id: 'search-123',
  status: 'completed',
  intent: {
    objective: 'Find a quiet study cafe',
    rewritten_query: 'quiet study cafe',
    criteria: [],
    exclusions: [],
    unresolved_information: [],
    clarification_required: false,
  },
  preferences_used: [],
  verified_results: [result],
  unverified_results: [],
  excluded_result_count: 0,
  errors: [],
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe('GenericSearchPage', () => {
  it('submits a generic search, shows evidence status, and sends feedback', async () => {
    const requests: Array<{ url: string; method: string; body?: Record<string, unknown> }> = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? 'GET';
      const body = init?.body ? JSON.parse(String(init.body)) as Record<string, unknown> : undefined;
      requests.push({ url, method, body });
      if (url.endsWith('/api/v2/search') && method === 'POST') {
        return jsonResponse({ search_id: 'search-123', status: 'queued' });
      }
      if (url.endsWith('/api/v2/search/search-123')) return jsonResponse(completedSearch);
      if (url.endsWith('/api/v2/feedback')) return jsonResponse({ status: 'success', updated_preferences: 0 });
      return jsonResponse([]);
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<GenericSearchPage onUseLegacy={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('검색어'), { target: { value: 'quiet study cafe' } });
    fireEvent.click(screen.getByRole('checkbox', { name: '내 선호 반영' }));
    fireEvent.click(screen.getByRole('button', { name: '검색' }));

    expect(await screen.findByRole('heading', { name: 'Quiet study cafe' })).toBeInTheDocument();
    expect(screen.getByText('근거 확인됨')).toBeInTheDocument();
    const searchRequest = requests.find((item) => item.url.endsWith('/api/v2/search') && item.method === 'POST');
    expect(searchRequest?.body).toMatchObject({ query: 'quiet study cafe', personalization_enabled: false });

    fireEvent.click(screen.getByRole('button', { name: '좋아요' }));
    expect(await screen.findByRole('status')).toHaveTextContent('피드백을 저장했습니다.');
    await waitFor(() => expect(requests.some((item) => item.url.endsWith('/api/v2/feedback'))).toBe(true));
  });

  it('shows a search error returned by the API', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ detail: 'Search unavailable' }, 503));
    vi.stubGlobal('fetch', fetchMock);

    render(<GenericSearchPage onUseLegacy={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('검색어'), { target: { value: 'search query' } });
    fireEvent.click(screen.getByRole('button', { name: '검색' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Search unavailable');
  });
});
