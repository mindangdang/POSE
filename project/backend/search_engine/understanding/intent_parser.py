from __future__ import annotations

import re
from typing import Protocol

from project.backend.search_engine.schemas import (
    Criterion,
    CriterionOperator,
    CriterionSource,
    Preference,
    SearchContext,
    SearchIntent,
)


class StructuredIntentClient(Protocol):
    async def parse_intent(
        self, query: str, context: SearchContext, preferences: list[Preference]
    ) -> SearchIntent: ...


_HARD_MARKERS = (
    "must", "only", "required", "require", "필수", "반드시", "꼭", "만 가능", "이상이어야",
)
_NEGATION_PATTERN = re.compile(
    r"(?:\bno\b|\bwithout\b|\bavoid\b|\bnot\b|제외|빼고|말고|없이|싫어)",
    re.IGNORECASE,
)
_NEGATION_PREFIX = re.compile(
    r"(?:\bwithout\b|\bavoid\b|\bno\b|\bnot\b|제외|빼고|말고|없이|싫어)\s+",
    re.IGNORECASE,
)
_FOLLOWING_REQUIREMENT = re.compile(
    r"\s+(?=(?:must\b|only\b|required\b|require\b|at least\b|필수|반드시|꼭))",
    re.IGNORECASE,
)
_ENTITY_TERMS = {
    "cafe": ("cafe", "카페"),
    "place": ("place", "장소", "갈 곳"),
    "article": ("article", "논문", "자료", "글"),
    "job": ("job", "채용", "일자리"),
    "product": ("product", "상품", "제품", "살 만한"),
    "repository": ("repository", "repo", "깃허브", "코드"),
}


def _split_query(query: str) -> list[str]:
    parts = re.split(r"(?:,|;|그리고|또는|and|or|but|하지만|인데|면서)", query, flags=re.I)
    return [part.strip(" .!?。") for part in parts if part.strip(" .!?。")]


def _is_explicit_hard(query: str, segment: str) -> bool:
    lowered = segment.lower()
    return bool(
        re.search(r"(?:must|only|필수|반드시|꼭|만|이상)", segment, flags=re.I)
    ) or any(marker in lowered for marker in _HARD_MARKERS)


def _as_criterion(segment: str, *, hard: bool, source: CriterionSource) -> Criterion:
    return Criterion(
        attribute="query_requirement",
        operator=CriterionOperator.SEMANTIC_MATCH,
        value=segment,
        weight=1.0 if hard else 0.7,
        confidence=1.0 if source == CriterionSource.EXPLICIT else 0.65,
        is_hard_constraint=hard,
        source=source,
    )


def _extract_typed_criteria(segment: str, *, hard: bool) -> list[Criterion]:
    text = segment.casefold()
    extracted: list[Criterion] = []
    rules = (
        (r"\b(?:quiet|calm|silent)\b|조용|차분", "noise_level", "quiet", CriterionOperator.SEMANTIC_MATCH),
        (r"\b(?:noisy|loud|rowdy)\b|시끄|소란", "noise_level", "loud", CriterionOperator.SEMANTIC_MATCH),
        (r"\b(?:power\s+)?outlets?\b|콘센트", "outlets", True, CriterionOperator.EQ),
        (r"\bremote\b|\bwork.from.home\b|원격|재택", "remote", True, CriterionOperator.EQ),
        (r"\b(?:accessible|step.free|wheelchair.accessible)\b|무장애|접근성", "accessibility", "accessible", CriterionOperator.SEMANTIC_MATCH),
    )
    for pattern, attribute, value, operator in rules:
        if re.search(pattern, text, flags=re.I):
            extracted.append(
                Criterion(
                    attribute=attribute,
                    operator=operator,
                    value=value,
                    weight=1.0 if hard else 0.85,
                    confidence=1.0,
                    is_hard_constraint=hard,
                    source=CriterionSource.EXPLICIT,
                )
            )
    return extracted


def _excluded_phrase(segment: str) -> str:
    patterns = (
        r"(?:\bwithout\b|\bavoid\b|\bno\b|\bnot\b)\s+(.+)$",
        r"(.+?)(?:\s+없이|\s+말고|\s+제외|\s+빼고)$",
    )
    for pattern in patterns:
        match = re.search(pattern, segment, flags=re.I)
        if match:
            return match.group(1).strip(" .,!?:")
    return segment.strip()


def _constraint_phrase(segment: str) -> str:
    value = re.sub(
        r"\b(?:must have|must be|must|only|required|require|at least)\b|필수|반드시|꼭|만 가능|이어야",
        " ",
        segment,
        flags=re.I,
    )
    return " ".join(value.split()).strip(" .,!?:") or segment


class DeterministicIntentParser:
    """Offline parser that preserves explicit constraints and never invents hard ones."""

    async def parse(
        self,
        query: str,
        context: SearchContext | None = None,
        preferences: list[Preference] | None = None,
    ) -> SearchIntent:
        context = context or SearchContext()
        preferences = preferences or []
        normalized = " ".join(query.split())
        segments = _split_query(normalized)
        exclusions: list[Criterion] = []
        criteria: list[Criterion] = []

        for segment in segments or [normalized]:
            if _NEGATION_PATTERN.search(segment):
                negative_match = _NEGATION_PREFIX.search(segment)
                negative_end = len(segment)
                if negative_match:
                    next_requirement = _FOLLOWING_REQUIREMENT.search(segment, negative_match.end())
                    if next_requirement:
                        negative_end = next_requirement.start()
                negative_segment = segment[:negative_end]
                excluded = _excluded_phrase(negative_segment)
                exclusions.append(
                    Criterion(
                        attribute="query_requirement",
                        operator=CriterionOperator.NEQ,
                        value=excluded,
                        weight=1.0,
                        confidence=1.0,
                        is_hard_constraint=True,
                        source=CriterionSource.EXPLICIT,
                    )
                )
                positive_remainder = segment[negative_end:].strip()
                if positive_remainder:
                    hard = _is_explicit_hard(normalized, positive_remainder)
                    typed = _extract_typed_criteria(positive_remainder, hard=hard)
                    criteria.extend(typed or [
                        _as_criterion(
                            _constraint_phrase(positive_remainder) if hard else positive_remainder,
                            hard=hard,
                            source=CriterionSource.EXPLICIT,
                        )
                    ])
            else:
                hard = _is_explicit_hard(normalized, segment)
                typed = _extract_typed_criteria(segment, hard=hard)
                criteria.extend(typed or [
                    _as_criterion(
                        _constraint_phrase(segment) if hard else segment,
                        hard=hard,
                        source=CriterionSource.EXPLICIT,
                    )
                ])

        entity = next(
            (
                name
                for name, terms in _ENTITY_TERMS.items()
                if any(term in normalized.lower() for term in terms)
            ),
            None,
        )
        unresolved: list[str] = []
        clarification = False
        requires_location = any(
            term in normalized.lower() for term in ("near me", "근처", "주변", "집 근처")
        )
        if requires_location:
            criteria.append(
                Criterion(
                    attribute="location",
                    operator=CriterionOperator.SEMANTIC_MATCH,
                    value=context.location or ("near me" if "near me" in normalized.lower() else "집 근처"),
                    weight=1.0,
                    confidence=1.0,
                    is_hard_constraint=True,
                    source=CriterionSource.EXPLICIT,
                )
            )
            if not context.location:
                unresolved.append("검색에 사용할 위치")
                clarification = True

        memory_terms = [p.value for p in preferences if p.polarity == "positive"]
        rewrite = normalized
        if context.location and requires_location:
            rewrite = re.sub(
                r"\bnear me\b|집 근처|근처|주변",
                context.location,
                rewrite,
                flags=re.IGNORECASE,
            )
        relevant_memory = [value for value in memory_terms if value.lower() in normalized.lower()]
        if relevant_memory:
            rewrite = f"{normalized} {' '.join(relevant_memory)}"

        criteria_attributes = {item.attribute for item in criteria}
        study_or_focus = any(
            marker in normalized.casefold()
            for marker in ("study", "studying", "focus", "work", "공부", "집중")
        )
        if study_or_focus and "noise_level" not in criteria_attributes and not re.search(
            r"\b(?:loud|noisy|busy)\b|시끄|소란", normalized, flags=re.I
        ):
            criteria.append(
                Criterion(
                    attribute="noise_level",
                    operator=CriterionOperator.SEMANTIC_MATCH,
                    value="quiet",
                    weight=0.8,
                    confidence=0.7,
                    is_hard_constraint=False,
                    source=CriterionSource.INFERRED,
                )
            )
        if study_or_focus and "seat_comfort" not in criteria_attributes and not re.search(
            r"\b(?:uncomfortable|hard seats?)\b|불편|딱딱한 의자", normalized, flags=re.I
        ):
            criteria.append(
                Criterion(
                    attribute="seat_comfort",
                    operator=CriterionOperator.SEMANTIC_MATCH,
                    value="comfortable",
                    weight=0.65,
                    confidence=0.55,
                    is_hard_constraint=False,
                    source=CriterionSource.INFERRED,
                )
            )

        queries = list(dict.fromkeys([rewrite, *segments]))[:3]
        objective = normalized
        return SearchIntent(
            original_query=query,
            objective=objective,
            target_entity=entity,
            rewritten_query=rewrite,
            criteria=criteria,
            exclusions=exclusions,
            sub_queries=queries,
            unresolved_information=unresolved,
            clarification_required=clarification,
        )
