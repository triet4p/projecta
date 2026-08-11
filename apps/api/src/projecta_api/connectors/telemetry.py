"""Safe correlated connector telemetry port and deterministic test sink."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class ConnectorTelemetryEvent:
    phase: Literal["start", "terminal"]
    operation: Literal["sync"]
    connector_type: str
    project_scope: str
    attempt_mode: Literal["single", "explicit-retry"]
    outcome: str | None
    duration_ms: int | None
    event_count: int
    replay_count: int
    correlation_id: str
    recorded_at: datetime


class ConnectorTelemetrySink(Protocol):
    def emit(self, event: ConnectorTelemetryEvent) -> None: ...


@dataclass
class InMemoryConnectorTelemetry:
    events: list[ConnectorTelemetryEvent] = field(
        default_factory=lambda: list[ConnectorTelemetryEvent]()
    )

    def emit(self, event: ConnectorTelemetryEvent) -> None:
        self.events.append(event)


def safe_project_scope(project_id: str) -> str:
    """Return a non-reversible project correlation scope for telemetry."""
    return "project-" + sha256(project_id.encode("utf-8")).hexdigest()[:16]


def now_utc() -> datetime:
    return datetime.now(UTC)
