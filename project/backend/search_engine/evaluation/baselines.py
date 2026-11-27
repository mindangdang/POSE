from __future__ import annotations

from project.backend.search_engine.personalization.encoder import QueryEncoder
from project.backend.search_engine.personalization.preferences import retrieve_relevant_preferences
from project.backend.search_engine.retrieval.dense import dense_scores, hashing_embedding
from project.backend.search_engine.retrieval.fusion import weighted_reciprocal_rank_fusion
from project.backend.search_engine.retrieval.sparse import bm25_scores


def _order(documents, scores):
    return [
        item.document_id
        for item, score in sorted(
            zip(documents, scores),
            key=lambda pair: (-pair[1], pair[0].document_id),
        )
    ]


async def baseline_rankings(query, documents, preferences, context):
    intent = await __import__(
        "project.backend.search_engine.understanding.intent_parser",
        fromlist=["DeterministicIntentParser"],
    ).DeterministicIntentParser().parse(query, context, preferences)
    external = [
        item.document_id
        for item in await __import__(
            "project.backend.search_engine.sources.fixture",
            fromlist=["FixtureSearchProvider"],
        ).FixtureSearchProvider().search(query, 50, context)
    ]
    sparse = _order(documents, bm25_scores(query, documents))
    dense = _order(documents, dense_scores(hashing_embedding(query), documents))
    hybrid = weighted_reciprocal_rank_fusion(
        {"external": external, "sparse": sparse, "dense": dense},
        {"external": 0.3125, "sparse": 0.3125, "dense": 0.375},
        personalized_enabled=False,
    )
    b3 = sorted(hybrid, key=lambda item: (-hybrid[item], item))
    rewritten = _order(documents, bm25_scores(intent.rewritten_query, documents))
    rewritten_hybrid = weighted_reciprocal_rank_fusion(
        {"external": external, "sparse": rewritten, "dense": dense},
        {"external": 0.3125, "sparse": 0.3125, "dense": 0.375},
        personalized_enabled=False,
    )
    b4 = sorted(rewritten_hybrid, key=lambda item: (-rewritten_hybrid[item], item))
    selected = retrieve_relevant_preferences(query, preferences, context, limit=5)
    representation = await QueryEncoder().encode(intent, selected, context)
    b7 = _order(documents, dense_scores(representation.personalized_embedding, documents))
    positive = [item for item in preferences if item.polarity == "positive"]
    static_text = " ".join(f"{item.attribute} {item.value}" for item in positive)
    static = hashing_embedding(static_text or query)
    b6 = _order(documents, dense_scores(static, documents))
    return {
        "B0_external": external,
        "B1_bm25": sparse,
        "B2_dense": dense,
        "B3_hybrid": b3,
        "B4_rewrite_hybrid": b4,
        "B5_reranker_fallback": b3,
        "B6_static_user_vector": b6,
        "B7_query_conditioned": b7,
    }
