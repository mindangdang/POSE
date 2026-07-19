import { apiFetch } from '../lib/api';

type EventProperties = Record<string, unknown>;

type AnalyticsEvent = {
  timestamp: string;
  event_name: string;
  session_id: string;
  user_id?: string | number | null;
  properties: EventProperties;
  page: string;
  user_agent: string;
};

const FLUSH_INTERVAL_MS = 1000;
const MAX_BATCH_SIZE = 20;
const MAX_QUEUE_SIZE = 200;

const eventQueue: AnalyticsEvent[] = [];
let userId: string | number | null = null;
let flushTimer: number | null = null;
let isFlushing = false;

function getSessionId() {
  const storageKey = 'pose.analytics.session_id';
  const existing = window.sessionStorage.getItem(storageKey);
  if (existing) return existing;

  const next = crypto.randomUUID();
  window.sessionStorage.setItem(storageKey, next);
  return next;
}

function getPage() {
  return `${window.location.pathname}${window.location.search}`;
}

export function setAnalyticsUser(nextUserId: string | number | null | undefined) {
  userId = nextUserId ?? null;
}

export function trackEvent(eventName: string, properties: EventProperties = {}) {
  eventQueue.push({
    timestamp: new Date().toISOString(),
    event_name: eventName,
    session_id: getSessionId(),
    user_id: userId,
    properties,
    page: getPage(),
    user_agent: navigator.userAgent,
  });

  if (eventQueue.length > MAX_QUEUE_SIZE) {
    eventQueue.splice(0, eventQueue.length - MAX_QUEUE_SIZE);
  }

  if (eventQueue.length >= MAX_BATCH_SIZE) {
    void flushEvents();
  }
}

export async function flushEvents() {
  if (isFlushing || eventQueue.length === 0) return;

  isFlushing = true;
  const events = eventQueue.splice(0, MAX_BATCH_SIZE);

  try {
    const res = await apiFetch('/api/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ events }),
      keepalive: events.length < 10,
    });

    if (!res.ok) {
      eventQueue.unshift(...events);
    }
  } catch (error) {
    eventQueue.unshift(...events);
    console.warn('이벤트 로그 전송 실패:', error);
  } finally {
    isFlushing = false;
  }
}

export function startAnalytics() {
  if (flushTimer !== null) return;
  flushTimer = window.setInterval(() => void flushEvents(), FLUSH_INTERVAL_MS);

  window.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') {
      void flushEvents();
    }
  });

  window.addEventListener('beforeunload', () => {
    void flushEvents();
  });
}
