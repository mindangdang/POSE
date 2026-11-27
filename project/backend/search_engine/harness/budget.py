from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic


@dataclass
class SearchBudget:
    max_rounds: int = 2
    max_queries_per_round: int = 3
    max_external_calls: int = 6
    max_candidates: int = 50
    max_evidence_documents: int = 15
    max_concurrent_evidence: int = 4
    max_semantic_evaluations: int = 24
    max_results: int = 10
    deadline_seconds: float = 60.0
    rounds: int = 0
    external_calls: int = 0
    evidence_documents_fetched: int = 0
    semantic_evaluations: int = 0
    started_at: float = field(default_factory=monotonic)

    def has_time(self) -> bool:
        return monotonic() - self.started_at < self.deadline_seconds

    def can_search(self, query_count: int = 1) -> bool:
        return (
            self.has_time()
            and self.rounds < self.max_rounds
            and self.external_calls + query_count <= self.max_external_calls
        )

    def consume_search(self, query_count: int) -> None:
        if query_count > self.max_queries_per_round or not self.can_search(query_count):
            raise RuntimeError("Search budget exhausted")
        self.rounds += 1
        self.external_calls += query_count

    @property
    def evidence_remaining(self) -> int:
        return max(0, self.max_evidence_documents - self.evidence_documents_fetched)

    def consume_evidence(self, requested_count: int) -> int:
        if requested_count < 0:
            raise ValueError("Evidence request count cannot be negative")
        granted = min(requested_count, self.evidence_remaining)
        self.evidence_documents_fetched += granted
        return granted

    def consume_semantic(self, requested_count: int) -> int:
        if requested_count < 0:
            raise ValueError("Semantic evaluation count cannot be negative")
        granted = min(
            requested_count,
            max(0, self.max_semantic_evaluations - self.semantic_evaluations),
        )
        self.semantic_evaluations += granted
        return granted
