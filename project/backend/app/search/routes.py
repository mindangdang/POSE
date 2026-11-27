from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, field_validator
from starlette import status

from project.backend.app.api.dependencies import get_current_user
from project.backend.app.runtime.sessions import get_registry
from project.backend.app.search.persistence import (
    get_session_factory,
    load_preferences,
    delete_persisted_preference,
    owned_session,
    persist_feedback_once,
    persist_preference,
    persist_search,
)
from project.backend.search_engine.personalization.embedding import refresh_preference_embedding
from project.backend.search_engine.schemas import FeedbackType, Preference, SearchFeedback, SearchRequest


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

    @field_validator("answers")
    @classmethod
    def allow_only_context_fields(cls, answers: dict[str, Any]) -> dict[str, Any]:
        allowed = {"location", "task_context", "criteria_overrides", "exclusion_overrides"}
        if set(answers) - allowed:
            raise ValueError("Clarification can update only search context fields")
        return answers



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
        await load_preferences(
            registry, owner_id, get_session_factory(request), session.session_id
        )
        session.session_preferences = registry.session_preferences.get(
            (owner_id, session.session_id), []
        )
    await persist_search(get_session_factory(request), session)
    await registry.start(
        session,
        getattr(request.app.state, "pose_search_provider", None),
        get_session_factory(request),
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
    context["session_id"] = old.session_id
    new_request = old.request.model_copy(update={"context": old.request.context.model_validate(context)})
    session = await registry.create(old.owner_id, new_request)
    session.session_preferences = old.session_preferences
    if new_request.personalization_enabled:
        await load_preferences(
            registry, old.owner_id, get_session_factory(request), session.session_id
        )
        session.session_preferences = registry.session_preferences.get(
            (old.owner_id, session.session_id), session.session_preferences
        )
    await persist_search(get_session_factory(request), session)
    await registry.start(
        session,
        getattr(request.app.state, "pose_search_provider", None),
        get_session_factory(request),
    )
    return {"search_id": session.search_id, "status": session.status}


@router.post("/search/{search_id}/cancel")
async def cancel_search(
    search_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    session = await owned_session(request, get_registry(request), search_id, str(current_user["sub"]))
    registry = get_registry(request)
    if session.task and not session.task.done():
        session.task.cancel()
        await asyncio.gather(session.task, return_exceptions=True)
    else:
        await registry.transition(session, "cancelled", "SEARCH_CANCELLED")
    return {"search_id": search_id, "status": session.status}


@router.post("/feedback")
async def add_feedback(
    payload: SearchFeedback,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    registry = get_registry(request)
    session = await owned_session(request, registry, payload.search_id, str(current_user["sub"]))
    async with registry.feedback_lock(session.owner_id):
        owner_key = (session.owner_id, payload.idempotency_key)
        if payload.idempotency_key in session.feedback_keys or registry.has_feedback(owner_key):
            return {"status": "duplicate", "updated_preferences": 0}
        if not session.response:
            raise HTTPException(status_code=409, detail="Search results are not available yet")
        exposed = {
            result.document.document_id
            for result in [*session.response.verified_results, *session.response.unverified_results]
        }
        if payload.document_id and payload.document_id not in exposed:
            raise HTTPException(status_code=400, detail="Feedback must reference an exposed result")
        session_factory = get_session_factory(request)
        preference_to_store: Preference | None = None
        if payload.feedback_type == FeedbackType.PREFERENCE_UPDATE and payload.preference:
            preference = payload.preference.model_copy(update={"user_id": session.owner_id})
            if payload.feedback_scope == "session":
                session_key = (session.owner_id, session.session_id)
                session_items = registry.session_preferences.get(session_key, [])
                if not any(item.id == preference.id for item in session_items):
                    preference = preference.model_copy(update={"id": str(uuid4())})
                values = preference.model_dump()
                values.update(scope="session", session_id=session.session_id)
                preference = Preference.model_validate(values)
            else:
                if preference.scope.value == "session":
                    raise HTTPException(
                        status_code=400,
                        detail="Related-search preference updates must use a persistent scope",
                    )
                loaded = await load_preferences(
                    registry, session.owner_id, session_factory, session.session_id
                )
                if not any(item.id == preference.id for item in loaded):
                    preference = preference.model_copy(update={"id": str(uuid4())})
            preference = Preference.model_validate(preference.model_dump())
            preference_to_store = await refresh_preference_embedding(preference)
        inserted = await persist_feedback_once(
            session_factory, payload, session.owner_id, preference_to_store
        )
        if not inserted:
            session.feedback_keys.add(payload.idempotency_key)
            registry.remember_feedback(owner_key)
            return {"status": "duplicate", "updated_preferences": 0}
        session.feedback_keys.add(payload.idempotency_key)
        registry.remember_feedback(owner_key)
        if preference_to_store:
            if preference_to_store.scope.value == "session":
                session_key = (session.owner_id, session.session_id)
                items = registry.session_preferences.setdefault(session_key, [])
                registry.session_preferences_loaded.add(session_key)
                registry.touch_session_preferences(session_key)
                session.session_preferences = items
            else:
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
        return {
            "status": "success",
            "updated_preferences": 1 if preference_to_store else 0,
        }


@router.get("/preferences")
async def list_preferences(
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    owner_id = str(current_user["sub"])
    return [
        item.model_dump(mode="json")
        for item in await load_preferences(get_registry(request), owner_id, get_session_factory(request))
    ]


@router.post("/preferences", status_code=status.HTTP_201_CREATED)
async def create_preference(
    payload: Preference,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    registry = get_registry(request)
    owner_id = str(current_user["sub"])
    await load_preferences(registry, owner_id, get_session_factory(request))
    if payload.scope.value == "session":
        raise HTTPException(status_code=400, detail="Session preferences belong to a search session")
    preference = await refresh_preference_embedding(
        payload.model_copy(update={"id": str(uuid4()), "user_id": owner_id})
    )
    items = registry.preferences.setdefault(owner_id, [])
    items.append(preference)
    await persist_preference(get_session_factory(request), preference, owner_id)
    return preference.model_dump(mode="json")


@router.patch("/preferences/{preference_id}")
async def update_preference(
    preference_id: str,
    payload: PreferencePatch,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    owner_id = str(current_user["sub"])
    items = await load_preferences(get_registry(request), owner_id, get_session_factory(request))
    index = next((i for i, item in enumerate(items) if item.id == preference_id), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Preference not found")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("scope") == "session":
        raise HTTPException(status_code=400, detail="Session preferences belong to a search session")
    updated = items[index].model_copy(update=changes)
    # Round-trip validation ensures enum/range constraints also apply to patches.
    updated = Preference.model_validate(updated.model_dump())
    if "attribute" in changes or "value" in changes:
        updated = await refresh_preference_embedding(updated)
    items[index] = updated
    await persist_preference(get_session_factory(request), updated, owner_id)
    return updated.model_dump(mode="json")


@router.delete("/preferences/{preference_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_preference(
    preference_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> None:
    owner_id = str(current_user["sub"])
    items = await load_preferences(get_registry(request), owner_id, get_session_factory(request))
    filtered = [item for item in items if item.id != preference_id]
    if len(filtered) == len(items):
        raise HTTPException(status_code=404, detail="Preference not found")
    get_registry(request).preferences[owner_id] = filtered
    await delete_persisted_preference(get_session_factory(request), preference_id, owner_id)


