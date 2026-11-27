import '@testing-library/jest-dom/vitest';

class TestWebSocket {
  onmessage: ((event: MessageEvent) => void) | null = null;
  close() {}
}

Object.defineProperty(window, 'WebSocket', {
  configurable: true,
  value: TestWebSocket,
});
