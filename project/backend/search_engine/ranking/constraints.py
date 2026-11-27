from __future__ import annotations

import re

from project.backend.search_engine.schemas import (
    Criterion,
    CriterionEvaluation,
    SearchCandidate,
)
from project.backend.search_engine.retrieval.sparse import tokenize


def evaluate_criterion(criterion: Criterion, document: SearchCandidate) -> CriterionEvaluation:
    value = str(criterion.value).casefold()
    content = " ".join([document.title, document.snippet, document.content]).casefold()
    attribute_value = document.metadata.get(criterion.attribute)
    if attribute_value is None:
        for key, item in document.metadata.items():
            if key.casefold() == criterion.attribute.casefold():
                attribute_value = item
                break

    if attribute_value is not None:
        actual = str(attribute_value).casefold()
        if actual.strip() in {"", "unknown", "unspecified", "not provided", "n/a", "null"}:
            return CriterionEvaluation(
                criterion_id=criterion.id,
                document_id=document.document_id,
                status="unknown",
                confidence=0.0,
                evidence_url=document.canonical_url,
                evidence_type="none",
            )
        if criterion.operator.value in {"eq", "semantic_match"}:
            satisfied = value in actual or actual in value
        elif criterion.operator.value == "neq":
            satisfied = value not in actual
        elif criterion.operator.value == "contains":
            satisfied = value in actual
        else:
            try:
                left, right = float(actual), float(value)
                satisfied = {
                    "gt": left > right,
                    "gte": left >= right,
                    "lt": left < right,
                    "lte": left <= right,
                }[criterion.operator.value]
            except (ValueError, KeyError):
                satisfied = False
        return CriterionEvaluation(
            criterion_id=criterion.id,
            document_id=document.document_id,
            status="satisfied" if satisfied else "violated",
            confidence=1.0,
            evidence_excerpt=f"{criterion.attribute}: {attribute_value}",
            evidence_url=document.canonical_url,
            evidence_type="metadata",
        )

    normalized_value = re.sub(r"\s+", " ", value).strip()
    value_tokens = set(tokenize(normalized_value))
    content_tokens = set(tokenize(content))
    overlap = len(value_tokens & content_tokens) / len(value_tokens) if value_tokens else 0.0
    if criterion.operator.value == "neq":
        if not document.content and not document.snippet:
            return CriterionEvaluation(
                criterion_id=criterion.id,
                document_id=document.document_id,
                status="unknown",
                confidence=0.0,
                evidence_url=document.canonical_url,
                evidence_type="none",
            )
        # A negative requirement is only verified when the text explicitly
        # denies the phrase or structured metadata says it is absent. Silence
        # in a page is not evidence that the excluded property is absent.
        phrase_present = bool(normalized_value and normalized_value in content)
        if phrase_present:
            escaped = re.escape(normalized_value)
            negative_context = re.search(
                rf"(?:\bno\b|\bwithout\b|\bfree of\b|\bdoes not\b|\bdoesn't\b|\bnot\b|없이|없음|없는)\W{{0,24}}{escaped}",
                content,
            )
            if negative_context:
                return CriterionEvaluation(
                    criterion_id=criterion.id,
                    document_id=document.document_id,
                    status="satisfied",
                    confidence=0.8,
                    evidence_excerpt=negative_context.group(0),
                    evidence_url=document.canonical_url,
                    evidence_type="content" if document.content else "snippet",
                )
            return CriterionEvaluation(
                criterion_id=criterion.id,
                document_id=document.document_id,
                status="violated",
                confidence=0.8,
                evidence_excerpt=normalized_value,
                evidence_url=document.canonical_url,
                evidence_type="content" if document.content else "snippet",
            )
        return CriterionEvaluation(
            criterion_id=criterion.id,
            document_id=document.document_id,
            status="unknown",
            confidence=0.0,
            evidence_url=document.canonical_url,
            evidence_type="none",
        )
    if normalized_value and (normalized_value in content or overlap >= 0.8):
        escaped = re.escape(normalized_value)
        negative_context = re.search(
            rf"(?:\bno\b|\bwithout\b|\bfree of\b|\bdoes not have\b|\bdoesn't have\b|\bnot\b|없는|없음|없이)\W{{0,24}}{escaped}",
            content,
        )
        if negative_context:
            return CriterionEvaluation(
                criterion_id=criterion.id,
                document_id=document.document_id,
                status="violated",
                confidence=0.8,
                evidence_excerpt=negative_context.group(0),
                evidence_url=document.canonical_url,
                evidence_type="content" if document.content else "snippet",
            )
        return CriterionEvaluation(
            criterion_id=criterion.id,
            document_id=document.document_id,
            status="satisfied",
            confidence=0.8,
            evidence_excerpt=normalized_value if normalized_value in content else " ".join(value_tokens & content_tokens),
            evidence_url=document.canonical_url,
            evidence_type="content" if document.content else "snippet",
        )
    return CriterionEvaluation(
        criterion_id=criterion.id,
        document_id=document.document_id,
        status="unknown",
        confidence=0.0,
        evidence_url=document.canonical_url,
        evidence_type="none",
    )


def assess_candidate(
    document: SearchCandidate, criteria: list[Criterion], exclusions: list[Criterion]
) -> tuple[list[CriterionEvaluation], bool, bool]:
    evaluations = [evaluate_criterion(item, document) for item in [*criteria, *exclusions]]
    by_id = {item.criterion_id: item for item in evaluations}
    hard_violated = any(
        by_id[item.id].status == "violated"
        for item in [*criteria, *exclusions]
        if item.is_hard_constraint
    )
    hard_unknown = any(
        by_id[item.id].status == "unknown"
        for item in [*criteria, *exclusions]
        if item.is_hard_constraint
    )
    return evaluations, hard_violated, hard_unknown
