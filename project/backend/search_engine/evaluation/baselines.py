from __future__ import annotations

import math

from project.backend.search_engine.personalization.encoder import QueryEncoder
from project.backend.search_engine.personalization.preferences import retrieve_relevant_preferences
from project.backend.search_engine.retrieval.dense import dense_scores, hashing_embedding
from project.backend.search_engine.retrieval.fusion import weighted_reciprocal_rank_fusion
from project.backend.search_engine.retrieval.sparse import bm25_scores
from project.backend.search_engine.schemas import (
    EmbeddingVector,
    Preference,
    SearchCandidate,
    SearchContext,
    SearchIntent,
)
from project.backend.search_engine.sources.fixture import FixtureSearchProvider
from project.backend.search_engine.understanding.intent_parser import DeterministicIntentParser


def _order(documents: list[SearchCandidate], scores: list[float]) -> list[str]:
    return [
        item.document_id
        for item, score in sorted(
            zip(documents, scores),
            key=lambda pair: (-pair[1], pair[0].document_id),
        )
    ]


def _normalized(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in values))
    return [value / norm for value in values] if norm else values


async def baseline_rankings(
    query: str,
    documents: list[SearchCandidate],
    preferences: list[Preference],
    context: SearchContext,
    cross_encoder_scores: dict[str, float] | None = None,
) -> dict[str, list[str]]:
    intent = await DeterministicIntentParser().parse(query, context, preferences)
    external = [
        item.document_id
        for item in await FixtureSearchProvider().search(query, 50, context)
    ]
    sparse = _order(documents, bm25_scores(query, documents))
    dense = _order(documents, dense_scores(
        EmbeddingVector(
            space=QueryEncoder.FALLBACK_SPACE,
            values=hashing_embedding(query, QueryEncoder.FALLBACK_SPACE.dimension),
        ),
        documents,
    ))
    hybrid_scores = weighted_reciprocal_rank_fusion(
        {"external": external, "sparse": sparse, "dense": dense},
        {"external": 0.3125, "sparse": 0.3125, "dense": 0.375},
        personalized_enabled=False,
    )
    hybrid = sorted(hybrid_scores, key=lambda item: (-hybrid_scores[item], item))
    rewritten = _order(documents, bm25_scores(intent.rewritten_query, documents))
    rewritten_scores = weighted_reciprocal_rank_fusion(
        {"external": external, "sparse": rewritten, "dense": dense},
        {"external": 0.3125, "sparse": 0.3125, "dense": 0.375},
        personalized_enabled=False,
    )
    rewritten_hybrid = sorted(rewritten_scores, key=lambda item: (-rewritten_scores[item], item))

    # B6/B7 deliberately share the same query text, corpus, dense retrieval
    # channel, and document ordering. Only the user representation changes.
    representation_query = SearchIntent(
        original_query=query,
        objective="Retrieval baseline",
        rewritten_query=query,
    )
    query_values = hashing_embedding(query, QueryEncoder.FALLBACK_SPACE.dimension)
    profile_values = [0.0] * QueryEncoder.FALLBACK_SPACE.dimension
    for preference in preferences:
        sign = 1.0 if preference.polarity == "positive" else -1.0
        values = hashing_embedding(
            f"{preference.attribute} {preference.value}",
            QueryEncoder.FALLBACK_SPACE.dimension,
        )
        weight = preference.weight * preference.confidence * sign
        for index, value in enumerate(values):
            profile_values[index] += weight * value
    static_values = _normalized(
        [query_value + 0.25 * user_value for query_value, user_value in zip(query_values, profile_values)]
    )
    static_query = EmbeddingVector(space=QueryEncoder.FALLBACK_SPACE, values=static_values)
    static_order = _order(documents, dense_scores(static_query, documents))

    selected = retrieve_relevant_preferences(query, preferences, context, limit=5)
    contextual = await QueryEncoder().encode(representation_query, selected, context)
    conditioned_order = _order(documents, dense_scores(contextual.personalized_vector, documents))

    baselines = {
        "B0_external": external,
        "B1_bm25": sparse,
        "B2_dense": dense,
        "B3_hybrid": hybrid,
        "B4_rewrite_hybrid": rewritten_hybrid,
        "B6_static_user_vector": static_order,
        "B7_query_conditioned": conditioned_order,
    }
    if cross_encoder_scores is not None:
        baselines["B5_cross_encoder"] = sorted(
            (item.document_id for item in documents),
            key=lambda document_id: (-cross_encoder_scores.get(document_id, float("-inf")), document_id),
        )
    return baselines
