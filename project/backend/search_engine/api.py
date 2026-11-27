from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict
from starlette import status

from project.backend.app.api.dependencies import get_current_user
from project.backend.app.manage.settings import get_settings
from project.backend.app.db.models.search import (
    Document as DocumentRow,
    SearchFeedback as FeedbackRow,
    SearchImpression as ImpressionRow,
    SearchSession as SessionRow,
    SearchTrace as TraceRow,
    UserPreference as PreferenceRow,
)
from project.backend.search_engine.pipeline import SearchPipeline
from project.backend.search_engine.schemas import FeedbackType, Preference, SearchFeedback, SearchRequest, SearchResponse


class PreferencePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str | None = None
    polarity: str | None = None
    weight: float | None = None
    confidence: float | None = None
    scope: str | None = None
    domain: str | None = None
    source: str | None = None


class ClarificationRequest(BaseModel):
    answers: dict[str, Any]


@dataclass
class SearchSession:
    search_id: str
    owner_id: str
    request: SearchRequest
    status: str = "queued"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    events: list[dict[str, Any]] = field(default_factory=list)
    response: SearchResponse | None = None
    session_preferences: list[Preference] = field(default_factory=list)
    task: asyncio.Task | None = None
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)
    feedback_keys: set[str] = field(default_factory=set)


class SearchSessionRegistry:
    def __init__(self) -> None:
        self.sessions: dict[str, SearchSession] = {}
        self.preferences: dict[str, list[Preference]] = {}
        self.preferences_loaded: set[str] = set()

    async def create(self, owner_id: str, request: SearchRequest) -> SearchSession:
        session = SearchSession(search_id=str(uuid4()), owner_id=owner_id, request=request)
        self.sessions[session.search_id] = session
        await self.emit(session.search_id, "SEARCH_STARTED", status="queued")
        return session

    async def emit(self, search_id: str, event_type: str, **payload: Any) -> None:
        session = self.sessions.get(search_id)
        if not session:
            return
        event = {
            "sequence": len(session.events) + 1,
            "search_id": search_id,
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        async with session.condition:
            session.events.append(event)
            if len(session.events) > 200:
                session.events = session.events[-200:]
            session.condition.notify_all()

    def owned(self, search_id: str, owner_id: str) -> SearchSession:
        session = self.sessions.get(search_id)
        if not session or session.owner_id != owner_id:
            raise HTTPException(status_code=404, detail="Search session not found")
        return session

    async def start(self, session: SearchSession, provider=None, session_factory=None) -> None:
        session.status = "running"
        await self.emit(session.search_id, "SEARCH_STARTED", status="running")
        await persist_search(session_factory, session)

        async def run_search() -> None:
            async def emit(event: dict[str, Any]) -> None:
                await self.emit(session.search_id, event.pop("type"), **event)

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
                    search_id=session.search_id,
                )
                session.response = result
                session.status = result.status
                await persist_search(session_factory, session)
                await self.emit(session.search_id, "SEARCH_PARTIAL" if result.status == "partial" else "SEARCH_COMPLETED", status=result.status)
            except asyncio.CancelledError:
                session.status = "cancelled"
                session.response = SearchResponse(
                    search_id=session.search_id,
                    status="cancelled",
                    completed_at=datetime.now(timezone.utc),
                )
                await persist_search(session_factory, session)
                await self.emit(session.search_id, "SEARCH_CANCELLED", status="cancelled")
                raise
            except Exception as exc:
                session.status = "failed"
                session.response = SearchResponse(
                    search_id=session.search_id,
                    status="failed",
                    errors=[type(exc).__name__],
                    completed_at=datetime.now(timezone.utc),
                )
                await persist_search(session_factory, session)
                await self.emit(session.search_id, "SEARCH_FAILED", error_code=type(exc).__name__)

        session.task = asyncio.create_task(run_search(), name=f"pose-search-{session.search_id}")


def get_registry(request: Request) -> SearchSessionRegistry:
    registry = getattr(request.app.state, "pose_search_registry", None)
    if registry is None:
        registry = SearchSessionRegistry()
        request.app.state.pose_search_registry = registry
    return registry


def _session_factory(request: Request):
    return getattr(request.app.state, "db_session_factory", None)


async def load_preferences(registry: SearchSessionRegistry, owner_id: str, session_factory) -> list[Preference]:
    if owner_id not in registry.preferences_loaded:
        if session_factory:
            from sqlalchemy import select

            async with session_factory() as db:
                rows = (
                    await db.execute(
                        select(PreferenceRow).where(
                            PreferenceRow.user_id == int(owner_id),
                            PreferenceRow.active.is_(True),
                        )
                    )
                ).scalars().all()
            registry.preferences[owner_id] = [
                Preference(
                    id=row.id,
                    user_id=owner_id,
                    attribute=row.attribute,
                    value=row.value,
                    polarity=row.polarity,
                    weight=row.weight,
                    confidence=row.confidence,
                    scope=row.scope,
                    domain=row.domain,
                    source=row.source,
                    evidence_event_ids=row.evidence_event_ids,
                    embedding=row.embedding,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
                for row in rows
            ]
        registry.preferences_loaded.add(owner_id)
    return registry.preferences.setdefault(owner_id, [])


async def persist_search(session_factory, session: SearchSession) -> None:
    if not session_factory:
        return
    async with session_factory() as db:
        row = await db.get(SessionRow, session.search_id)
        request_json = session.request.model_dump(mode="json")
        if row is None:
            row = SessionRow(
                search_id=session.search_id,
                user_id=int(session.owner_id),
                status=session.status,
                query=session.request.query,
                request_json=request_json,
            )
            db.add(row)
        else:
            row.status = session.status
            row.request_json = request_json
            row.response_json = session.response.model_dump(mode="json") if session.response else None
            row.updated_at = datetime.now(timezone.utc)
        if session.response:
            row.response_json = session.response.model_dump(mode="json")
            response = session.response
            results = [*response.verified_results, *response.unverified_results]
            for result in results:
                from sqlalchemy import select

                if await db.get(DocumentRow, result.document.document_id) is None:
                    db.add(
                        DocumentRow(
                            document_id=result.document.document_id,
                            canonical_url=result.document.canonical_url,
                            source_url=result.document.source_url,
                            title=result.document.title,
                            snippet=result.document.snippet,
                            content=result.document.content,
                            source=result.document.source,
                            document_type=result.document.document_type,
                            published_at=result.document.published_at,
                            fetched_at=result.document.fetched_at,
                            metadata_json=result.document.metadata,
                        )
                    )
                existing_impression = (
                    await db.execute(
                        select(ImpressionRow.id).where(
                            ImpressionRow.search_id == session.search_id,
                            ImpressionRow.document_id == result.document.document_id,
                        )
                    )
                ).first()
                if not existing_impression:
                    db.add(
                        ImpressionRow(
                            search_id=session.search_id,
                            user_id=int(session.owner_id),
                            document_id=result.document.document_id,
                            original_rank=result.rank,
                        )
                    )
            db.add(
                TraceRow(
                    search_id=session.search_id,
                    trace_id=str(uuid4()),
                    trace_json=[
                        {"type": event["type"], "sequence": event["sequence"]}
                        for event in session.events
                    ],
                )
            )
        await db.commit()


async def persist_preference(session_factory, preference: Preference, owner_id: str) -> None:
    if not session_factory:
        return
    async with session_factory() as db:
        row = await db.get(PreferenceRow, preference.id)
        values = preference.model_dump(exclude={"user_id", "id", "created_at", "updated_at"})
        if row is None:
            row = PreferenceRow(id=preference.id, user_id=int(owner_id), **values)
            db.add(row)
        else:
            for key, value in values.items():
                setattr(row, key, value)
            row.updated_at = datetime.now(timezone.utc)
        await db.commit()


async def owned_session(
    request: Request,
    registry: SearchSessionRegistry,
    search_id: str,
    owner_id: str,
) -> SearchSession:
    session = registry.sessions.get(search_id)
    if session:
        return registry.owned(search_id, owner_id)
    if not _session_factory(request):
        return registry.owned(search_id, owner_id)
    from sqlalchemy import select

    async with _session_factory(request)() as db:
        row = (
            await db.execute(
                select(SessionRow).where(
                    SessionRow.search_id == search_id,
                    SessionRow.user_id == int(owner_id),
                )
            )
        ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Search session not found")
    session = SearchSession(
        search_id=row.search_id,
        owner_id=owner_id,
        request=SearchRequest.model_validate(row.request_json),
        status=row.status,
    )
    if row.response_json:
        session.response = SearchResponse.model_validate(row.response_json)
    registry.sessions[search_id] = session
    return session


router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "pose-search-v2"}


@router.post("/search", status_code=status.HTTP_202_ACCEPTED)
async def start_search(
    payload: SearchRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    owner_id = str(current_user["sub"])
    registry = get_registry(request)
    session = await registry.create(owner_id, payload)
    if payload.personalization_enabled:
        await load_preferences(registry, owner_id, _session_factory(request))
    await persist_search(_session_factory(request), session)
    await registry.start(
        session,
        getattr(request.app.state, "pose_search_provider", None),
        _session_factory(request),
    )
    return {"search_id": session.search_id, "status": session.status}


@router.get("/search/{search_id}")
async def get_search(
    search_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    registry = get_registry(request)
    owner_id = str(current_user["sub"])
    session = await owned_session(request, registry, search_id, owner_id)
    if session.response is not None:
        return session.response.model_dump(mode="json")
    return {
        "search_id": session.search_id,
        "status": session.status,
        "created_at": session.created_at.isoformat(),
        "events": session.events,
    }


@router.post("/search/{search_id}/clarify", status_code=status.HTTP_202_ACCEPTED)
async def clarify_search(
    search_id: str,
    payload: ClarificationRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    registry = get_registry(request)
    old = await owned_session(request, registry, search_id, str(current_user["sub"]))
    if old.status != "clarification_required":
        raise HTTPException(status_code=409, detail="This search does not need clarification")
    context = old.request.context.model_dump()
    context.update(payload.answers)
    new_request = old.request.model_copy(update={"context": old.request.context.model_validate(context)})
    session = await registry.create(old.owner_id, new_request)
    await persist_search(_session_factory(request), session)
    await registry.start(
        session,
        getattr(request.app.state, "pose_search_provider", None),
        _session_factory(request),
    )
    return {"search_id": session.search_id, "status": session.status}


@router.post("/search/{search_id}/cancel")
async def cancel_search(
    search_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    session = await owned_session(request, get_registry(request), search_id, str(current_user["sub"]))
    if session.task and not session.task.done():
        session.task.cancel()
    else:
        session.status = "cancelled"
        await get_registry(request).emit(search_id, "SEARCH_CANCELLED", status="cancelled")
    return {"search_id": search_id, "status": "cancelled"}


@router.post("/feedback")
async def add_feedback(
    payload: SearchFeedback,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    registry = get_registry(request)
    session = await owned_session(request, registry, payload.search_id, str(current_user["sub"]))
    if payload.idempotency_key in session.feedback_keys:
        return {"status": "duplicate", "updated_preferences": 0}
    if not session.response:
        raise HTTPException(status_code=409, detail="Search results are not available yet")
    exposed = {
        result.document.document_id
        for result in [*session.response.verified_results, *session.response.unverified_results]
    }
    if payload.document_id and payload.document_id not in exposed:
        raise HTTPException(status_code=400, detail="Feedback must reference an exposed result")
    session_factory = _session_factory(request)
    updated = 0
    preference_to_store: Preference | None = None
    if payload.feedback_type == FeedbackType.PREFERENCE_UPDATE and payload.preference:
        preference = payload.preference.model_copy(update={"user_id": session.owner_id})
        if payload.feedback_scope == "session":
            preference = preference.model_copy(
                update={"scope": "session", "session_id": session.search_id}
            )
            session.session_preferences.append(preference)
        else:
            user_preferences = await load_preferences(registry, session.owner_id, session_factory)
            if not any(item.id == preference.id for item in user_preferences):
                preference = preference.model_copy(update={"id": str(uuid4())})
            preference_to_store = preference
        updated = 1
    if session_factory:
        from sqlalchemy import select

        async with session_factory() as db:
            previous = (
                await db.execute(
                    select(FeedbackRow.id).where(
                        FeedbackRow.user_id == int(session.owner_id),
                        FeedbackRow.idempotency_key == payload.idempotency_key,
                    )
                )
            ).first()
            if previous:
                return {"status": "duplicate", "updated_preferences": 0}
            db.add(FeedbackRow(
                user_id=int(session.owner_id),
                search_id=payload.search_id,
                document_id=payload.document_id,
                original_rank=payload.original_rank,
                idempotency_key=payload.idempotency_key,
                feedback_type=payload.feedback_type.value,
                feedback_reason=payload.feedback_reason,
                affected_criterion=payload.affected_criterion,
                feedback_scope=payload.feedback_scope,
                feedback_json=payload.model_dump(mode="json"),
            ))
            if preference_to_store:
                preference_row = await db.get(PreferenceRow, preference_to_store.id)
                values = preference_to_store.model_dump(
                    exclude={"user_id", "id", "created_at", "updated_at"}
                )
                if preference_row is None:
                    db.add(
                        PreferenceRow(
                            id=preference_to_store.id,
                            user_id=int(session.owner_id),
                            **values,
                        )
                    )
                elif preference_row.user_id != int(session.owner_id):
                    raise HTTPException(status_code=404, detail="Preference not found")
                else:
                    for key, value in values.items():
                        setattr(preference_row, key, value)
                    preference_row.updated_at = datetime.now(timezone.utc)
            await db.commit()
    session.feedback_keys.add(payload.idempotency_key)
    if preference_to_store:
        items = registry.preferences.setdefault(session.owner_id, [])
        index = next((i for i, item in enumerate(items) if item.id == preference_to_store.id), None)
        if index is None:
            items.append(preference_to_store)
        else:
            items[index] = preference_to_store
    await registry.emit(
        session.search_id,
        "FEEDBACK_RECORDED",
        feedback_type=payload.feedback_type.value,
        document_id=payload.document_id,
    )
    return {"status": "success", "updated_preferences": updated}


@router.get("/preferences")
async def list_preferences(
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    owner_id = str(current_user["sub"])
    return [
        item.model_dump(mode="json")
        for item in await load_preferences(get_registry(request), owner_id, _session_factory(request))
    ]


@router.post("/preferences", status_code=status.HTTP_201_CREATED)
async def create_preference(
    payload: Preference,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    registry = get_registry(request)
    owner_id = str(current_user["sub"])
    await load_preferences(registry, owner_id, _session_factory(request))
    if payload.scope.value == "session":
        raise HTTPException(status_code=400, detail="Session preferences belong to a search session")
    preference = payload.model_copy(update={"id": str(uuid4()), "user_id": owner_id})
    items = registry.preferences.setdefault(owner_id, [])
    items.append(preference)
    await persist_preference(_session_factory(request), preference, owner_id)
    return preference.model_dump(mode="json")


@router.patch("/preferences/{preference_id}")
async def update_preference(
    preference_id: str,
    payload: PreferencePatch,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    owner_id = str(current_user["sub"])
    items = await load_preferences(get_registry(request), owner_id, _session_factory(request))
    index = next((i for i, item in enumerate(items) if item.id == preference_id), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Preference not found")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("scope") == "session":
        raise HTTPException(status_code=400, detail="Session preferences belong to a search session")
    updated = items[index].model_copy(update=changes)
    # Round-trip validation ensures enum/range constraints also apply to patches.
    updated = Preference.model_validate(updated.model_dump())
    items[index] = updated
    await persist_preference(_session_factory(request), updated, owner_id)
    return updated.model_dump(mode="json")


@router.delete("/preferences/{preference_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_preference(
    preference_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> None:
    owner_id = str(current_user["sub"])
    items = await load_preferences(get_registry(request), owner_id, _session_factory(request))
    filtered = [item for item in items if item.id != preference_id]
    if len(filtered) == len(items):
        raise HTTPException(status_code=404, detail="Preference not found")
    get_registry(request).preferences[owner_id] = filtered
    if _session_factory(request):
        async with _session_factory(request)() as db:
            row = await db.get(PreferenceRow, preference_id)
            if row and row.user_id == int(owner_id):
                await db.delete(row)
                await db.commit()


@router.websocket("/ws/{search_id}")
async def search_events(websocket: WebSocket, search_id: str) -> None:
    settings = get_settings()
    token = websocket.query_params.get("token", "")
    if not settings.jwt_secret:
        await websocket.close(code=4401)
        return
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        owner_id = str(claims["sub"])
    except Exception:
        await websocket.close(code=4401)
        return
    registry = getattr(websocket.app.state, "pose_search_registry", None)
    session = registry.sessions.get(search_id) if registry else None
    if not session or session.owner_id != owner_id:
        await websocket.close(code=4404)
        return
    await websocket.accept()
    last_sequence = 0
    try:
        while True:
            async with session.condition:
                await session.condition.wait_for(
                    lambda: any(event["sequence"] > last_sequence for event in session.events)
                    or session.status in {"completed", "partial", "failed", "cancelled"}
                )
                new_events = [event for event in session.events if event["sequence"] > last_sequence]
            for event in new_events:
                await websocket.send_json(event)
                last_sequence = event["sequence"]
            if session.status in {"completed", "partial", "failed", "cancelled"} and not new_events:
                return
    except WebSocketDisconnect:
        return
