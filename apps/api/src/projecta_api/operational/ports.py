"""Provider-neutral typed ports for connector operational state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

Outcome = Literal["accepted", "replayed", "failed", "cancelled", "truncated", "conflict", "in_progress"]


@dataclass(frozen=True, slots=True)
class InstallationRecord:
    installation_id: str
    project_id: str
    connector_type: str
    capability_snapshot: dict[str, object]
    secret_reference: str | None
    enabled: bool
    revision: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class EventClaim:
    event_id: str
    project_id: str
    installation_id: str
    outcome: Literal["new", "replayed", "in_progress", "conflict"]
    accepted_outcome: str | None
    content_reference: str


@dataclass(frozen=True, slots=True)
class SyncRunRecord:
    run_id: str
    installation_id: str
    project_id: str
    status: str
    started_at: datetime
    terminal_at: datetime | None
    terminal_outcome: str | None
    revision: int
    retry_of_run_id: str | None
    failure_code: str | None
    failure_detail: str | None
    event_count: int = 0
    replay_count: int = 0
    dead_letter_id: int | None = None


@dataclass(frozen=True, slots=True)
class CursorRecord:
    installation_id: str
    project_id: str
    checkpoint: str | None
    revision: int
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class DeadLetterRecord:
    dead_letter_id: int
    installation_id: str
    project_id: str
    run_id: str | None
    event_id: str | None
    failure_code: str
    sanitized_detail: str
    created_at: datetime
    resolved_at: datetime | None


class ConnectorOperationalRepository(Protocol):
    """Finite repository operations; SQLAlchemy rows never cross this port."""

    def get_installation(
        self, project_id: str, installation_id: str
    ) -> InstallationRecord | None: ...

    def list_installations(
        self, project_id: str, *, limit: int = 50, offset: int = 0
    ) -> list[InstallationRecord]: ...

    def upsert_installation(
        self,
        *,
        project_id: str,
        installation_id: str,
        connector_type: str,
        capability_snapshot: dict[str, object],
        secret_reference: str | None,
        enabled: bool,
        expected_revision: int | None,
        audit_operation: str | None = None,
        actor_reference: str | None = None,
        correlation_id: str | None = None,
    ) -> InstallationRecord: ...

    def claim_event(
        self,
        *,
        project_id: str,
        installation_id: str,
        event_id: str,
        body_hash: str,
        content_reference: str,
    ) -> EventClaim: ...

    def complete_event(
        self,
        *,
        project_id: str,
        installation_id: str,
        event_id: str,
        body_hash: str,
        outcome: Outcome,
        checkpoint: str | None,
        expected_cursor_revision: int | None,
    ) -> CursorRecord | None: ...

    def get_cursor(self, project_id: str, installation_id: str) -> CursorRecord | None: ...

    def start_run(
        self,
        *,
        project_id: str,
        installation_id: str,
        run_id: str,
        idempotency_key: str,
        retry_of_run_id: str | None = None,
    ) -> SyncRunRecord: ...

    def finish_run(
        self,
        *,
        project_id: str,
        installation_id: str,
        run_id: str,
        outcome: Outcome,
        failure_code: str | None = None,
        failure_detail: str | None = None,
        event_count: int = 0,
        replay_count: int = 0,
        dead_letter_id: int | None = None,
    ) -> SyncRunRecord: ...

    def get_run(
        self, project_id: str, installation_id: str, run_id: str
    ) -> SyncRunRecord | None: ...

    def list_runs(
        self, project_id: str, installation_id: str, *, limit: int = 50
    ) -> list[SyncRunRecord]: ...

    def record_dead_letter(
        self,
        *,
        project_id: str,
        installation_id: str,
        failure_code: str,
        sanitized_detail: str,
        run_id: str | None = None,
        event_id: str | None = None,
    ) -> int: ...

    def record_audit(
        self,
        *,
        project_id: str,
        operation: str,
        outcome: str,
        actor_reference: str,
        correlation_id: str,
        installation_id: str | None = None,
        revision: int | None = None,
    ) -> None: ...

    def list_audit(self, project_id: str, *, limit: int = 50) -> list[dict[str, object]]: ...
