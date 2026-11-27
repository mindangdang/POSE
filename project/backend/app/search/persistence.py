from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from fastapi import HTTPException, Request

from project.backend.app.db.models.search import (
    Document as DocumentRow,
    SearchFeedback as FeedbackRow,
    SearchImpression as ImpressionRow,
    SearchSession as SessionRow,
    SearchTrace as TraceRow,
    UserPreference as PreferenceRow,
)
from project.backend.search_engine.schemas import Preference, SearchFeedback, SearchRequest, SearchResponse

if TYPE_CHECKING:
    from project.backend.app.runtime.sessions import SearchSession, SearchSessionRegistry


def get_session_factory(request: Request):
    return getattr(request.app.state, "db_session_factory", None)


def _preference_from_row(row, owner_id: str) -> Preference:
    return Preference(
        id=row.id,
        user_id=owner_id,
        attribute=row.attribute,
        value=row.value,
        polarity=row.polarity,
        weight=row.weight,
        confidence=row.confidence,
        scope=row.scope,
        domain=row.domain,
        session_id=row.session_id,
        source=row.source,
        evidence_event_ids=row.evidence_event_ids,
        embedding=row.embedding,
        embedding_space=row.embedding_space,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def load_preferences(
    registry: SearchSessionRegistry,
    owner_id: str,
    session_factory,
    session_id: str | None = None,
) -> list[Preference]:
    if owner_id not in registry.preferences_loaded:
        if session_factory:
            from sqlalchemy import select

            async with session_factory() as db:
                rows = (
                    await db.execute(
                        select(PreferenceRow).where(
                            PreferenceRow.user_id == int(owner_id),
                            PreferenceRow.active.is_(True),
                            PreferenceRow.scope != "session",
                        )
                    )
                ).scalars().all()
            registry.preferences[owner_id] = [_preference_from_row(row, owner_id) for row in rows]
        registry.preferences_loaded.add(owner_id)
    user_preferences = registry.preferences.setdefault(owner_id, [])
    if session_id is None:
        return user_preferences
    session_key = (owner_id, session_id)
    registry.touch_session_preferences(session_key)
    if session_key not in registry.session_preferences_loaded:
        if session_factory:
            from sqlalchemy import select

            async with session_factory() as db:
                rows = (
                    await db.execute(
                        select(PreferenceRow).where(
                            PreferenceRow.user_id == int(owner_id),
                            PreferenceRow.active.is_(True),
                            PreferenceRow.scope == "session",
                            PreferenceRow.session_id == session_id,
                        )
                    )
                ).scalars().all()
            registry.session_preferences[session_key] = [
                _preference_from_row(row, owner_id) for row in rows
            ]
        registry.session_preferences_loaded.add(session_key)
    return [*user_preferences, *registry.session_preferences.setdefault(session_key, [])]


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
                        *[
                            {"type": event["type"], "sequence": event["sequence"]}
                            for event in session.events
                        ],
                        *[
                            {
                                "type": "trace_span",
                                **span.model_dump(mode="json"),
                            }
                            for span in session.response.trace
                        ],
                    ],
                )
            )
        await db.commit()


async def persist_preference(session_factory, preference: Preference, owner_id: str) -> None:
    if not session_factory:
        return
    async with session_factory() as db:
        row = await db.get(PreferenceRow, preference.id)
        values = preference.model_dump(
            mode="json",
            exclude={"user_id", "id", "created_at", "updated_at"},
        )
        if row is None:
            row = PreferenceRow(id=preference.id, user_id=int(owner_id), **values)
            db.add(row)
        else:
            for key, value in values.items():
                setattr(row, key, value)
            row.updated_at = datetime.now(timezone.utc)
        await db.commit()


async def persist_feedback_once(
    session_factory,
    feedback: SearchFeedback,
    owner_id: str,
    preference: Preference | None = None,
) -> bool:
    """Insert feedback and its preference update atomically and idempotently."""
    if not session_factory:
        return True
    from sqlalchemy.dialects.postgresql import insert

    async with session_factory() as db:
        statement = (
            insert(FeedbackRow)
            .values(
                user_id=int(owner_id),
                search_id=feedback.search_id,
                document_id=feedback.document_id,
                original_rank=feedback.original_rank,
                idempotency_key=feedback.idempotency_key,
                feedback_type=feedback.feedback_type.value,
                feedback_reason=feedback.feedback_reason,
                affected_criterion=feedback.affected_criterion,
                feedback_scope=feedback.feedback_scope,
                feedback_json=feedback.model_dump(mode="json"),
            )
            .on_conflict_do_nothing(index_elements=[FeedbackRow.user_id, FeedbackRow.idempotency_key])
            .returning(FeedbackRow.id)
        )
        inserted_id = (await db.execute(statement)).scalar_one_or_none()
        if inserted_id is None:
            return False
        if preference is not None:
            row = await db.get(PreferenceRow, preference.id)
            values = preference.model_dump(
                mode="json",
                exclude={"user_id", "id", "created_at", "updated_at"},
            )
            if row is None:
                db.add(PreferenceRow(id=preference.id, user_id=int(owner_id), **values))
            elif row.user_id != int(owner_id):
                raise HTTPException(status_code=404, detail="Preference not found")
            else:
                for key, value in values.items():
                    setattr(row, key, value)
                row.updated_at = datetime.now(timezone.utc)
        await db.commit()
    return True


async def delete_persisted_preference(session_factory, preference_id: str, owner_id: str) -> None:
    if not session_factory:
        return
    async with session_factory() as db:
        row = await db.get(PreferenceRow, preference_id)
        if row is None or row.user_id != int(owner_id):
            raise HTTPException(status_code=404, detail="Preference not found")
        await db.delete(row)
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
    if not get_session_factory(request):
        return registry.owned(search_id, owner_id)
    from sqlalchemy import select

    async with get_session_factory(request)() as db:
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
    from project.backend.app.runtime.sessions import SearchSession, SearchStatus

    restored_request = SearchRequest.model_validate(row.request_json)
    session = SearchSession(
        search_id=row.search_id,
        owner_id=owner_id,
        request=restored_request,
        session_id=(
            restored_request.context.session_id
            or restored_request.session_id
            or row.search_id
        ),
        status=SearchStatus(row.status),
    )
    if row.response_json:
        session.response = SearchResponse.model_validate(row.response_json)
        if session.response.execution_id:
            session.execution_id = session.response.execution_id
    registry.sessions[search_id] = session
    return session


