from __future__ import annotations

from types import SimpleNamespace
from datetime import timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.dialects.postgresql import dialect

from project.backend.app.repositories.search_cache import PostgresCachedDocumentRepository
from project.backend.app.runtime.sessions import SearchSession, SearchSessionRegistry
from project.backend.app.search.persistence import load_preferences
from project.backend.app.search.routes import add_feedback
import project.backend.app.search.routes as search_routes
from project.backend.search_engine.pipeline import SearchPipeline
from project.backend.search_engine.schemas import (
    Preference,
    SearchCandidate,
    SearchFeedback,
    SearchRequest,
    SearchResponse,
)
from project.backend.search_engine.sources.fixture import FixtureSearchProvider


class NoopModelServer:
    async def embed(self, texts):
        return None

    async def rerank(self, query, documents):
        return None


def candidate(document_id: str, body: str, metadata: dict | None = None) -> SearchCandidate:
    url = f"https://example.org/{document_id}"
    return SearchCandidate(
        document_id=document_id,
        canonical_url=url,
        source_url=url,
        title="Study cafe",
        snippet=body,
        content=body,
        metadata=metadata or {},
    )


@pytest.mark.asyncio
async def test_search_session_uses_distinct_session_and_execution_ids() -> None:
    registry = SearchSessionRegistry()
    session = await registry.create(
        "7",
        SearchRequest(query="coffee", context={"session_id": "browser-session"}),
    )
    assert session.session_id == "browser-session"
    assert session.search_id != session.session_id
    assert session.execution_id != session.search_id
    assert session.request.context.session_id == "browser-session"


@pytest.mark.asyncio
async def test_search_events_keep_monotonic_sequence_after_trimming() -> None:
    registry = SearchSessionRegistry()
    session = await registry.create("7", SearchRequest(query="coffee"))
    for index in range(205):
        await registry.emit(session.search_id, "PROGRESS", index=index)
    sequences = [event["sequence"] for event in session.events]
    assert len(sequences) == 200
    assert sequences == sorted(sequences)
    assert sequences[0] > 1
    assert sequences[-1] == session.event_sequence


@pytest.mark.asyncio
async def test_terminal_state_and_event_are_immutable_and_deduplicated() -> None:
    registry = SearchSessionRegistry()
    session = await registry.create("7", SearchRequest(query="coffee"))
    assert await registry.transition(session, "running", "SEARCH_RUNNING")
    assert await registry.transition(session, "completed", "SEARCH_COMPLETED")
    assert not await registry.transition(session, "completed", "SEARCH_COMPLETED")
    assert not await registry.transition(session, "cancelled", "SEARCH_CANCELLED")
    await registry.emit(session.search_id, "SEARCH_COMPLETED", status="completed")
    assert session.status == "completed"
    assert [event["type"] for event in session.events].count("SEARCH_COMPLETED") == 1


@pytest.mark.asyncio
async def test_queued_search_can_be_cancelled_once() -> None:
    registry = SearchSessionRegistry()
    session = await registry.create("7", SearchRequest(query="coffee"))
    assert await registry.transition(session, "cancelled", "SEARCH_CANCELLED")
    assert not await registry.transition(session, "running", "SEARCH_RUNNING")
    assert session.status == "cancelled"


@pytest.mark.asyncio
async def test_session_preferences_are_scoped_to_browser_session() -> None:
    registry = SearchSessionRegistry()
    global_preference = Preference(attribute="topic", value="science", scope="global")
    scoped = Preference(
        attribute="noise",
        value="quiet",
        scope="session",
        session_id="browser-one",
    )
    registry.preferences["7"] = [global_preference]
    registry.preferences_loaded.add("7")
    registry.session_preferences[("7", "browser-one")] = [scoped]
    registry.session_preferences_loaded.add(("7", "browser-one"))
    first = await load_preferences(registry, "7", None, "browser-one")
    second = await load_preferences(registry, "7", None, "browser-two")
    assert {item.value for item in first} == {"science", "quiet"}
    assert {item.value for item in second} == {"science"}


@pytest.mark.asyncio
async def test_feedback_preference_is_attached_to_browser_session(monkeypatch) -> None:
    registry = SearchSessionRegistry()
    session = await registry.create(
        "7", SearchRequest(query="quiet cafe", context={"session_id": "browser-one"})
    )
    await registry.transition(session, "running", "SEARCH_RUNNING")
    await registry.transition(session, "completed", "SEARCH_COMPLETED")
    session.response = SearchResponse(search_id=session.search_id, status="completed")

    async def keep_unembedded(preference):
        return preference

    monkeypatch.setattr(search_routes, "refresh_preference_embedding", keep_unembedded)
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(pose_search_registry=registry, db_session_factory=None)
        )
    )
    payload = SearchFeedback(
        idempotency_key="session-preference",
        search_id=session.search_id,
        feedback_type="PREFERENCE_UPDATE",
        preference=Preference(attribute="noise", value="quiet"),
    )
    result = await add_feedback(payload, request, {"sub": 7})
    assert result["status"] == "success"
    saved = registry.session_preferences[("7", "browser-one")][0]
    assert saved.scope.value == "session"
    assert saved.session_id == "browser-one"
    next_search = await registry.create(
        "7", SearchRequest(query="coffee", context={"session_id": "browser-one"})
    )
    loaded = await load_preferences(registry, "7", None, next_search.session_id)
    assert any(item.id == saved.id for item in loaded)


@pytest.mark.asyncio
async def test_registry_expires_only_terminal_sessions_and_enforces_capacity() -> None:
    registry = SearchSessionRegistry(ttl=timedelta(seconds=1), max_sessions=2)
    finished = await registry.create("7", SearchRequest(query="done"))
    await registry.transition(finished, "cancelled", "SEARCH_CANCELLED")
    active = await registry.create("7", SearchRequest(query="active"))
    await registry.transition(active, "running", "SEARCH_RUNNING")
    finished.last_activity_at -= timedelta(seconds=2)
    registry.prune()
    assert finished.search_id not in registry.sessions
    assert active.search_id in registry.sessions
    await registry.create("7", SearchRequest(query="active two"))
    with pytest.raises(HTTPException) as error:
        await registry.create("7", SearchRequest(query="capacity"))
    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_postgres_document_cache_queries_and_writes_model_keyed_vectors() -> None:
    vector = [1.0, *([0.0] * 1023)]
    document_row = SimpleNamespace(
        document_id="cached-row",
        canonical_url="https://example.org/cached-row",
        source_url="https://example.org/cached-row",
        title="Cached document",
        snippet="A useful snippet",
        content="Cached document content",
        source="fixture",
        document_type="web_page",
        published_at=None,
        fetched_at=None,
        metadata_json={"topic": "search"},
    )
    embedding_row = SimpleNamespace(
        embedding_model="BAAI/bge-m3",
        embedding_version="bge-m3-cls-v1",
        embedding_dimension=1024,
        pooling_method="cls",
        content_hash="current-content-hash",
        embedding=vector,
    )

    class FakeResult:
        def all(self):
            return [(document_row, embedding_row)]

    class FakeSession:
        def __init__(self):
            self.compiled_statements = []
            self.committed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def execute(self, statement):
            self.compiled_statements.append(str(statement.compile(dialect=dialect())))
            return FakeResult()

        async def commit(self):
            self.committed = True

    db = FakeSession()
    repository = PostgresCachedDocumentRepository(lambda: db)
    results = await repository.search(vector, "BAAI/bge-m3", 5)
    await repository.upsert(
        [
            SearchCandidate(
                document_id="cached-row",
                canonical_url="https://example.org/cached-row",
                source_url="https://example.org/cached-row",
                title="Cached document",
                snippet="A useful snippet",
                content="Cached document content",
                source="fixture",
                embedding_model="BAAI/bge-m3",
                embedding_version="bge-m3-cls-v1",
                embedding_dimension=1024,
                embedding_pooling_method="cls",
                embedding=vector,
            )
        ]
    )
    assert results[0].document_id == "cached-row"
    assert results[0].metadata == {"topic": "search"}
    assert results[0].retrieval_ranks == {"cached": 1}
    assert "<=>" in db.compiled_statements[0]
    assert len(db.compiled_statements) == 4
    assert db.committed is True

@pytest.mark.asyncio
@pytest.mark.integration
async def test_feedback_is_idempotent_and_search_is_owner_scoped() -> None:
    registry = SearchSessionRegistry()
    # Construct a minimal typed result through the real fixture workflow so feedback
    # can only point at an item the response actually exposed.
    pipeline_response = await SearchPipeline(
        provider=FixtureSearchProvider(),
        use_llm=False,
        model_client=NoopModelServer(),
    ).run(SearchRequest(query="study cafe"), user_id=7, search_id="owned-search")
    exposed = next(
        iter([*pipeline_response.verified_results, *pipeline_response.unverified_results]),
        None,
    )
    assert exposed is not None
    result_response = pipeline_response.model_copy(update={"search_id": "owned-search"})
    session = SearchSession(
        search_id="owned-search",
        owner_id="7",
        request=SearchRequest(query="study cafe"),
        status="completed",
        response=result_response,
    )
    registry.sessions[session.search_id] = session
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(pose_search_registry=registry, db_session_factory=None))
    )
    payload = SearchFeedback(
        idempotency_key="once",
        search_id=session.search_id,
        document_id=exposed.document.document_id,
        original_rank=exposed.rank,
        feedback_type="RESULT_LIKE",
    )
    first = await add_feedback(payload, request, {"sub": 7})
    duplicate = await add_feedback(payload, request, {"sub": 7})
    assert first["status"] == "success"
    assert duplicate["status"] == "duplicate"
    with pytest.raises(HTTPException) as error:
        await add_feedback(payload, request, {"sub": 8})
    assert error.value.status_code == 404

@pytest.mark.integration
def test_backend_and_lazy_model_server_health_without_database_or_weights(monkeypatch) -> None:
    import project.backend.app.manage.database as database_module
    from project.backend.main import app as backend_app
    from project.gpu_server.main import app as model_server_app

    monkeypatch.setattr(database_module, "get_settings", lambda: SimpleNamespace(neon_db_url=None))
    with TestClient(backend_app) as backend_client:
        backend = backend_client.get("/api/v2/health")
    with TestClient(model_server_app) as model_client:
        model = model_client.get("/health")
    assert backend.status_code == 200
    assert backend.json()["service"] == "pose-search-v2"
    assert model.status_code == 200
    assert model.json()["embedding_loaded"] is False
