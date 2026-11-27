from __future__ import annotations

import hashlib
import math
from collections import Counter

from project.backend.search_engine.schemas import EmbeddingSpace, EmbeddingVector, SearchCandidate


def hashing_embedding(text: str, dimension: int = 256) -> list[float]:
    """Stable dependency-free embedding fallback; model vectors can replace it."""
    vector = [0.0] * dimension
    for token, count in Counter(text.casefold().split()).items():
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest, "big") % dimension
        sign = 1.0 if digest[0] & 1 else -1.0
        vector[index] += sign * min(count, 3)
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def cosine_similarity(
    left: list[float] | EmbeddingVector,
    right: list[float] | EmbeddingVector,
) -> float:
    if isinstance(left, EmbeddingVector) and isinstance(right, EmbeddingVector):
        if left.space != right.space:
            raise ValueError("Cosine similarity requires vectors from the same embedding space")
        left, right = left.values, right.values
    elif isinstance(left, EmbeddingVector) or isinstance(right, EmbeddingVector):
        raise ValueError("Cannot compare a metadata-bearing embedding with an untyped vector")
    if len(left) != len(right) or not left:
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


def dense_scores(
    query_embedding: list[float] | EmbeddingVector,
    documents: list[SearchCandidate],
) -> list[float]:
    query_values = query_embedding.values if isinstance(query_embedding, EmbeddingVector) else query_embedding
    query_space = query_embedding.space if isinstance(query_embedding, EmbeddingVector) else None
    scores: list[float] = []
    for document in documents:
        if query_space is not None and query_space.pooling_method == "hashing":
            # Hash every side of this retrieval channel. Cached model vectors are ignored.
            document_vector = hashing_embedding(
                " ".join((document.title, document.snippet, document.content)),
                query_space.dimension,
            )
            scores.append(cosine_similarity(query_values, document_vector))
            continue
        if document.embedding is None or len(document.embedding) != len(query_values):
            scores.append(0.0)
            continue
        if query_space is not None:
            if not all((document.embedding_model, document.embedding_version, document.embedding_pooling_method)):
                scores.append(0.0)
                continue
            assert document.embedding_model is not None
            assert document.embedding_version is not None
            assert document.embedding_pooling_method is not None
            document_space = EmbeddingSpace(
                model_id=document.embedding_model,
                model_version=document.embedding_version,
                dimension=document.embedding_dimension or len(document.embedding),
                pooling_method=document.embedding_pooling_method,
            )
            if document_space != query_space:
                scores.append(0.0)
                continue
            scores.append(
                cosine_similarity(
                    EmbeddingVector(space=query_space, values=query_values),
                    EmbeddingVector(space=document_space, values=document.embedding),
                )
            )
        else:
            scores.append(cosine_similarity(query_values, document.embedding))
    return scores
