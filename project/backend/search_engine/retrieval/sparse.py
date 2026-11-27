from __future__ import annotations

import math
import re
from collections import Counter

from project.backend.search_engine.schemas import SearchCandidate


_TOKEN_RE = re.compile(r"[\w]+", flags=re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Unicode-aware fallback tokenizer for Korean, English, and mixed text."""
    return [token.casefold() for token in _TOKEN_RE.findall(text) if len(token) > 1]


def bm25_scores(query: str, documents: list[SearchCandidate], k1: float = 1.5, b: float = 0.75) -> list[float]:
    query_terms = tokenize(query)
    tokenized = [tokenize(" ".join((d.title, d.snippet, d.content))) for d in documents]
    if not tokenized:
        return []
    lengths = [len(tokens) for tokens in tokenized]
    average_length = sum(lengths) / max(len(lengths), 1)
    document_frequency: Counter[str] = Counter()
    term_frequencies = [Counter(tokens) for tokens in tokenized]
    for tokens in tokenized:
        document_frequency.update(set(tokens))

    scores: list[float] = []
    count = len(tokenized)
    for frequency, length in zip(term_frequencies, lengths):
        score = 0.0
        for term in query_terms:
            tf = frequency[term]
            if not tf:
                continue
            df = document_frequency[term]
            inverse = math.log(1 + (count - df + 0.5) / (df + 0.5))
            denominator = tf + k1 * (1 - b + b * length / max(average_length, 1))
            score += inverse * tf * (k1 + 1) / denominator
        scores.append(score)
    return scores


def rank_bm25(query: str, documents: list[SearchCandidate]) -> list[SearchCandidate]:
    scores = bm25_scores(query, documents)
    ranked = sorted(zip(documents, scores), key=lambda pair: (-pair[1], pair[0].document_id))
    return [document for document, score in ranked if score > 0]
