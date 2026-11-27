from __future__ import annotations

import pytest
import socket
import httpx

from project.backend.search_engine.harness.budget import SearchBudget
from project.backend.search_engine.harness.evidence import PublicOnlyBackend, fetch_public_html
from project.backend.search_engine.models import ModelServerClient
from project.backend.search_engine.personalization.encoder import QueryEncoder
from project.backend.search_engine.personalization.embedding import refresh_preference_embedding
from project.backend.search_engine.personalization.preferences import Preference
from project.backend.search_engine.pipeline import SearchPipeline
from project.backend.search_engine.ranking.constraints import (
    SemanticJudgment,
    evaluate_criterion,
    evaluate_expression,
)
from project.backend.search_engine.retrieval.dense import cosine_similarity, dense_scores
from project.backend.search_engine.ranking.utility_ranker import UtilityWeights, rank_candidates
from project.backend.search_engine.schemas import (
    ConditionExpression,
    Criterion,
    CriterionValueType,
    EmbeddingSpace,
    EmbeddingBatch,
    EmbeddingVector,
    SearchCandidate,
    SearchContext,
    SearchIntent,
    SearchRequest,
)
from project.backend.search_engine.sources.fixture import FixtureSearchProvider


def candidate(
    document_id: str,
    text: str,
    metadata: dict | None = None,
) -> SearchCandidate:
    url = f"https://example.org/{document_id}"
    return SearchCandidate(
        document_id=document_id,
        canonical_url=url,
        source_url=url,
        title="",
        snippet=text,
        content=text,
        metadata=metadata or {},
    )


def criterion(
    attribute: str,
    operator: str,
    value,
    *,
    weight=1.0,
    confidence=1.0,
    value_type="auto",
) -> Criterion:
    return Criterion(
        attribute=attribute,
        operator=operator,
        value=value,
        value_type=value_type,
        weight=weight,
        confidence=confidence,
        source="explicit",
    )


def test_unparseable_numeric_metadata_is_unknown() -> None:
    result = evaluate_criterion(
        criterion("price", "lte", 100),
        candidate("x", "budget guide", {"price": "contact us"}),
    )
    assert result.status == "unknown"


def test_numeric_date_boolean_and_enum_comparisons_are_typed() -> None:
    document = candidate(
        "typed",
        "Role details",
        {
            "salary": "125000",
            "published": "2025-03-02T10:30:00Z",
            "remote": "yes",
            "city": "York",
        },
    )
    assert evaluate_criterion(criterion("salary", "gte", 120000), document).status == "satisfied"
    assert evaluate_criterion(
        criterion("published", "gte", "2025-03-01", value_type=CriterionValueType.DATE), document
    ).status == "satisfied"
    assert evaluate_criterion(criterion("remote", "eq", True), document).status == "satisfied"
    assert evaluate_criterion(criterion("city", "eq", "New York"), document).status == "violated"


def test_semantic_phrase_presence_alone_does_not_prove_criterion() -> None:
    result = evaluate_criterion(
        criterion("atmosphere", "semantic_match", "quiet"),
        candidate("x", "A quietly decorated cafe with bright walls."),
    )
    assert result.status == "unknown"
    assert result.evidence_excerpt is None


def test_multiple_preferences_accumulate_and_negative_preferences_reduce_score() -> None:
    documents = [
        candidate("a-both", "quiet outlets"),
        candidate("b-quiet", "quiet"),
        candidate("c-loud", "loud outlets"),
    ]
    preferences = [
        Preference(attribute="feature", value="quiet", weight=1, confidence=1),
        Preference(attribute="feature", value="outlets", weight=1, confidence=1),
        Preference(attribute="noise", value="loud", polarity="negative", weight=1, confidence=1),
    ]
    verified, _, _ = rank_candidates(
        "study cafe",
        documents,
        {item.document_id: 0.01 for item in documents},
        preferences,
        [],
        [],
        weights=UtilityWeights(threshold=0),
    )
    scores = {item.document.document_id: item.features.preference_compatibility for item in verified}
    assert scores["a-both"] > scores["b-quiet"]
    assert scores["c-loud"] < scores["b-quiet"]


def test_zero_weight_and_confidence_criterion_does_not_change_utility() -> None:
    document = candidate("x", "remote work", {"remote": False})
    base, _, _ = rank_candidates(
        "remote work", [document], {"x": 1}, [], [], [], weights=UtilityWeights(threshold=0)
    )
    ignored, _, _ = rank_candidates(
        "remote work",
        [document],
        {"x": 1},
        [],
        [criterion("remote", "eq", True, weight=0, confidence=1)],
        [],
        weights=UtilityWeights(threshold=0),
    )
    assert ignored[0].score == pytest.approx(base[0].score)


def test_reranker_scores_are_used_only_when_a_reranker_result_exists() -> None:
    documents = [candidate("a", "search query"), candidate("b", "search query")]
    ranked, _, _ = rank_candidates(
        "search query",
        documents,
        {"a": 10_000, "b": 0.0001},
        [],
        [],
        [],
        weights=UtilityWeights(
            relevance=1,
            preference=0,
            constraints=0,
            evidence=0,
            reranker=1,
            threshold=0,
        ),
        cross_encoder_scores={"a": 0.0, "b": 1.0},
    )
    assert [item.document.document_id for item in ranked] == ["b", "a"]


def test_high_weight_criterion_controls_soft_constraint_score() -> None:
    documents = [
        candidate("a-primary", "remote role", {"remote": True, "flexible_hours": False}),
        candidate("b-secondary", "remote role", {"remote": False, "flexible_hours": True}),
    ]
    criteria = [
        criterion("remote", "eq", True, weight=1, confidence=1),
        criterion("flexible_hours", "eq", True, weight=0.1, confidence=1),
    ]
    verified, _, _ = rank_candidates(
        "remote role",
        documents,
        {"a-primary": 0.001, "b-secondary": 1000.0},
        [],
        criteria,
        [],
        weights=UtilityWeights(threshold=0),
    )
    scores = {item.document.document_id: item.features.constraint_satisfaction for item in verified}
    assert scores["a-primary"] > scores["b-secondary"]


class NoopModelServer:
    async def embed(self, texts):
        return None

    async def rerank(self, query, documents):
        return None


class PreferenceSpyParser:
    def __init__(self) -> None:
        self.preferences: list[Preference] = []
        self.last_retry_count = 0

    async def parse(self, query, context, preferences):
        self.preferences = list(preferences)
        return (
            SearchIntent(
                original_query=query,
                objective="Find a quiet cafe",
                rewritten_query=query,
            ),
            None,
        )


@pytest.mark.asyncio
async def test_conflicting_preference_is_filtered_before_intent_rewrite() -> None:
    preference = Preference(attribute="noise_level", value="loud", weight=1, confidence=1)
    parser = PreferenceSpyParser()
    pipeline = SearchPipeline(
        provider=FixtureSearchProvider(),
        enable_evidence_fetch=False,
        model_client=NoopModelServer(),
    )
    pipeline.parser = parser
    state = {
        "request": SearchRequest(query="quiet cafe", context=SearchContext()),
        "preferences": [preference],
        "errors": [],
        "trace": type("Trace", (), {"record": lambda *args, **kwargs: None})(),
        "search_id": "conflict-check",
    }
    await pipeline.prepare(state)
    assert parser.preferences == []


def test_evidence_budget_is_cumulative_across_rounds() -> None:
    budget = SearchBudget(max_evidence_documents=2)
    assert budget.consume_evidence(2) == 2
    assert budget.evidence_remaining == 0
    assert budget.consume_evidence(1) == 0
    semantic_budget = SearchBudget(max_semantic_evaluations=1)
    assert semantic_budget.consume_semantic(1) == 1
    assert semantic_budget.consume_semantic(1) == 0


def test_rrf_retrieval_score_does_not_create_relevance_for_unrelated_results() -> None:
    unrelated = [candidate("x", "mountain hiking guide")]
    verified, unverified, _ = rank_candidates(
        "quantum accounting",
        unrelated,
        {"x": 0.0001},
        [],
        [],
        [],
    )
    assert verified == []
    assert unverified == []


def test_embedding_space_mismatch_is_rejected_and_missing_vectors_are_not_hashed() -> None:
    bge = EmbeddingSpace(
        model_id="BAAI/bge-m3", model_version="bge-m3-cls-v1", dimension=2, pooling_method="cls"
    )
    hashing = EmbeddingSpace(
        model_id="pose-hashing-fallback-v1", model_version="v1", dimension=2, pooling_method="hashing"
    )
    with pytest.raises(ValueError, match="same embedding space"):
        cosine_similarity(
            EmbeddingVector(space=bge, values=[1, 0]),
            EmbeddingVector(space=hashing, values=[1, 0]),
        )
    assert dense_scores(EmbeddingVector(space=bge, values=[1, 0]), [candidate("x", "any text")]) == [0.0]


def test_condition_expression_supports_and_or_not_with_unknowns() -> None:
    remote = criterion("remote", "eq", True)
    price = criterion("price", "lte", 100)
    document = candidate("x", "role details", {"remote": "true", "price": "not listed"})
    and_result = evaluate_expression(
        ConditionExpression(operator="and", operands=[
            ConditionExpression(criterion=remote), ConditionExpression(criterion=price)
        ]),
        document,
    )
    or_result = evaluate_expression(
        ConditionExpression(operator="or", operands=[
            ConditionExpression(criterion=remote), ConditionExpression(criterion=price)
        ]),
        document,
    )
    not_result = evaluate_expression(
        ConditionExpression(operator="not", operands=[ConditionExpression(criterion=remote)]),
        document,
    )
    assert and_result.status == "unknown"
    assert or_result.status == "satisfied"
    assert not_result.status == "violated"


def test_semantic_judgment_requires_a_verifiable_quote() -> None:
    item = criterion("atmosphere", "semantic_match", "quiet")
    document = candidate("x", "A quiet room with a view.")
    invalid = evaluate_criterion(
        item, document, SemanticJudgment(status="satisfied", confidence=0.9, evidence_quote="invented quote")
    )
    valid = evaluate_criterion(
        item, document, SemanticJudgment(status="satisfied", confidence=0.9, evidence_quote="quiet room")
    )
    assert invalid.status == "unknown"
    assert valid.status == "satisfied"
    assert valid.evidence_excerpt == "quiet room"


def test_korean_and_english_negation_counterexamples() -> None:
    english = evaluate_criterion(
        criterion("requirement", "contains", "quiet"),
        candidate("en", "This room is not quiet despite the soft lighting."),
    )
    korean = evaluate_criterion(
        criterion("requirement", "neq", "시끄러운 음악"),
        candidate("ko", "카페에 시끄러운 음악이 없습니다."),
    )
    korean_positive = evaluate_criterion(
        criterion("requirement", "semantic_match", "조용"),
        candidate("ko-not-quiet", "조용하지 않은 카페입니다."),
    )
    assert english.status == "violated"
    assert korean.status == "satisfied"
    assert korean_positive.status == "violated"


def test_bge_cls_pooling_matches_first_token_hidden_state() -> None:
    from project.gpu_server.generic_models import pool_cls_tokens

    class HiddenStates:
        values = [
            [[0.0, 1.0, 2.0, 3.0], [4.0, 5.0, 6.0, 7.0], [8.0, 9.0, 10.0, 11.0]],
            [[12.0, 13.0, 14.0, 15.0], [16.0, 17.0, 18.0, 19.0], [20.0, 21.0, 22.0, 23.0]],
        ]

        def __getitem__(self, selection):
            batch, token, features = selection
            return [item[token][features] for item in self.values[batch]]

    hidden = HiddenStates()
    pooled = pool_cls_tokens(hidden, normalize=False, torch_module=object())
    assert pooled == [[0.0, 1.0, 2.0, 3.0], [12.0, 13.0, 14.0, 15.0]]


@pytest.mark.asyncio
async def test_embedding_api_reports_model_space_metadata(monkeypatch) -> None:
    import project.gpu_server.generic_routes as routes

    monkeypatch.setattr(
        routes.generic_models,
        "embed",
        lambda texts, normalize=True: ([[1.0, 0.0] for _ in texts], "cpu"),
    )
    payload = await routes.embed_batch(routes.BatchEmbedRequest(texts=["one"]))
    assert payload["model_id"] == routes.EMBEDDING_MODEL_ID
    assert payload["model_version"] == routes.EMBEDDING_MODEL_VERSION
    assert payload["embedding_dimension"] == 2
    assert payload["pooling_method"] == "cls"


@pytest.mark.asyncio
async def test_model_client_requires_complete_embedding_metadata(monkeypatch) -> None:
    import project.backend.search_engine.models as models

    class FakeResponse:
        def __init__(self, body):
            self.body = body

        def raise_for_status(self):
            return None

        def json(self):
            return self.body

    class FakeClient:
        response_body = {}

        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return FakeResponse(self.response_body)

    monkeypatch.setattr(models.httpx, "AsyncClient", FakeClient)
    client = ModelServerClient(base_url="http://model.test")
    FakeClient.response_body = {
        "embeddings": [[1.0, 0.0]],
        "model_id": "BAAI/bge-m3",
        "model_version": "bge-m3-cls-v1",
        "embedding_dimension": 2,
        "pooling_method": "cls",
    }
    batch = await client.embed(["text"])
    assert batch is not None
    assert batch.space.dimension == 2
    del FakeClient.response_body["pooling_method"]
    assert await client.embed(["text"]) is None


@pytest.mark.asyncio
async def test_query_encoder_uses_distinct_query_vectors_and_consistent_fallback_space() -> None:
    intent = SearchIntent(
        original_query="quiet cafe for study",
        objective="Find a cafe",
        rewritten_query="quiet cafe with outlets",
    )
    representation = await QueryEncoder().encode(
        intent,
        [Preference(attribute="noise", value="quiet", weight=1, confidence=1)],
        SearchContext(),
    )
    assert representation.original_embedding != representation.rewritten_embedding
    assert representation.original_vector.space == representation.personalized_vector.space
    assert representation.personalized_embedding != representation.rewritten_embedding


@pytest.mark.asyncio
async def test_preference_embedding_is_saved_with_its_space() -> None:
    space = EmbeddingSpace(
        model_id="BAAI/bge-m3",
        model_version="bge-m3-cls-v1",
        dimension=2,
        pooling_method="cls",
    )

    class Model:
        async def embed(self, texts):
            return EmbeddingBatch(space=space, embeddings=[[0.6, 0.8] for _ in texts])

    preference = Preference(attribute="noise", value="quiet")
    updated = await refresh_preference_embedding(preference, Model())
    assert updated.embedding == [0.6, 0.8]
    assert updated.embedding_space == space


def test_invalid_serpapi_configuration_never_selects_fixture_implicitly(monkeypatch) -> None:
    import project.backend.search_engine.pipeline as pipeline_module

    monkeypatch.setattr(
        pipeline_module,
        "get_settings",
        lambda: type("Settings", (), {
            "search_provider": "serpapi",
            "serpapi_api_key": None,
            "serp_api_key": None,
        })(),
    )
    with pytest.raises(RuntimeError, match="requires SERPAPI"):
        pipeline_module.default_provider()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "private_address",
    ["127.0.0.1", "::ffff:127.0.0.1", "64:ff9b::7f00:1", "2002:7f00:1::1"],
)
async def test_dns_rebinding_private_answer_is_rejected_before_connect(
    monkeypatch, private_address: str
) -> None:
    calls = []

    class Backend:
        async def connect_tcp(self, **kwargs):
            calls.append(kwargs)
            raise AssertionError("A rejected address must never be connected")

        async def sleep(self, _seconds):
            return None

    def private_dns_answer(*_args, **_kwargs):
        family = socket.AF_INET6 if ":" in private_address else socket.AF_INET
        return [
            (family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (private_address, 443))
        ]

    monkeypatch.setattr(socket, "getaddrinfo", private_dns_answer)
    with pytest.raises(ValueError, match="Private, loopback"):
        await PublicOnlyBackend(Backend()).connect_tcp("rebinding.example", 443)
    assert calls == []


@pytest.mark.asyncio
async def test_public_dns_answer_is_pinned_for_the_actual_connection(monkeypatch) -> None:
    calls = []

    class Backend:
        async def connect_tcp(self, **kwargs):
            calls.append(kwargs)
            return object()

        async def sleep(self, _seconds):
            return None

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", 443))
        ],
    )
    await PublicOnlyBackend(Backend()).connect_tcp("public.example", 443)
    assert calls[0]["host"] == "8.8.8.8"


@pytest.mark.asyncio
async def test_redirect_origin_robots_policy_is_checked_before_fetch(monkeypatch) -> None:
    import project.backend.search_engine.harness.evidence as evidence

    async def allow_host(_host):
        return None

    monkeypatch.setattr(evidence, "_validate_public_host", allow_host)
    requested: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.host == "first.example" and request.url.path == "/robots.txt":
            return httpx.Response(200, request=request, text="User-agent: *\nAllow: /\n")
        if request.url.host == "first.example":
            return httpx.Response(
                302,
                request=request,
                headers={"Location": "https://redirect.example/article"},
            )
        if request.url.path == "/robots.txt":
            return httpx.Response(200, request=request, text="User-agent: *\nDisallow: /article\n")
        return httpx.Response(200, request=request, text="should not fetch")

    def client_factory(timeout):
        return httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            timeout=timeout,
            follow_redirects=False,
        )

    with pytest.raises(ValueError, match="Robots policy disallows"):
        await fetch_public_html(
            "https://first.example/article", client_factory=client_factory
        )
    assert "https://redirect.example/article" not in requested

