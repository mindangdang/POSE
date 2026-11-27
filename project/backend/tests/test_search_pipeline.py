from __future__ import annotations


import pytest
import httpx

from project.backend.search_engine.pipeline import SearchPipeline
from project.backend.search_engine.evaluation.baselines import baseline_rankings
from project.backend.search_engine.retrieval.cache import document_content_hash
from project.backend.search_engine.ranking.utility_ranker import rank_candidates
from project.backend.search_engine.schemas import (
    Criterion,
    EmbeddingBatch,
    EmbeddingSpace,
    Preference,
    SearchContext,
    SearchCandidate,
    SearchIntent,
    SearchRequest,
)
from project.backend.search_engine.sources.fixture import FixtureSearchProvider
from project.backend.search_engine.sources.urls import canonicalize_url, stable_document_id
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

def test_url_dedup_and_stable_ids_across_fixture_adapter() -> None:
    url = "https://example.org/result?utm_campaign=x&id=1"
    canonical = canonicalize_url(url)
    assert canonical == "https://example.org/result?id=1"
    assert stable_document_id(canonical) == stable_document_id(canonicalize_url(url))

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
    trace_nodes = {span.node for span in response.trace}
    assert "provider_search" in trace_nodes
    assert "total" in trace_nodes


@pytest.mark.asyncio
async def test_full_text_is_fetched_before_embedding_and_cache_hashing(monkeypatch) -> None:
    import project.backend.search_engine.retrieval.service as retrieval_service

    space = EmbeddingSpace(
        model_id="test-model",
        model_version="test-cls-v1",
        dimension=2,
        pooling_method="cls",
    )
    source_document = candidate("fetched", "short snippet").model_copy(update={"content": ""})

    class Provider:
        name = "single-fixture"

        async def search(self, _query, _limit, _context):
            return [source_document.model_copy(deep=True)]

    class Model:
        def __init__(self):
            self.calls: list[list[str]] = []

        async def embed(self, texts):
            self.calls.append(list(texts))
            return EmbeddingBatch(space=space, embeddings=[[1.0, 0.0] for _ in texts])

        async def rerank(self, _query, _documents):
            return None

    class Cache:
        def __init__(self):
            self.saved: list[SearchCandidate] = []

        async def search(self, *_args, **_kwargs):
            return []

        async def upsert(self, documents):
            self.saved = [item.model_copy(deep=True) for item in documents]

    async def fetch(document):
        document.content = "The full evidence body was fetched before embedding."
        return True

    monkeypatch.setattr(retrieval_service, "fetch_candidate_evidence", fetch)
    model = Model()
    cache = Cache()
    response = await SearchPipeline(
        provider=Provider(),
        use_llm=False,
        enable_evidence_fetch=True,
        model_client=model,
        document_repository=cache,
    ).run(SearchRequest(query="evidence body"), user_id=1)
    assert response.status == "completed"
    assert "full evidence body" in model.calls[-1][0]
    saved = cache.saved[0]
    assert saved.content == "The full evidence body was fetched before embedding."
    assert saved.embedding_content_hash == document_content_hash(saved)


@pytest.mark.asyncio
async def test_b5_requires_reranker_scores_and_b6_b7_share_candidate_corpus() -> None:
    provider = FixtureSearchProvider()
    documents = await provider.search("fixture corpus", 50, SearchContext())
    preferences = [
        Preference(attribute="noise_level", value="quiet", weight=0.9),
        Preference(attribute="accessibility", value="step-free", weight=0.8),
    ]
    baseline = await baseline_rankings(
        "quiet study cafe", documents, preferences, SearchContext()
    )
    assert "B5_cross_encoder" not in baseline
    assert set(baseline["B6_static_user_vector"]) == {item.document_id for item in documents}
    assert set(baseline["B7_query_conditioned"]) == {item.document_id for item in documents}
    assert baseline["B6_static_user_vector"] != baseline["B7_query_conditioned"]

    reranked = await baseline_rankings(
        "quiet study cafe",
        documents,
        preferences,
        SearchContext(),
        cross_encoder_scores={item.document_id: float(index) for index, item in enumerate(documents)},
    )
    assert "B5_cross_encoder" in reranked
    assert set(reranked["B5_cross_encoder"]) == {item.document_id for item in documents}
