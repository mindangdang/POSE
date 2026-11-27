from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.engine import make_url

from project.backend.app.db.base import Base
from project.backend.app.db.models.search import SearchFeedback, SearchSession, UserPreference
from project.backend.app.db.models.user import User
from project.backend.app.runtime.sessions import SearchSessionRegistry
from project.backend.app.search.persistence import load_preferences, persist_feedback_once
from project.backend.search_engine.schemas import Preference, SearchFeedback as FeedbackPayload


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_feedback_idempotency_and_session_preference_persistence() -> None:
    database_url = os.getenv("POSE_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("POSE_TEST_DATABASE_URL is not configured")
    url = make_url(database_url)
    if url.database != "pose_test":
        pytest.fail("PostgreSQL integration tests require the disposable pose_test database")
    async_url = url.set(drivername="postgresql+psycopg")
    schema = f"pose_it_{uuid4().hex}"
    admin_engine = create_async_engine(async_url)
    async with admin_engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(
        async_url,
        connect_args={"options": f"-c search_path={schema},public"},
    )
    tables = [
        User.__table__,
        SearchSession.__table__,
        UserPreference.__table__,
        SearchFeedback.__table__,
    ]
    try:
        async with engine.begin() as connection:
            await connection.run_sync(lambda sync: Base.metadata.create_all(sync, tables=tables))
        factory = async_sessionmaker(engine, expire_on_commit=False)
        search_id = str(uuid4())
        session_id = str(uuid4())
        async with factory() as db:
            user = User(oauth_user_id="pose-it-user", email="pose-it@example.test")
            db.add(user)
            await db.flush()
            user_id = user.id
            db.add(
                SearchSession(
                    search_id=search_id,
                    user_id=user_id,
                    status="completed",
                    query="quiet cafe",
                    request_json={"query": "quiet cafe"},
                )
            )
            await db.commit()

        preference = Preference(
            attribute="noise_level",
            value="quiet",
            scope="session",
            session_id=session_id,
            embedding=[0.0] * 1024,
        )
        feedback = FeedbackPayload(
            idempotency_key="integration-once",
            search_id=search_id,
            feedback_type="PREFERENCE_UPDATE",
            preference=preference,
        )
        results = await asyncio.gather(
            persist_feedback_once(factory, feedback, str(user_id), preference),
            persist_feedback_once(factory, feedback, str(user_id), preference),
        )
        assert sorted(results) == [False, True]

        async with factory() as db:
            feedback_count = await db.scalar(
                select(func.count()).select_from(SearchFeedback).where(
                    SearchFeedback.user_id == user_id,
                    SearchFeedback.idempotency_key == "integration-once",
                )
            )
            preference_count = await db.scalar(
                select(func.count()).select_from(UserPreference).where(
                    UserPreference.user_id == user_id,
                    UserPreference.session_id == session_id,
                )
            )
        assert feedback_count == 1
        assert preference_count == 1

        registry = SearchSessionRegistry()
        session_preferences = await load_preferences(registry, str(user_id), factory, session_id)
        other_session_preferences = await load_preferences(
            registry, str(user_id), factory, str(uuid4())
        )
        assert [item.value for item in session_preferences] == ["quiet"]
        assert other_session_preferences == []
    finally:
        await engine.dispose()
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin_engine.dispose()
