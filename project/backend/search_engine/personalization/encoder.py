from __future__ import annotations

from dataclasses import dataclass
from math import exp, sqrt

from project.backend.search_engine.personalization.preferences import preference_relevance
from project.backend.search_engine.retrieval.dense import hashing_embedding
from project.backend.search_engine.schemas import (
    EmbeddingSpace,
    EmbeddingVector,
    Preference,
    SearchContext,
    SearchIntent,
)


@dataclass
class QueryRepresentation:
    original_embedding: list[float]
    rewritten_embedding: list[float]
    personalized_embedding: list[float]
    space: EmbeddingSpace
    selected_preferences: list[Preference]

    @property
    def original_vector(self) -> EmbeddingVector:
        return EmbeddingVector(space=self.space, values=self.original_embedding)

    @property
    def rewritten_vector(self) -> EmbeddingVector:
        return EmbeddingVector(space=self.space, values=self.rewritten_embedding)

    @property
    def personalized_vector(self) -> EmbeddingVector:
        return EmbeddingVector(space=self.space, values=self.personalized_embedding)


class QueryEncoder:
    """One query-conditioning algorithm for model and hashing embedding spaces."""

    FALLBACK_SPACE = EmbeddingSpace(
        model_id="pose-hashing-fallback-v1",
        model_version="v1",
        dimension=256,
        pooling_method="hashing",
    )

    def __init__(
        self,
        temperature: float = 0.2,
        personalization_lambda: float = 0.25,
        dimension: int = 256,
    ):
        self.temperature = temperature
        self.personalization_lambda = personalization_lambda
        self.dimension = dimension

    def _weights(self, items: list[tuple[float, Preference]]) -> list[float]:
        if not items:
            return []
        logits = [score / self.temperature for score, _ in items]
        peak = max(logits)
        values = [exp(value - peak) for value in logits]
        denominator = sum(values) or 1.0
        return [value / denominator for value in values]

    async def encode(
        self,
        query: SearchIntent,
        preferences: list[Preference],
        context: SearchContext | None = None,
        query_embedding: list[float] | None = None,
        semantic_similarities: dict[str, float] | None = None,
        *,
        original_query_embedding: list[float] | None = None,
        rewritten_query_embedding: list[float] | None = None,
        embedding_space: EmbeddingSpace | None = None,
    ) -> QueryRepresentation:
        context = context or SearchContext()
        legacy_vector = query_embedding
        if rewritten_query_embedding is None and legacy_vector is not None:
            rewritten_query_embedding = legacy_vector
        if embedding_space is None and (rewritten_query_embedding or original_query_embedding):
            vector = rewritten_query_embedding or original_query_embedding or []
            embedding_space = EmbeddingSpace(
                model_id="legacy-unversioned",
                model_version="legacy-unversioned",
                dimension=len(vector),
                pooling_method="unknown",
            )
        if embedding_space is None:
            embedding_space = EmbeddingSpace(
                model_id=self.FALLBACK_SPACE.model_id,
                model_version=self.FALLBACK_SPACE.model_version,
                dimension=self.dimension,
                pooling_method=self.FALLBACK_SPACE.pooling_method,
            )

        # If either side came from a different backend, discard both model
        # vectors and use one complete hashing space for this retrieval channel.
        if (
            embedding_space.model_id == "legacy-unversioned"
            and original_query_embedding is None
            and rewritten_query_embedding is not None
        ):
            original_query_embedding = rewritten_query_embedding
        if (
            (original_query_embedding is not None and len(original_query_embedding) != embedding_space.dimension)
            or (rewritten_query_embedding is not None and len(rewritten_query_embedding) != embedding_space.dimension)
        ):
            embedding_space = EmbeddingSpace(
                model_id=self.FALLBACK_SPACE.model_id,
                model_version=self.FALLBACK_SPACE.model_version,
                dimension=self.dimension,
                pooling_method=self.FALLBACK_SPACE.pooling_method,
            )
            original_query_embedding = None
            rewritten_query_embedding = None

        original = original_query_embedding or hashing_embedding(query.original_query, embedding_space.dimension)
        rewritten = rewritten_query_embedding or hashing_embedding(query.rewritten_query, embedding_space.dimension)
        if not preferences:
            return QueryRepresentation(original, rewritten, rewritten, embedding_space, [])

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
        ]
        weighted = sorted(weighted, key=lambda pair: -pair[0])[:5]
        weighted = [(score, item) for score, item in weighted if score > 0]
        compatible = [
            (score, item)
            for score, item in weighted
            if item.embedding is not None
            and item.embedding_space == embedding_space
            and len(item.embedding) == embedding_space.dimension
        ]
        if embedding_space.pooling_method == "hashing":
            compatible = weighted
        if not compatible:
            return QueryRepresentation(original, rewritten, rewritten, embedding_space, [])

        preference_vector = [0.0] * embedding_space.dimension
        for polarity in ("positive", "negative"):
            group = [(score, item) for score, item in compatible if item.polarity == polarity]
            group_weights = self._weights(group)
            polarity_sign = 1.0 if polarity == "positive" else -1.0
            for weight, (_, item) in zip(group_weights, group):
                preference_values = item.embedding
                if preference_values is None or item.embedding_space != embedding_space:
                    preference_values = hashing_embedding(
                        f"{item.attribute} {item.value}", embedding_space.dimension
                    )
                for index, value in enumerate(preference_values):
                    preference_vector[index] += polarity_sign * weight * value

        combined = [
            q + self.personalization_lambda * p
            for q, p in zip(rewritten, preference_vector)
        ]
        norm = sqrt(sum(value * value for value in combined))
        personalized = [value / norm for value in combined] if norm else rewritten
        return QueryRepresentation(
            original_embedding=original,
            rewritten_embedding=rewritten,
            personalized_embedding=personalized,
            space=embedding_space,
            selected_preferences=[item for _, item in compatible],
        )
