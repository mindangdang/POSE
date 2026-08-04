import { apiFetch } from './api';

export type UserEventAction =
  | 'SEARCH'
  | 'LIKE'
  | 'DISLIKE'
  | 'SAVE_WISHLIST'
  | 'REMOVE_WISHLIST'
  | 'CLICK_PURCHASE'
  | 'CLICK_ITEM'
  | 'VOTE_PRETTY'
  | 'VOTE_UGLY';

export type UserEventEntityType = 'SEARCH_RESULT' | 'VOTING_ITEM' | 'WISHLIST_ITEM' | 'SITE';

type TrackEventInput = {
  action: UserEventAction;
  entityType: UserEventEntityType;
  entityId?: string | number | null;
  metadata?: Record<string, unknown>;
};

export async function trackEvent({ action, entityType, entityId = null, metadata = {} }: TrackEventInput) {
  try {
    await apiFetch('/api/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action,
        entity_type: entityType,
        entity_id: entityId == null ? null : String(entityId),
        metadata,
        timestamp: new Date().toISOString(),
      }),
      keepalive: true,
    });
  } catch (error) {
    console.error('Failed to track event:', error);
  }
}
