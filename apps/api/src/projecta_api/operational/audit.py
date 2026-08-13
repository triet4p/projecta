"""Safe cross-boundary audit events for identity, secrets, connectors, and candidates."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal, Protocol

AuditCategory = Literal["login", "session", "membership", "secret", "connector", "candidate"]
AuditOutcome = Literal["started", "succeeded", "failed", "changed", "revoked", "committed", "rejected"]


@dataclass(frozen=True, slots=True)
class SecurityAuditEvent:
    """Correlated safe label; raw subjects, provider IDs, refs, and payloads are excluded."""

    category: AuditCategory
    action: str
    outcome: AuditOutcome
    correlation_id: str
    project_scope: str | None = None
    actor_scope: str | None = None
    revision: int | None = None
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class SecurityAuditSink(Protocol):
    def emit(self, event: SecurityAuditEvent) -> None: ...


@dataclass
class InMemorySecurityAuditSink:
    """Deterministic sink for acceptance tests and local operator diagnostics."""

    events: list[SecurityAuditEvent] = field(default_factory=lambda: list[SecurityAuditEvent]())

    def emit(self, event: SecurityAuditEvent) -> None:
        self.events.append(event)


def safe_scope(value: str) -> str:
    return "scope-" + sha256(value.encode("utf-8")).hexdigest()[:16]


def emit_safe(
    sink: SecurityAuditSink | None,
    *,
    category: AuditCategory,
    action: str,
    outcome: AuditOutcome,
    correlation_id: str,
    project_id: str | None = None,
    actor_id: str | None = None,
    revision: int | None = None,
) -> None:
    if sink is None:
        return
    sink.emit(
        SecurityAuditEvent(
            category=category,
            action=action,
            outcome=outcome,
            correlation_id=correlation_id,
            project_scope=safe_scope(project_id) if project_id else None,
            actor_scope=safe_scope(actor_id) if actor_id else None,
            revision=revision,
        )
    )
