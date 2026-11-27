from __future__ import annotations


import pytest
from pydantic import ValidationError

from project.backend.search_engine.harness.budget import SearchBudget
from project.backend.search_engine.harness.evidence import _validate_public_host
from project.backend.search_engine.ranking.constraints import evaluate_criterion
from project.backend.search_engine.ranking.utility_ranker import UtilityWeights, rank_candidates
from project.backend.search_engine.retrieval.fusion import weighted_reciprocal_rank_fusion
from project.backend.search_engine.retrieval.dense import cosine_similarity, hashing_embedding
from project.backend.search_engine.retrieval.sparse import bm25_scores
from project.backend.search_engine.schemas import (
    Criterion,
    SearchCandidate,
    SearchIntent,
)
from project.backend.search_engine.sources.urls import canonicalize_url, stable_document_id
from project.backend.search_engine.understanding.intent_parser import DeterministicIntentParser


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

def test_url_canonicalization_preserves_meaningful_parameters() -> None:
    canonical = canonicalize_url(
        "HTTPS://WWW.Example.org:443/article?id=7&utm_source=mail&lang=ko#section"
    )
    assert canonical == "https://example.org/article?id=7&lang=ko"
    assert stable_document_id(canonical) == stable_document_id(canonical)
    with pytest.raises(ValueError):
        canonicalize_url("https://user:password@example.org/private")

@pytest.mark.asyncio
async def test_evidence_host_guard_rejects_loopback_and_private_hosts() -> None:
    with pytest.raises(ValueError):
        await _validate_public_host("127.0.0.1")
    with pytest.raises(ValueError):
        await _validate_public_host("localhost")

@pytest.mark.asyncio
async def test_intent_parser_marks_explicit_exclusion_and_hard_condition() -> None:
    parsed = await DeterministicIntentParser().parse(
        "quiet study cafe and no loud music must have power outlets"
    )
    assert parsed.exclusions
    assert parsed.exclusions[0].is_hard_constraint is True
    assert any(item.is_hard_constraint for item in parsed.criteria)
    assert len(parsed.sub_queries) <= 3

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

def test_hashing_embedding_is_normalized_and_dimension_compatible() -> None:
    vector = hashing_embedding("quiet study cafe", dimension=128)
    assert len(vector) == 128
    assert sum(value * value for value in vector) == pytest.approx(1.0)
    assert cosine_similarity(vector, [1.0, 0.0]) == 0.0

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
