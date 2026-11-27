import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { SearchState } from './types';

const apiMocks = vi.hoisted(() => ({
  cancelSearch: vi.fn(),
  clarifySearch: vi.fn(),
  createPreference: vi.fn(),
  createSearch: vi.fn(),
  deletePreference: vi.fn(),
  getSearchState: vi.fn(),
  listPreferences: vi.fn(),
  openSearchSocket: vi.fn(),
  sendResultFeedback: vi.fn(),
  updatePreference: vi.fn(),
}));

vi.mock('./api', () => ({
  cancelSearch: apiMocks.cancelSearch,
  clarifySearch: apiMocks.clarifySearch,
  createPreference: apiMocks.createPreference,
  createSearch: apiMocks.createSearch,
  deletePreference: apiMocks.deletePreference,
  getSearchState: apiMocks.getSearchState,
  listPreferences: apiMocks.listPreferences,
  openSearchSocket: apiMocks.openSearchSocket,
  sendResultFeedback: apiMocks.sendResultFeedback,
  updatePreference: apiMocks.updatePreference,
}));

import { useGenericSearch } from './useGenericSearch';

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
}

afterEach(() => {
  vi.clearAllMocks();
  vi.useRealTimers();
});

describe('useGenericSearch request lifecycle', () => {
  it('ignores a stale search response after a newer search starts', async () => {
    const staleResponse = deferred<SearchState>();
    apiMocks.createSearch
      .mockResolvedValueOnce({ search_id: 'old-search', status: 'queued' })
      .mockResolvedValueOnce({ search_id: 'new-search', status: 'queued' });
    apiMocks.getSearchState.mockImplementation((id: string) => (
      id === 'old-search'
        ? staleResponse.promise
        : Promise.resolve({ search_id: id, status: 'completed' } satisfies SearchState)
    ));
    apiMocks.openSearchSocket.mockReturnValue(null);

    const { result } = renderHook(() => useGenericSearch());
    act(() => result.current.setQuery('first query'));
    await act(async () => { await result.current.submitSearch(); });
    await waitFor(() => expect(apiMocks.getSearchState).toHaveBeenCalledWith('old-search'));

    act(() => result.current.setQuery('second query'));
    await act(async () => { await result.current.submitSearch(); });
    await waitFor(() => expect(result.current.searchState?.search_id).toBe('new-search'));

    await act(async () => {
      staleResponse.resolve({ search_id: 'old-search', status: 'completed' });
      await staleResponse.promise;
    });
    expect(result.current.searchState?.search_id).toBe('new-search');
  });

  it('stops polling while the WebSocket is connected', async () => {
    vi.useFakeTimers();
    const listeners: Record<string, EventListener> = {};
    const socket = {
      addEventListener: (type: string, listener: EventListener) => { listeners[type] = listener; },
      close: vi.fn(),
    };
    apiMocks.createSearch.mockResolvedValue({ search_id: 'live-search', status: 'queued' });
    apiMocks.getSearchState.mockResolvedValue({ search_id: 'live-search', status: 'running' });
    apiMocks.openSearchSocket.mockReturnValue(socket);

    const { result } = renderHook(() => useGenericSearch());
    act(() => result.current.setQuery('live query'));
    await act(async () => {
      await result.current.submitSearch();
      await Promise.resolve();
    });
    expect(apiMocks.getSearchState).toHaveBeenCalledTimes(1);
    act(() => listeners.open(new Event('open')));
    await act(async () => { await vi.advanceTimersByTimeAsync(3600); });
    expect(apiMocks.getSearchState).toHaveBeenCalledTimes(1);
  });
});
