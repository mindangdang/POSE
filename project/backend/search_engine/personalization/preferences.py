from __future__ import annotations

import math
import re
from datetime import datetime, timezone

from project.backend.search_engine.schemas import (
    Criterion,
    CriterionOperator,
    CriterionSource,
    Preference,
    PreferenceScope,
    SearchContext,
    SearchIntent,
)

_SYNONYMS = {
    "quiet": {"quiet", "calm", "silent", "low-noise", "조용", "차분"},
    "comfortable": {"comfortable", "spacious", "ergonomic", "편안", "넓은"},
    "cheap": {"cheap", "affordable", "budget", "저렴", "가성비"},
    "accessible": {"accessible", "step-free", "wheelchair", "접근성", "무장애"},
    "remote": {"remote", "work-from-home", "원격", "재택"},
}
_ATTRIBUTE_CONTEXT_HINTS = {
    "accessibility": {"place", "cafe", "restaurant", "venue", "building", "hotel", "library"},
    "step_free": {"place", "cafe", "restaurant", "venue", "building", "hotel", "library"},
    "noise_level": {"place", "cafe", "restaurant", "venue", "building", "hotel", "library"},
    "seat_comfort": {"place", "cafe", "restaurant", "venue", "library"},
    "power": {"place", "cafe", "restaurant", "venue", "library", "office"},
}


def _terms(text: str) -> set[str]:
    terms = {word.casefold() for word in re.findall(r"[\w]+", text, flags=re.UNICODE) if len(word) > 1}
    for group in _SYNONYMS.values():
        if terms & group:
            terms.update(group)
    return terms


def preference_relevance(
    query: str,
    preference: Preference,
    context: SearchContext,
    semantic_similarity: float | None = None,
) -> float:
    query_terms = _terms(query)
    preference_terms = _terms(f"{preference.attribute} {preference.value}")
    if not query_terms or not preference_terms:
        return 0.0
    similarity = (
        max(0.0, min(1.0, semantic_similarity))
        if semantic_similarity is not None
        else len(query_terms & preference_terms) / math.sqrt(len(query_terms) * len(preference_terms))
    )
    contextual_terms = set().union(
        *(
            hints
            for attribute, hints in _ATTRIBUTE_CONTEXT_HINTS.items()
            if attribute in _terms(preference.attribute)
        )
    ) if preference.attribute else set()
    if query_terms & contextual_terms:
        similarity = max(similarity, 0.5)
    scope_weight = {
        PreferenceScope.SESSION: 1.0
        if context.session_id and (not preference.session_id or context.session_id == preference.session_id)
        else 0.0,
        PreferenceScope.DOMAIN: 1.0 if preference.domain == context.task_context else 0.35,
        PreferenceScope.GLOBAL: 0.8,
    }[preference.scope]
    decay = 1.0
    if preference.source.value == "inferred":
        age_days = max((datetime.now(timezone.utc) - preference.updated_at).days, 0)
        decay = math.exp(-age_days / 180.0)
    return similarity * preference.weight * preference.confidence * scope_weight * decay


def conflicts_with_intent(preference: Preference, intent: SearchIntent) -> bool:
    terms = _terms(f"{preference.attribute} {preference.value}")
    query = _terms(intent.original_query)
    preference_value_terms = _terms(preference.value)
    for criterion in [*intent.criteria, *intent.exclusions]:
        if (
            criterion.source.value == "explicit"
            and criterion.attribute.casefold() == preference.attribute.casefold()
            and not (preference_value_terms & _terms(str(criterion.value)))
        ):
            return True
    explicit = {
        term
        for criterion in [*intent.criteria, *intent.exclusions]
        if criterion.source.value == "explicit"
        for term in _terms(str(criterion.value))
    }
    if preference.polarity == "negative":
        return bool(terms & query) and bool(terms & explicit)
    opposites = (
        ({"quiet", "calm", "silent", "loud", "noisy", "시끄러운", "조용"}),
        ({"remote", "on-site", "onsite", "office", "재택", "출근"}),
        ({"cheap", "affordable", "expensive", "저렴", "비싼"}),
    )
    return any(
        bool(terms & group) and bool(query & group) and not bool(terms & query)
        for group in opposites
    )


def retrieve_relevant_preferences(
    query: str,
    preferences: list[Preference],
    context: SearchContext,
    intent: SearchIntent | None = None,
    limit: int = 5,
    semantic_similarities: dict[str, float] | None = None,
) -> list[Preference]:
    filtered = [
        item for item in preferences
        if item.scope != PreferenceScope.SESSION or bool(context.session_id)
    ]
    if intent:
        filtered = [item for item in filtered if not conflicts_with_intent(item, intent)]
    ranked = sorted(
        (
            (
                preference_relevance(
                    query,
                    item,
                    context,
                    (semantic_similarities or {}).get(item.id),
                ),
                item,
            )
            for item in filtered
        ),
        key=lambda pair: (-pair[0], pair[1].id),
    )
    return [item for score, item in ranked[:limit] if score > 0]


def merge_explicit_conditions(
    intent: SearchIntent, preferences: list[Preference]
) -> SearchIntent:
    """Explicit query criteria remain first; memory contributes soft criteria only."""
    known = {(c.attribute.casefold(), str(c.value).casefold()) for c in intent.criteria}
    explicit_attributes = {
        criterion.attribute.casefold(): _terms(str(criterion.value))
        for criterion in intent.criteria
        if criterion.source.value == "explicit"
    }
    additions: list[Criterion] = []
    for preference in preferences:
        key = (preference.attribute.casefold(), preference.value.casefold())
        if preference.polarity != "positive" or key in known:
            continue
        explicit_terms = explicit_attributes.get(preference.attribute.casefold())
        if explicit_terms and not (_terms(preference.value) & explicit_terms):
            continue
        additions.append(
            Criterion(
                attribute=preference.attribute,
                operator=CriterionOperator.SEMANTIC_MATCH,
                value=preference.value,
                weight=preference.weight,
                confidence=preference.confidence,
                is_hard_constraint=False,
                source=CriterionSource.USER_MEMORY,
            )
        )
    return intent.model_copy(update={"criteria": [*intent.criteria, *additions]})
