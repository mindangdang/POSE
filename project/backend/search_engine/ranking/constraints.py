from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from project.backend.search_engine.schemas import (
    ConditionEvaluation,
    ConditionExpression,
    Criterion,
    CriterionEvaluation,
    CriterionOperator,
    CriterionValueType,
    SearchCandidate,
)


class SemanticJudgment(BaseModel):
    """A structured judgment from an optional, bounded NLI/LLM adapter."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["satisfied", "violated", "unknown"]
    confidence: float = Field(ge=0, le=1)
    evidence_quote: str | None = None


class SemanticEvaluator(Protocol):
    async def evaluate(self, criterion: Criterion, evidence: str) -> SemanticJudgment: ...


_MISSING = {"", "unknown", "unspecified", "not provided", "n/a", "null", "알 수 없음", "미정"}
_EN_NEGATION = re.compile(
    r"(?<!\w)(?:no|without|free\s+of|does\s+not(?:\s+have)?|doesn't(?:\s+have)?|not(?!\s+only\b))\s+(?:any\s+|a\s+|an\s+)?",
    re.IGNORECASE,
)
_KO_NEGATION_BEFORE = re.compile(
    r"(?:없이|없음|없는|없다|없습니다|아니(?:다|에요|요)?|않(?:다|은|고|아요|습니다)|못하(?:다|는|고))\s*"
)
_KO_NEGATION_AFTER = re.compile(
    r"(?:이|가|은|는|을|를)?\s*(?:없(?:다|어요|습니다|음|는)|아니(?:다|에요|요)?|"
    r"하지\s*않(?:다|은|고|아요|습니다)|지\s*않(?:다|은|고|아요|습니다))"
)
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ].*)?$")


def _source_text(document: SearchCandidate) -> str:
    return "\n".join(part for part in (document.title, document.snippet, document.content) if part)


def _quote_from_source(quote: str, source: str) -> str | None:
    """Return the exact source substring matching quote, or None."""
    if not quote:
        return None
    index = source.casefold().find(quote.casefold())
    return source[index : index + len(quote)] if index >= 0 else None


def _evaluation(
    criterion: Criterion,
    document: SearchCandidate,
    status: Literal["satisfied", "violated", "unknown"],
    *,
    confidence: float = 0.0,
    quote: str | None = None,
    evidence_type: Literal["metadata", "content", "snippet", "none"] = "none",
) -> CriterionEvaluation:
    source = _source_text(document)
    checked_quote = _quote_from_source(quote, source) if quote else None
    if quote and checked_quote is None:
        status, confidence, evidence_type = "unknown", 0.0, "none"
    return CriterionEvaluation(
        criterion_id=criterion.id,
        document_id=document.document_id,
        status=status,
        confidence=confidence,
        evidence_excerpt=checked_quote,
        evidence_url=document.canonical_url if checked_quote or evidence_type == "metadata" else None,
        evidence_type=evidence_type if checked_quote or evidence_type == "metadata" else "none",
    )


def _parse_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "yes", "1", "예", "맞음", "가능", "있음"}:
            return True
        if normalized in {"false", "no", "0", "아니오", "아님", "불가", "없음"}:
            return False
    return None


def _parse_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not _ISO_DATE.fullmatch(value.strip()):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None


def _compare_ordered(left: object, right: object, operator: CriterionOperator) -> bool | None:
    if isinstance(left, bool) or isinstance(right, bool):
        return None
    left_text, right_text = str(left).strip(), str(right).strip()
    if _ISO_DATE.fullmatch(left_text) or _ISO_DATE.fullmatch(right_text):
        left_date, right_date = _parse_date(left), _parse_date(right)
        if left_date is None or right_date is None:
            return None
        return {
            CriterionOperator.GT: left_date > right_date,
            CriterionOperator.GTE: left_date >= right_date,
            CriterionOperator.LT: left_date < right_date,
            CriterionOperator.LTE: left_date <= right_date,
        }[operator]
    else:
        try:
            left_number, right_number = float(left_text), float(right_text)
        except (TypeError, ValueError):
            return None
    return {
        CriterionOperator.GT: left_number > right_number,
        CriterionOperator.GTE: left_number >= right_number,
        CriterionOperator.LT: left_number < right_number,
        CriterionOperator.LTE: left_number <= right_number,
    }[operator]


def _parse_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _value_type(criterion: Criterion) -> CriterionValueType:
    if criterion.value_type != CriterionValueType.AUTO:
        return criterion.value_type
    if criterion.operator == CriterionOperator.SEMANTIC_MATCH:
        return CriterionValueType.SEMANTIC
    if isinstance(criterion.value, bool):
        return CriterionValueType.BOOLEAN
    if isinstance(criterion.value, (int, float)):
        return CriterionValueType.NUMERIC
    if isinstance(criterion.value, str) and _ISO_DATE.fullmatch(criterion.value.strip()):
        return CriterionValueType.DATE
    return CriterionValueType.ENUM


def _negative_quote(value: str, content: str) -> str | None:
    if not value:
        return None
    # Match explicit English negation immediately before the requested phrase.
    pattern = re.compile(
        rf"{_EN_NEGATION.pattern}{re.escape(value)}",
        re.IGNORECASE,
    )
    match = pattern.search(content)
    if match:
        return match.group(0)
    # Korean commonly places the predicate after its object (e.g. "소음이 없습니다").
    pattern = re.compile(rf"{re.escape(value)}\s*{_KO_NEGATION_AFTER.pattern}", re.IGNORECASE)
    match = pattern.search(content)
    if match:
        return match.group(0)
    # Also cover adjective negation before a phrase ("조용하지 않은 카페").
    pattern = re.compile(rf"{_KO_NEGATION_BEFORE.pattern}{re.escape(value)}", re.IGNORECASE)
    match = pattern.search(content)
    return match.group(0) if match else None


def _metadata_value(document: SearchCandidate, attribute: str) -> object | None:
    if attribute in document.metadata:
        return document.metadata[attribute]
    return next(
        (value for key, value in document.metadata.items() if key.casefold() == attribute.casefold()),
        None,
    )


def evaluate_criterion(
    criterion: Criterion,
    document: SearchCandidate,
    semantic_judgment: SemanticJudgment | None = None,
) -> CriterionEvaluation:
    """Evaluate typed facts deterministically; semantic text requires a validated judge quote."""
    expected = criterion.value
    operator = criterion.operator
    value_type = _value_type(criterion)
    metadata = _metadata_value(document, criterion.attribute)
    if metadata is not None:
        status: Literal["satisfied", "violated", "unknown"]
        if isinstance(metadata, str) and metadata.strip().casefold() in _MISSING:
            return _evaluation(criterion, document, "unknown")
        if operator in {CriterionOperator.GT, CriterionOperator.GTE, CriterionOperator.LT, CriterionOperator.LTE}:
            comparison = _compare_ordered(metadata, expected, operator)
            if comparison is None:
                return _evaluation(criterion, document, "unknown")
            status = "satisfied" if comparison else "violated"
        elif value_type == CriterionValueType.BOOLEAN:
            actual_bool = _parse_bool(metadata)
            if actual_bool is None:
                return _evaluation(criterion, document, "unknown")
            equal = actual_bool is expected
            status = "satisfied" if (equal if operator != CriterionOperator.NEQ else not equal) else "violated"
        elif value_type in {CriterionValueType.NUMERIC, CriterionValueType.DATE}:
            if value_type == CriterionValueType.NUMERIC:
                actual_value, expected_value = _parse_number(metadata), _parse_number(expected)
                if actual_value is None or expected_value is None:
                    return _evaluation(criterion, document, "unknown")
                equal = actual_value == expected_value
            else:
                actual_date, expected_date = _parse_date(metadata), _parse_date(expected)
                if actual_date is None or expected_date is None:
                    return _evaluation(criterion, document, "unknown")
                equal = actual_date == expected_date
            satisfied = not equal if operator == CriterionOperator.NEQ else equal
            status = "satisfied" if satisfied else "violated"
        else:
            expected_text = str(expected).strip().casefold()
            if isinstance(metadata, list):
                equal = any(str(item).strip().casefold() == expected_text for item in metadata)
                contains = any(expected_text in str(item).casefold() for item in metadata)
            else:
                actual_text = str(metadata).strip().casefold()
                equal = actual_text == expected_text
                contains = expected_text in actual_text
            if operator == CriterionOperator.NEQ:
                satisfied = not equal
            elif operator == CriterionOperator.CONTAINS:
                satisfied = contains
            elif operator == CriterionOperator.SEMANTIC_MATCH:
                # Structured metadata is an authoritative fact only on exact match.
                satisfied = equal
            else:
                satisfied = equal
            status = "satisfied" if satisfied else "violated"
        return CriterionEvaluation(
            criterion_id=criterion.id,
            document_id=document.document_id,
            status=status,
            confidence=1.0,
            evidence_excerpt=f"{criterion.attribute}: {metadata}",
            evidence_url=document.canonical_url,
            evidence_type="metadata",
        )

    source = _source_text(document)
    content = source.casefold()
    normalized_value = " ".join(str(expected).casefold().split())
    if operator == CriterionOperator.SEMANTIC_MATCH:
        if semantic_judgment is None:
            negative = _negative_quote(normalized_value, content)
            if negative:
                return _evaluation(
                    criterion,
                    document,
                    "violated",
                    confidence=0.8,
                    quote=_quote_from_source(negative, source),
                    evidence_type="content" if document.content else "snippet",
                )
            return _evaluation(criterion, document, "unknown")
        quote = semantic_judgment.evidence_quote
        if not quote or _quote_from_source(quote, source) is None:
            return _evaluation(criterion, document, "unknown")
        return _evaluation(
            criterion,
            document,
            semantic_judgment.status,
            confidence=semantic_judgment.confidence,
            quote=quote,
            evidence_type="content" if document.content else "snippet",
        )

    value = normalized_value
    if not value or not source:
        return _evaluation(criterion, document, "unknown")
    exact_index = content.find(value)
    if operator == CriterionOperator.NEQ:
        if exact_index < 0:
            return _evaluation(criterion, document, "unknown")
        quote = _negative_quote(value, content)
        if quote:
            raw_quote = _quote_from_source(quote, source)
            return _evaluation(
                criterion,
                document,
                "satisfied",
                confidence=0.8,
                quote=raw_quote,
                evidence_type="content" if document.content else "snippet",
            )
        return _evaluation(
            criterion,
            document,
            "violated",
            confidence=0.8,
            quote=_quote_from_source(value, source),
            evidence_type="content" if document.content else "snippet",
        )

    if exact_index < 0:
        return _evaluation(criterion, document, "unknown")
    quote = _quote_from_source(value, source)
    negative = _negative_quote(value, content)
    if negative:
        return _evaluation(
            criterion,
            document,
            "violated",
            confidence=0.8,
            quote=_quote_from_source(negative, source),
            evidence_type="content" if document.content else "snippet",
        )
    if operator == CriterionOperator.CONTAINS:
        return _evaluation(
            criterion,
            document,
            "satisfied",
            confidence=0.8,
            quote=quote,
            evidence_type="content" if document.content else "snippet",
        )
    return _evaluation(criterion, document, "unknown")


def assess_candidate(
    document: SearchCandidate,
    criteria: list[Criterion],
    exclusions: list[Criterion],
    semantic_judgments: dict[str, dict[str, SemanticJudgment]] | None = None,
) -> tuple[list[CriterionEvaluation], bool, bool]:
    all_criteria = [*criteria, *exclusions]
    evaluations = [
        evaluate_criterion(
            item,
            document,
            (semantic_judgments or {}).get(document.document_id, {}).get(item.id),
        )
        for item in all_criteria
    ]
    by_id = {item.criterion_id: item for item in evaluations}
    hard_violated = any(
        by_id[item.id].status == "violated"
        for item in all_criteria
        if item.is_hard_constraint
    )
    hard_unknown = any(
        by_id[item.id].status == "unknown"
        for item in all_criteria
        if item.is_hard_constraint
    )
    return evaluations, hard_violated, hard_unknown


def evaluate_expression(
    expression: ConditionExpression,
    document: SearchCandidate,
    semantic_judgments: dict[str, dict[str, SemanticJudgment]] | None = None,
) -> ConditionEvaluation:
    """Evaluate AND/OR/NOT with Kleene three-valued logic."""
    if expression.criterion is not None:
        evaluation = evaluate_criterion(
            expression.criterion,
            document,
            (semantic_judgments or {}).get(document.document_id, {}).get(expression.criterion.id),
        )
        return ConditionEvaluation(
            status=evaluation.status,
            confidence=evaluation.confidence,
            evaluations=[evaluation],
        )

    assert expression.operator is not None
    children = [
        evaluate_expression(item, document, semantic_judgments)
        for item in expression.operands
    ]
    statuses = [item.status for item in children]
    status: Literal["satisfied", "violated", "unknown"]
    if expression.operator == "not":
        negated_statuses: dict[
            Literal["satisfied", "violated", "unknown"],
            Literal["satisfied", "violated", "unknown"],
        ] = {
            "satisfied": "violated",
            "violated": "satisfied",
            "unknown": "unknown",
        }
        status = negated_statuses[statuses[0]]
    elif expression.operator == "and":
        status = "violated" if "violated" in statuses else "unknown" if "unknown" in statuses else "satisfied"
    else:
        status = "satisfied" if "satisfied" in statuses else "unknown" if "unknown" in statuses else "violated"
    return ConditionEvaluation(
        status=status,
        confidence=min((item.confidence for item in children), default=0.0),
        evaluations=[evaluation for child in children for evaluation in child.evaluations],
    )
