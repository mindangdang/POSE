from __future__ import annotations

from dataclasses import dataclass

from project.backend.search_engine.personalization.preferences import preference_relevance
from project.backend.search_engine.retrieval.dense import hashing_embedding
from project.backend.search_engine.schemas import Preference, SearchContext, SearchIntent


@dataclass
class QueryRepresentation:
    original_embedding: list[float]
    personalized_embedding: list[float]
    selected_preferences: list[Preference]
    model_id: str = "pose-hashing-fallback-v1"


class QueryEncoder:
    """Training-free encoder interface, replaceable by BGE-M3 or a learned tower."""

    def __init__(self, temperature: float = 0.2, personalization_lambda: float = 0.25, dimension: int = 256):
        self.temperature = temperature
        self.personalization_lambda = personalization_lambda
        self.dimension = dimension

    async def encode(
        self,
        query: SearchIntent,
        preferences: list[Preference],
        context: SearchContext | None = None,
        query_embedding: list[float] | None = None,
        semantic_similarities: dict[str, float] | None = None,
    ) -> QueryRepresentation:
        context = context or SearchContext()
        base = (
            query_embedding
            if query_embedding is not None
            else hashing_embedding(query.rewritten_query, self.dimension)
        )
        dimension = len(base)
        weighted = [
            (
                preference_relevance(
                    query.rewritten_query,
                    preference,
                    context,
                    (semantic_similarities or {}).get(preference.id),
                ),
                preference,
            )
            for preference in preferences
            if preference.polarity == "positive"
        ]
        weighted = sorted(weighted, key=lambda pair: -pair[0])[:5]
        if not weighted or max((score for score, _ in weighted), default=0.0) <= 0:
            return QueryRepresentation(base, base, [])
        peak = max(score / self.temperature for score, _ in weighted)
        exponentials = [pow(2.718281828, score / self.temperature - peak) for score, _ in weighted]
        normalizer = sum(exponentials) or 1.0
        weights = [value / normalizer for value in exponentials]
        preference_vector = [0.0] * dimension
        for weight, (_, preference) in zip(weights, weighted):
            vector = preference.embedding
            if vector is None or len(vector) != dimension:
                vector = hashing_embedding(f"{preference.attribute} {preference.value}", dimension)
            for index, value in enumerate(vector):
                preference_vector[index] += weight * value
        combined = [q + self.personalization_lambda * p for q, p in zip(base, preference_vector)]
        norm = sum(value * value for value in combined) ** 0.5
        personalized = [value / norm for value in combined] if norm else base
        return QueryRepresentation(
            original_embedding=base,
            personalized_embedding=personalized,
            selected_preferences=[preference for _, preference in weighted],
        )
