from __future__ import annotations

import hashlib
import math
from collections import Counter

from project.backend.search_engine.schemas import SearchCandidate


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


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


def dense_scores(query_embedding: list[float], documents: list[SearchCandidate]) -> list[float]:
    return [
        cosine_similarity(
            query_embedding,
            document.embedding
            if document.embedding is not None and len(document.embedding) == len(query_embedding)
            else hashing_embedding(" ".join((document.title, document.snippet, document.content)), len(query_embedding)),
        )
        for document in documents
    ]
