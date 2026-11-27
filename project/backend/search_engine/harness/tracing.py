from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import perf_counter
from typing import Any


@dataclass
class TraceEvent:
    node: str
    status: str
    latency_ms: float
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchTrace:
    trace_id: str
    events: list[TraceEvent] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def record(self, node: str, started: float, status: str = "ok", **attributes: Any) -> None:
        self.events.append(
            TraceEvent(
                node=node,
                status=status,
                latency_ms=round((perf_counter() - started) * 1000, 3),
                attributes=attributes,
            )
        )

