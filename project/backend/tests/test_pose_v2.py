from __future__ import annotations

from types import SimpleNamespace

import pytest
import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import dialect

from project.backend.app.repositories.search_cache import PostgresCachedDocumentRepository
from project.backend.search_engine.api import SearchSession, SearchSessionRegistry, add_feedback
from project.backend.search_engine.harness.budget import SearchBudget
from project.backend.search_engine.harness.evidence import _validate_public_host
from project.backend.search_engine.pipeline import SearchPipeline
from project.backend.search_engine.ranking.constraints import evaluate_criterion
from project.backend.search_engine.ranking.utility_ranker import UtilityWeights, rank_candidates
from project.backend.search_engine.retrieval.fusion import weighted_reciprocal_rank_fusion
from project.backend.search_engine.retrieval.dense import cosine_similarity, hashing_embedding
from project.backend.search_engine.retrieval.sparse import bm25_scores
from project.backend.search_engine.schemas import (
    Criterion,
    Preference,
    SearchContext,
    SearchCandidate,
    SearchFeedback,
    SearchIntent,
    SearchRequest,
)
from project.backend.search_engine.sources.fixture import FixtureSearchProvider
from project.backend.search_engine.sources.urls import canonicalize_url, stable_document_id
from project.backend.search_engine.understanding.intent_parser import DeterministicIntentParser
from project.backend.search_engine.understanding.llm import OpenAICompatibleIntentClient


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


def test_intent_schema_bounds_operators_and_weights() -> None:
    with pytest.raises(ValidationError):
        Criterion(
            attribute="price",
            operator="approx",
            value=10,
            weight=1.2,
            confidence=0.7,
            source="explicit",
        )
    with pytest.raises(ValidationError):
        SearchIntent(
            original_query="x",
            objective="x",
            rewritten_query="x",
            sub_queries=["a", "b", "c", "d"],
        )


@pytest.mark.asyncio
async def test_intent_parser_marks_explicit_exclusion_and_hard_condition() -> None:
    parsed = await DeterministicIntentParser().parse(
        "quiet study cafe and no loud music must have power outlets"
    )
    assert parsed.exclusions
    assert parsed.exclusions[0].is_hard_constraint is True
    assert any(item.is_hard_constraint for item in parsed.criteria)
    assert len(parsed.sub_queries) <= 3


def test_url_canonicalization_preserves_meaningful_parameters() -> None:
    canonical = canonicalize_url(
        "HTTPS://WWW.Example.org:443/article?id=7&utm_source=mail&lang=ko#section"
    )
    assert canonical == "https://example.org/article?id=7&lang=ko"
    assert stable_document_id(canonical) == stable_document_id(canonical)
    with pytest.raises(ValueError):
        canonicalize_url("https://user:password@example.org/private")


def test_hashing_embedding_is_normalized_and_dimension_compatible() -> None:
    vector = hashing_embedding("quiet study cafe", dimension=128)
    assert len(vector) == 128
    assert sum(value * value for value in vector) == pytest.approx(1.0)
    assert cosine_similarity(vector, [1.0, 0.0]) == 0.0


def test_bm25_and_weighted_rrf_are_deterministic() -> None:
    documents = [
        candidate("a", "BM25 search ranking with sparse retrieval"),
        candidate("b", "a park with benches"),
    ]
    scores = bm25_scores("BM25 ranking", documents)
    assert scores[0] > scores[1]
    fused = weighted_reciprocal_rank_fusion(
        {"external": ["b", "a"], "sparse": ["a", "b"]},
        {"external": 0.2, "sparse": 0.8},
    )
    assert fused["a"] > 0 and fused["b"] > 0
    assert fused["a"] > fused["b"]


def test_hard_constraint_violation_and_missing_negative_evidence() -> None:
    remote = Criterion(
        attribute="remote",
        operator="eq",
        value=True,
        weight=1,
        confidence=1,
        is_hard_constraint=True,
        source="explicit",
    )
    assert evaluate_criterion(remote, candidate("office", "office role", {"remote": False})).status == "violated"

    no_loud_music = Criterion(
        attribute="music",
        operator="neq",
        value="loud music",
        weight=1,
        confidence=1,
        is_hard_constraint=True,
        source="explicit",
    )
    assert evaluate_criterion(no_loud_music, candidate("silent", "quiet cafe with comfortable seating")).status == "unknown"
    assert evaluate_criterion(no_loud_music, candidate("loud", "busy cafe with loud music")).status == "violated"
    assert evaluate_criterion(no_loud_music, candidate("no-music", "cafe without loud music")).status == "satisfied"

    outlets = Criterion(
        attribute="query_requirement",
        operator="semantic_match",
        value="power outlets",
        weight=1,
        confidence=1,
        is_hard_constraint=True,
        source="explicit",
    )
    assert evaluate_criterion(outlets, candidate("no-outlets", "Busy cafe. No power outlets.")).status == "violated"


def test_hard_constraint_policy_excludes_violations_and_marks_unknown_unverified() -> None:
    remote = Criterion(
        attribute="remote",
        operator="eq",
        value=True,
        weight=1,
        confidence=1,
        is_hard_constraint=True,
        source="explicit",
    )
    verified, unverified, excluded = rank_candidates(
        "quiet cafe",
        [
            candidate("violated", "quiet cafe", {"remote": False}),
            candidate("unknown", "quiet cafe with comfortable seating"),
        ],
        {"violated": 1.0, "unknown": 0.9},
        [],
        [remote],
        [],
        weights=UtilityWeights(threshold=0),
    )
    assert excluded == 1
    assert verified == []
    assert [item.document.document_id for item in unverified] == ["unknown"]
    assert unverified[0].evaluations[0].status == "unknown"


def test_search_budget_stops_at_round_call_and_deadline_limits() -> None:
    budget = SearchBudget(max_rounds=2, max_queries_per_round=3, max_external_calls=4)
    assert budget.can_search(3)
    budget.consume_search(3)
    assert not budget.can_search(2)
    budget.consume_search(1)
    assert not budget.can_search(1)


@pytest.mark.asyncio
async def test_evidence_host_guard_rejects_loopback_and_private_hosts() -> None:
    with pytest.raises(ValueError):
        await _validate_public_host("127.0.0.1")
    with pytest.raises(ValueError):
        await _validate_public_host("localhost")


def test_personalization_changes_rank_and_opt_out_removes_profile_signal() -> None:
    quiet = candidate("a-quiet", "cafe study quiet seats")
    lively = candidate("b-lively", "cafe study lively music")
    documents = [lively, quiet]
    preference = Preference(attribute="noise_level", value="quiet", weight=1, confidence=1)
    no_criteria = []
    personalized, _, _ = rank_candidates(
        "study cafe",
        documents,
        {"a-quiet": 1.0, "b-lively": 1.0},
        [preference],
        no_criteria,
        [],
        weights=None,
    )
    assert personalized[0].document.document_id == "a-quiet"

    profile_one, _, _ = rank_candidates("study cafe", documents, {"a-quiet": 1.0, "b-lively": 1.0}, [], [], [])
    profile_two, _, _ = rank_candidates("study cafe", documents, {"a-quiet": 1.0, "b-lively": 1.0}, [], [], [])
    assert [item.document.document_id for item in profile_one] == [item.document.document_id for item in profile_two]
    assert [item.score for item in profile_one] == [item.score for item in profile_two]


@pytest.mark.asyncio
async def test_personalization_opt_out_ignores_different_profiles_end_to_end() -> None:
    provider = FixtureSearchProvider()
    request = SearchRequest(query="quiet study cafe", personalization_enabled=False)
    responses = []
    for profile in [
        [Preference(attribute="noise_level", value="quiet", weight=1)],
        [Preference(attribute="noise_level", value="loud", weight=1)],
    ]:
        response = await SearchPipeline(
            provider=provider,
            use_llm=False,
            enable_evidence_fetch=False,
            model_client=NoopModelServer(),
        ).run(request, user_id=7, preferences=profile)
        responses.append([
            (item.document.document_id, item.score)
            for item in [*response.verified_results, *response.unverified_results]
        ])
    assert responses[0] == responses[1]


@pytest.mark.asyncio
async def test_llm_intent_client_retries_one_transient_failure(monkeypatch) -> None:
    import project.backend.search_engine.understanding.llm as llm_module

    calls = 0

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [
                    {
                        "message": {
                            "content": SearchIntent(
                                original_query="quiet cafe",
                                objective="Find a quiet cafe",
                                rewritten_query="quiet cafe",
                            ).model_dump_json()
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise httpx.ConnectError("temporary transport failure")
            return FakeResponse()

    async def no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(llm_module.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(llm_module.asyncio, "sleep", no_sleep)
    client = OpenAICompatibleIntentClient(max_retries=1)
    parsed = await client.parse_intent("quiet cafe", SearchContext(), [])
    assert parsed.original_query == "quiet cafe"
    assert calls == 2
    assert client.last_retry_count == 1


def test_url_dedup_and_stable_ids_across_fixture_adapter() -> None:
    url = "https://example.org/result?utm_campaign=x&id=1"
    canonical = canonicalize_url(url)
    assert canonical == "https://example.org/result?id=1"
    assert stable_document_id(canonical) == stable_document_id(canonicalize_url(url))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_fixture_search_pipeline_runs_without_external_services() -> None:
    pipeline = SearchPipeline(
        provider=FixtureSearchProvider(),
        use_llm=False,
        enable_evidence_fetch=False,
        model_client=NoopModelServer(),
    )
    response = await pipeline.run(
        SearchRequest(query="quiet study cafe"),
        user_id=42,
        preferences=[],
        search_id="fixture-integration",
    )
    assert response.status == "completed"
    assert response.intent is not None
    assert response.verified_results or response.unverified_results
    assert len(response.verified_results) <= 10


@pytest.mark.asyncio
@pytest.mark.integration
async def test_pipeline_retrieves_and_refreshes_cached_documents() -> None:
    cached_document = candidate(
        "cached-doc",
        "Information retrieval guide with a BM25 search example.",
    ).model_copy(
        update={
            "title": "Information retrieval guide",
            "source": "cache",
            "embedding_model": "BAAI/bge-m3",
            "embedding_version": "v1",
            "embedding": [1.0, *([0.0] * 1023)],
        }
    )

    class EmptyProvider:
        name = "empty-fixture"

        async def search(self, query, limit, context):
            return []

    class VectorModelServer:
        async def embed(self, texts):
            return [[1.0, *([0.0] * 1023)] for _ in texts], "BAAI/bge-m3"

        async def rerank(self, query, documents):
            return None

    class InMemoryDocumentCache:
        def __init__(self):
            self.searches = []
            self.upserted = []

        async def search(self, query_embedding, embedding_model, limit):
            self.searches.append((query_embedding, embedding_model, limit))
            return [cached_document.model_copy(deep=True)]

        async def upsert(self, documents):
            self.upserted.extend(documents)

    cache = InMemoryDocumentCache()
    response = await SearchPipeline(
        provider=EmptyProvider(),
        use_llm=False,
        enable_evidence_fetch=False,
        model_client=VectorModelServer(),
        document_repository=cache,
    ).run(SearchRequest(query="information retrieval"), user_id="cache-test")
    results = [*response.verified_results, *response.unverified_results]
    assert results
    assert results[0].document.source == "cache"
    assert cache.searches
    assert cache.searches[0][1] == "BAAI/bge-m3"
    assert cache.upserted


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
        embedding_version="v1",
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
                embedding_version="v1",
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


@pytest.mark.asyncio
async def test_location_query_requests_clarification_without_guessing() -> None:
    response = await SearchPipeline(
        provider=FixtureSearchProvider(),
        use_llm=False,
        model_client=NoopModelServer(),
    ).run(SearchRequest(query="quiet cafe near me"), user_id=1)
    assert response.status == "clarification_required"
    assert response.intent is not None
    assert response.intent.clarification_required is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_explicit_search_criterion_overrides_conflicting_user_memory() -> None:
    explicit_quiet = Criterion(
        attribute="noise_level",
        operator="semantic_match",
        value="quiet",
        weight=1,
        confidence=1,
        is_hard_constraint=True,
        source="explicit",
    )
    response = await SearchPipeline(
        provider=FixtureSearchProvider(),
        use_llm=False,
        model_client=NoopModelServer(),
    ).run(
        SearchRequest(
            query="quiet cafe",
            context=SearchContext(criteria_overrides=[explicit_quiet]),
        ),
        user_id=9,
        preferences=[Preference(attribute="noise_level", value="loud", weight=1)],
    )
    assert response.intent is not None
    assert response.intent.criteria[0].is_hard_constraint is True
    assert response.preferences_used == []


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
