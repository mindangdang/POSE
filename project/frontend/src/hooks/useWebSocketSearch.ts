import { useEffect } from 'react';
import type { AppUser } from '../types/user';
import type { SavedItem } from '../types/item';

type UseWebSocketSearchProps = {
  user: AppUser | null;
  onSearchSuccess: (newResults: SavedItem[], isAppend: boolean) => void;
  onSearchFinished: () => void;
  onSearchError: (message: string) => void;
};

export function useWebSocketSearch({
  user,
  onSearchSuccess,
  onSearchFinished,
  onSearchError,
}: UseWebSocketSearchProps) {
  useEffect(() => {
    if (!user) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws/${user.id}`;
    let ws: WebSocket | null = null;

    try {
      ws = new WebSocket(wsUrl);
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "SEARCH_SUCCESS") {
            onSearchSuccess(data.results || [], data.is_append);
          } else if (data.type === "SEARCH_FINISHED") {
            onSearchFinished();
          } else if (data.type === "SEARCH_ERROR") {
            onSearchError(data.message || "검색 중 오류가 발생했습니다.");
          }
        } catch (err) {
          console.error("웹소켓 메시지 파싱 오류:", err);
        }
      };
      ws.onerror = (event) => console.error("웹소켓 연결 오류:", event);
    } catch (err) {
      console.error("웹소켓 연결 설정 오류:", err);
    }

    return () => { if (ws) ws.close(); };
  }, [user, onSearchSuccess, onSearchFinished, onSearchError]);
}