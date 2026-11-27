from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CriterionOperator(str, Enum):
    EQ = "eq"
    NEQ = "neq"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    CONTAINS = "contains"
    SEMANTIC_MATCH = "semantic_match"


class CriterionSource(str, Enum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"
    USER_MEMORY = "user_memory"
    SESSION_CONTEXT = "session_context"


class Criterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    attribute: str = Field(min_length=1, max_length=120)
    operator: CriterionOperator
    value: str | float | bool | list[str]
    weight: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    is_hard_constraint: bool = False
    source: CriterionSource


class SearchIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_query: str
    objective: str
    target_entity: str | None = None
    rewritten_query: str
    criteria: list[Criterion] = Field(default_factory=list)
    exclusions: list[Criterion] = Field(default_factory=list)
    sub_queries: list[str] = Field(default_factory=list, max_length=3)
    unresolved_information: list[str] = Field(default_factory=list)
    clarification_required: bool = False


class SearchContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    locale: str = "ko-KR"
    session_id: str | None = None
    location: str | None = None
    task_context: str | None = None
    criteria_overrides: list[Criterion] | None = None
    exclusion_overrides: list[Criterion] | None = None


class PreferenceScope(str, Enum):
    SESSION = "session"
    DOMAIN = "domain"
    GLOBAL = "global"


class PreferenceSource(str, Enum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"


class Preference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str | None = None
    attribute: str
    value: str
    polarity: Literal["positive", "negative"] = "positive"
    weight: float = Field(default=0.5, ge=0, le=1)
    confidence: float = Field(default=1.0, ge=0, le=1)
    scope: PreferenceScope = PreferenceScope.GLOBAL
    domain: str | None = None
    session_id: str | None = None
    source: PreferenceSource = PreferenceSource.EXPLICIT
    evidence_event_ids: list[str] = Field(default_factory=list)
    embedding: list[float] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SearchCandidate(BaseModel):
    model_config = ConfigDict(extra="allow")

    document_id: str
    canonical_url: str
    source_url: str
    title: str
    snippet: str = ""
    content: str = ""
    source: str = "unknown"
    document_type: str = "web_page"
    published_at: datetime | None = None
    fetched_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding_model: str | None = None
    embedding_version: str | None = None
    embedding: list[float] | None = None
    retrieval_ranks: dict[str, int] = Field(default_factory=dict)

    @field_validator("canonical_url", "source_url")
    @classmethod
    def safe_http_url(cls, value: str) -> str:
        if not value.startswith(("https://", "http://")):
            raise ValueError("Only HTTP(S) URLs are supported")
        return value


class CriterionEvaluation(BaseModel):
    criterion_id: str
    document_id: str
    status: Literal["satisfied", "violated", "unknown"]
    confidence: float = Field(ge=0, le=1)
    evidence_excerpt: str | None = None
    evidence_url: str | None = None
    evidence_type: Literal["metadata", "content", "snippet", "none"] = "none"


class RankingFeatures(BaseModel):
    query_relevance: float = Field(ge=0, le=1)
    preference_compatibility: float = Field(ge=0, le=1)
    constraint_satisfaction: float = Field(ge=0, le=1)
    evidence_quality: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1)


class SearchResult(BaseModel):
    document: SearchCandidate
    rank: int
    score: float = Field(ge=0, le=1)
    verified: bool
    reason: str
    satisfied_criteria: list[str] = Field(default_factory=list)
    uncertain_criteria: list[str] = Field(default_factory=list)
    evaluations: list[CriterionEvaluation] = Field(default_factory=list)
    features: RankingFeatures


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None
    personalization_enabled: bool = True
    limit: int = Field(default=10, ge=1, le=10)
    context: SearchContext = Field(default_factory=SearchContext)


class SearchResponse(BaseModel):
    search_id: str
    status: Literal["queued", "running", "completed", "partial", "cancelled", "failed", "clarification_required"]
    intent: SearchIntent | None = None
    preferences_used: list[str] = Field(default_factory=list)
    verified_results: list[SearchResult] = Field(default_factory=list)
    unverified_results: list[SearchResult] = Field(default_factory=list)
    excluded_result_count: int = 0
    tool_calls: int = 0
    errors: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None


class FeedbackType(str, Enum):
    RESULT_CLICK = "RESULT_CLICK"
    RESULT_SAVE = "RESULT_SAVE"
    RESULT_DISMISS = "RESULT_DISMISS"
    RESULT_LIKE = "RESULT_LIKE"
    RESULT_DISLIKE = "RESULT_DISLIKE"
    CRITERION_CORRECTION = "CRITERION_CORRECTION"
    PREFERENCE_UPDATE = "PREFERENCE_UPDATE"


class SearchFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1, max_length=200)
    search_id: str
    document_id: str | None = None
    original_rank: int | None = Field(default=None, ge=1)
    feedback_type: FeedbackType
    feedback_reason: str | None = None
    affected_criterion: str | None = None
    feedback_scope: Literal["session", "related_searches"] = "session"
    preference: Preference | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def explicit_preference_for_learning(self) -> "SearchFeedback":
        if self.feedback_type == FeedbackType.PREFERENCE_UPDATE and self.preference is None:
            raise ValueError("PREFERENCE_UPDATE requires an explicit preference")
        return self

