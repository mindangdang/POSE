from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, Request

from project.backend.search_engine.pipeline import SearchPipeline
from project.backend.search_engine.schemas import Preference, SearchRequest, SearchResponse


class SearchStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"
    CLARIFICATION_REQUIRED = "clarification_required"


TERMINAL_STATUSES = {
    SearchStatus.COMPLETED,
    SearchStatus.PARTIAL,
    SearchStatus.FAILED,
    SearchStatus.CANCELLED,
    SearchStatus.CLARIFICATION_REQUIRED,
}
ALLOWED_TRANSITIONS = {
    SearchStatus.QUEUED: {
        SearchStatus.RUNNING,
        SearchStatus.CANCELLED,
        SearchStatus.FAILED,
    },
    SearchStatus.RUNNING: TERMINAL_STATUSES,
}
TERMINAL_EVENTS = {
    "SEARCH_COMPLETED",
    "SEARCH_PARTIAL",
    "SEARCH_FAILED",
    "SEARCH_CANCELLED",
    "SEARCH_CLARIFICATION_REQUIRED",
}
SESSION_TTL = timedelta(hours=2)
MAX_RETAINED_SESSIONS = 500
MAX_RETAINED_EVENTS = 200


@dataclass
class SearchSession:
    search_id: str
    owner_id: str
    request: SearchRequest
    session_id: str = ""
    execution_id: str = field(default_factory=lambda: str(uuid4()))
    status: SearchStatus = SearchStatus.QUEUED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    events: list[dict[str, Any]] = field(default_factory=list)
    event_sequence: int = 0
    terminal_event_published: bool = False
    response: SearchResponse | None = None
    session_preferences: list[Preference] = field(default_factory=list)
    task: asyncio.Task | None = None
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    feedback_keys: set[str] = field(default_factory=set)


class SearchSessionRegistry:
    def __init__(
        self,
        *,
        ttl: timedelta = SESSION_TTL,
        max_sessions: int = MAX_RETAINED_SESSIONS,
    ) -> None:
        self.sessions: dict[str, SearchSession] = {}
        self.preferences: dict[str, list[Preference]] = {}
        self.preferences_loaded: set[str] = set()
        self.session_preferences: dict[tuple[str, str], list[Preference]] = {}
        self.session_preferences_loaded: set[tuple[str, str]] = set()
        self.session_preference_activity: dict[tuple[str, str], datetime] = {}
        self.feedback_keys: dict[tuple[str, str], datetime] = {}
        self.feedback_locks: dict[str, asyncio.Lock] = {}
        self.ttl = ttl
        self.max_sessions = max_sessions
        self._registry_lock = asyncio.Lock()

    def feedback_lock(self, owner_id: str) -> asyncio.Lock:
        return self.feedback_locks.setdefault(owner_id, asyncio.Lock())

    def has_feedback(self, key: tuple[str, str]) -> bool:
        now = datetime.now(timezone.utc)
        self.feedback_keys = {
            item: created_at
            for item, created_at in self.feedback_keys.items()
            if now - created_at <= self.ttl
        }
        return key in self.feedback_keys

    def remember_feedback(self, key: tuple[str, str]) -> None:
        self.feedback_keys[key] = datetime.now(timezone.utc)
        if len(self.feedback_keys) > 10_000:
            oldest = sorted(self.feedback_keys.items(), key=lambda item: item[1])
            for expired_key, _created_at in oldest[: len(self.feedback_keys) - 10_000]:
                self.feedback_keys.pop(expired_key, None)

    def touch_session_preferences(self, key: tuple[str, str]) -> None:
        now = datetime.now(timezone.utc)
        self.session_preference_activity[key] = now
        expired = [
            item
            for item, touched_at in self.session_preference_activity.items()
            if now - touched_at > self.ttl
        ]
        for item in expired:
            self.session_preference_activity.pop(item, None)
            self.session_preferences.pop(item, None)
            self.session_preferences_loaded.discard(item)
        overflow = len(self.session_preference_activity) - self.max_sessions
        if overflow > 0:
            oldest = sorted(self.session_preference_activity.items(), key=lambda item: item[1])
            for old_key, _touched_at in oldest[:overflow]:
                self.session_preference_activity.pop(old_key, None)
                self.session_preferences.pop(old_key, None)
                self.session_preferences_loaded.discard(old_key)

    def prune(self, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        expired = [
            key
            for key, session in self.sessions.items()
            if session.status in TERMINAL_STATUSES
            and now - session.last_activity_at > self.ttl
        ]
        for search_id in expired:
            self.sessions.pop(search_id, None)
        expired_feedback = [
            key
            for key, created_at in self.feedback_keys.items()
            if now - created_at > self.ttl
        ]
        for feedback_key in expired_feedback:
            self.feedback_keys.pop(feedback_key, None)
        expired_preference_keys = [
            key
            for key, touched_at in self.session_preference_activity.items()
            if now - touched_at > self.ttl
        ]
        for preference_key in expired_preference_keys:
            self.session_preference_activity.pop(preference_key, None)
            self.session_preferences.pop(preference_key, None)
            self.session_preferences_loaded.discard(preference_key)
        overflow = len(self.sessions) - self.max_sessions
        if overflow > 0:
            completed = sorted(
                (
                    session
                    for session in self.sessions.values()
                    if session.status in TERMINAL_STATUSES
                ),
                key=lambda session: session.last_activity_at,
            )
            for session in completed[:overflow]:
                self.sessions.pop(session.search_id, None)

    async def create(self, owner_id: str, request: SearchRequest) -> SearchSession:
        context_session_id = (
            request.context.session_id or request.session_id or str(uuid4())
        )
        context = request.context.model_copy(update={"session_id": context_session_id})
        request = request.model_copy(
            update={"session_id": context_session_id, "context": context}
        )
        async with self._registry_lock:
            self.prune()
            if len(self.sessions) >= self.max_sessions:
                raise HTTPException(status_code=503, detail="Search capacity is temporarily full")
            session = SearchSession(
                search_id=str(uuid4()),
                owner_id=owner_id,
                request=request,
                session_id=context_session_id,
            )
            self.sessions[session.search_id] = session
        await self.emit(session.search_id, "SEARCH_QUEUED", status="queued")
        return session

    async def _publish_locked(
        self, session: SearchSession, event_type: str, payload: dict[str, Any]
    ) -> bool:
        if event_type in TERMINAL_EVENTS and session.terminal_event_published:
            return False
        session.event_sequence += 1
        session.last_activity_at = datetime.now(timezone.utc)
        event = {
            **payload,
            "sequence": session.event_sequence,
            "search_id": session.search_id,
            "session_id": session.session_id,
            "execution_id": session.execution_id,
            "type": event_type,
            "timestamp": session.last_activity_at.isoformat(),
        }
        session.events.append(event)
        if len(session.events) > MAX_RETAINED_EVENTS:
            session.events = session.events[-MAX_RETAINED_EVENTS:]
        if event_type in TERMINAL_EVENTS:
            session.terminal_event_published = True
        session.condition.notify_all()
        return True

    async def emit(self, search_id: str, event_type: str, **payload: Any) -> None:
        if event_type in TERMINAL_EVENTS:
            return
        session = self.sessions.get(search_id)
        if session is None:
            return
        async with session.condition:
            await self._publish_locked(session, event_type, payload)

    async def transition(
        self,
        session: SearchSession,
        status: str,
        event_type: str,
        **payload: Any,
    ) -> bool:
        try:
            target = SearchStatus(status)
        except ValueError as exc:
            raise ValueError(f"Unknown search state: {status}") from exc
        current = SearchStatus(session.status)
        if target not in ALLOWED_TRANSITIONS.get(current, set()):
            if current == target and target in TERMINAL_STATUSES:
                return False
            if current in TERMINAL_STATUSES:
                return False
            raise ValueError(f"Invalid search state transition: {current.value} -> {target.value}")
        async with session.condition:
            current = SearchStatus(session.status)
            if target not in ALLOWED_TRANSITIONS.get(current, set()):
                return False
            session.status = target
            return await self._publish_locked(
                session, event_type, {**payload, "status": target.value}
            )

    def owned(self, search_id: str, owner_id: str) -> SearchSession:
        self.prune()
        session = self.sessions.get(search_id)
        if not session or session.owner_id != owner_id:
            raise HTTPException(status_code=404, detail="Search session not found")
        session.last_activity_at = datetime.now(timezone.utc)
        return session

    async def start(self, session: SearchSession, provider=None, session_factory=None) -> None:
        from project.backend.app.search.persistence import persist_preference, persist_search

        if not await self.transition(session, "running", "SEARCH_RUNNING"):
            return
        await persist_search(session_factory, session)

        async def run_search() -> None:
            async def emit(event: dict[str, Any]) -> None:
                item = dict(event)
                event_type = item.pop("type", "SEARCH_PROGRESS")
                item.pop("search_id", None)
                await self.emit(session.search_id, event_type, **item)

            repository = None
            if session_factory:
                from project.backend.app.repositories.search_cache import (
                    PostgresCachedDocumentRepository,
                )

                repository = PostgresCachedDocumentRepository(session_factory)
            pipeline = SearchPipeline(
                provider=provider,
                event_callback=emit,
                document_repository=repository,
            )
            try:
                preferences = [
                    *(
                        self.preferences.get(session.owner_id, [])
                        if session.request.personalization_enabled
                        else []
                    ),
                    *session.session_preferences,
                ]
                result = await pipeline.run(
                    session.request,
                    user_id=session.owner_id,
                    preferences=preferences,
                    search_id=session.execution_id,
                )
                session.response = result.model_copy(
                    update={
                        "search_id": session.search_id,
                        "execution_id": session.execution_id,
                        "session_id": session.session_id,
                    }
                )
                selected_ids = set(result.preferences_used)
                for preference in preferences:
                    if (
                        preference.id in selected_ids
                        and preference.scope.value != "session"
                        and preference.embedding is not None
                        and preference.embedding_space is not None
                    ):
                        await persist_preference(session_factory, preference, session.owner_id)
                target_status = result.status
                if target_status == "clarification_required":
                    terminal_event = "SEARCH_CLARIFICATION_REQUIRED"
                elif target_status == "partial":
                    terminal_event = "SEARCH_PARTIAL"
                else:
                    terminal_event = "SEARCH_COMPLETED"
                await self.transition(session, target_status, terminal_event)
                await persist_search(session_factory, session)
            except asyncio.CancelledError:
                session.response = SearchResponse(
                    search_id=session.search_id,
                    execution_id=session.execution_id,
                    session_id=session.session_id,
                    status="cancelled",
                    completed_at=datetime.now(timezone.utc),
                )
                await self.transition(session, "cancelled", "SEARCH_CANCELLED")
                await persist_search(session_factory, session)
                raise
            except Exception as exc:
                session.response = SearchResponse(
                    search_id=session.search_id,
                    execution_id=session.execution_id,
                    session_id=session.session_id,
                    status="failed",
                    errors=[type(exc).__name__],
                    completed_at=datetime.now(timezone.utc),
                )
                await self.transition(
                    session, "failed", "SEARCH_FAILED", error_code=type(exc).__name__
                )
                await persist_search(session_factory, session)

        session.task = asyncio.create_task(run_search(), name=f"pose-search-{session.execution_id}")


def get_registry(request: Request) -> SearchSessionRegistry:
    registry = getattr(request.app.state, "pose_search_registry", None)
    if registry is None:
        registry = SearchSessionRegistry()
        request.app.state.pose_search_registry = registry
    return registry
