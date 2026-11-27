from __future__ import annotations

from typing import Any, TypedDict

from project.backend.search_engine.schemas import (
    EmbeddingSpace,
    EmbeddingVector,
    Preference,
    SearchCandidate,
    SearchIntent,
    SearchRequest,
    SearchResponse,
)
from project.backend.search_engine.harness.budget import SearchBudget


class SearchState(TypedDict, total=False):
    checkpoint_callback: Any
    search_id: str
    user_id: str
    request: SearchRequest
    preferences: list[Preference]
    intent: SearchIntent
    selected_preferences: list[Preference]
    embedding_model_id: str | None
    embedding_space: EmbeddingSpace | None
    query_representation: Any
    dense_original_embedding: EmbeddingVector
    dense_personalized_embedding: EmbeddingVector
    candidates: list[SearchCandidate]
    rankings: dict[str, list[str]]
    fused_scores: dict[str, float]
    reranker_scores: dict[str, float]
    semantic_judgments: dict[str, dict[str, Any]]
    verified_results: list
    unverified_results: list
    excluded_result_count: int
    errors: list[str]
    warnings: list[str]
    trace: Any
    budget: SearchBudget
    executed_queries: list[str]
    next_queries: list[str]
    retry_reason: str | None
    status: str
    response: SearchResponse

