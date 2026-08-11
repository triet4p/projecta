"""PostgreSQL implementation of the bounded connector operational port."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DataError, IntegrityError

from projecta_api.operational.database import ConnectorDatabase
from projecta_api.operational.errors import IdempotencyConflict, RevisionConflict
from projecta_api.operational.ports import (
    ConnectorOperationalRepository,
    CursorRecord,
    EventClaim,
    InstallationRecord,
    Outcome,
    SyncRunRecord,
)
from projecta_api.operational.schema import (
    ConnectorAuditRecord,
    ConnectorCursor,
    ConnectorDeadLetter,
    ConnectorEventInbox,
    ConnectorInstallation,
    ConnectorSyncAttempt,
    ConnectorSyncRun,
)

_LOGGER = logging.getLogger("projecta.connector.repository")


def _now() -> datetime:
    return datetime.now(UTC)


def _installation(row: Any) -> InstallationRecord:
    return InstallationRecord(
        installation_id=str(row.installation_id),
        project_id=str(row.project_id),
        connector_type=str(row.connector_type),
        capability_snapshot=dict(row.capability_snapshot),
        secret_reference=(str(row.secret_reference) if row.secret_reference is not None else None),
        enabled=bool(row.enabled),
        revision=int(row.revision),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _run(row: Any) -> SyncRunRecord:
    return SyncRunRecord(
        run_id=str(row.run_id),
        installation_id=str(row.installation_id),
        project_id=str(row.project_id),
        status=str(row.status),
        started_at=row.started_at,
        terminal_at=row.terminal_at,
        terminal_outcome=row.terminal_outcome,
        revision=int(row.revision),
        retry_of_run_id=row.retry_of_run_id,
        failure_code=row.failure_code,
        failure_detail=row.failure_detail,
        event_count=int(row.event_count),
        replay_count=int(row.replay_count),
        dead_letter_id=(int(row.dead_letter_id) if row.dead_letter_id is not None else None),
    )


class PostgresConnectorRepository(ConnectorOperationalRepository):
    """Use explicit project predicates and short transactions for every mutation."""

    def __init__(self, database: ConnectorDatabase) -> None:
        self._database = database

    def get_installation(self, project_id: str, installation_id: str) -> InstallationRecord | None:
        try:
            with self._database.connection(operation="get_installation") as connection:
                row = connection.execute(
                    select(ConnectorInstallation).where(
                        ConnectorInstallation.installation_id == installation_id,
                        ConnectorInstallation.project_id == project_id,
                    )
                ).fetchone()
        except Exception as error:  # noqa: BLE001 - preserve the safe operational boundary.
            _LOGGER.error(
                "connector installation lookup failed; failureType=%s",
                type(error).__name__,
            )
            raise
        return _installation(row) if row is not None else None

    def list_installations(
        self, project_id: str, *, limit: int = 50, offset: int = 0
    ) -> list[InstallationRecord]:
        bounded_limit = max(1, min(limit, 100))
        bounded_offset = max(0, min(offset, 10_000))
        with self._database.connection() as connection:
            rows = connection.execute(
                select(ConnectorInstallation)
                .where(ConnectorInstallation.project_id == project_id)
                .order_by(
                    ConnectorInstallation.updated_at.desc(), ConnectorInstallation.installation_id
                )
                .limit(bounded_limit)
                .offset(bounded_offset)
            ).fetchall()
        return [_installation(row) for row in rows]

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
    ) -> InstallationRecord:
        audit_values = (audit_operation, actor_reference, correlation_id)
        if any(value is not None for value in audit_values) and not all(
            isinstance(value, str) and value for value in audit_values
        ):
            raise ValueError("installation audit metadata is incomplete")
        now = _now()
        with self._database.connection() as connection:
            row = connection.execute(
                select(ConnectorInstallation).where(
                    ConnectorInstallation.installation_id == installation_id,
                    ConnectorInstallation.project_id == project_id,
                )
            ).fetchone()
            current = _installation(row) if row is not None else None
            if expected_revision is not None and (
                current is None or current.revision != expected_revision
            ):
                raise RevisionConflict("installation revision conflict")
            if current is None:
                try:
                    connection.execute(
                        insert(ConnectorInstallation).values(
                            installation_id=installation_id,
                            project_id=project_id,
                            connector_type=connector_type,
                            capability_snapshot=capability_snapshot,
                            secret_reference=secret_reference,
                            enabled=enabled,
                            revision=1,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                except IntegrityError as exc:
                    raise RevisionConflict(
                        "installation identity or project connector already exists"
                    ) from exc
            else:
                connection.execute(
                    update(ConnectorInstallation)
                    .where(
                        ConnectorInstallation.installation_id == installation_id,
                        ConnectorInstallation.project_id == project_id,
                        ConnectorInstallation.revision == current.revision,
                    )
                    .values(
                        connector_type=connector_type,
                        capability_snapshot=capability_snapshot,
                        secret_reference=secret_reference,
                        enabled=enabled,
                        revision=current.revision + 1,
                        updated_at=now,
                    )
                )
            result = connection.execute(
                select(ConnectorInstallation).where(
                    ConnectorInstallation.installation_id == installation_id,
                    ConnectorInstallation.project_id == project_id,
                )
            ).fetchone()
            if result is not None and audit_operation is not None:
                connection.execute(
                    insert(ConnectorAuditRecord).values(
                        project_id=project_id,
                        installation_id=installation_id,
                        operation=audit_operation,
                        outcome="accepted",
                        actor_reference=actor_reference,
                        correlation_id=correlation_id,
                        revision=int(result.revision),
                        recorded_at=now,
                    )
                )
        if result is None:
            raise RuntimeError("installation write did not produce a row")
        return _installation(result)

    def claim_event(
        self,
        *,
        project_id: str,
        installation_id: str,
        event_id: str,
        body_hash: str,
        content_reference: str,
    ) -> EventClaim:
        now = _now()
        conflict = False
        with self._database.connection() as connection:
            self._require_installation(connection, project_id, installation_id)
            existing = connection.execute(
                select(ConnectorEventInbox).where(
                    ConnectorEventInbox.event_id == event_id,
                    ConnectorEventInbox.project_id == project_id,
                    ConnectorEventInbox.installation_id == installation_id,
                )
            ).fetchone()
            if existing is None:
                result = connection.execute(
                    pg_insert(ConnectorEventInbox)
                    .values(
                        event_id=event_id,
                        installation_id=installation_id,
                        project_id=project_id,
                        body_hash=body_hash,
                        content_reference=content_reference,
                        accepted_outcome=None,
                        accepted_at=None,
                        conflict_count=0,
                        conflict_last_seen_at=None,
                        created_at=now,
                        updated_at=now,
                    )
                    .on_conflict_do_nothing(
                        index_elements=[
                            ConnectorEventInbox.event_id,
                            ConnectorEventInbox.installation_id,
                            ConnectorEventInbox.project_id,
                        ]
                    )
                    .returning(ConnectorEventInbox.event_id)
                )
                # RETURNING is the unambiguous winner signal. Driver rowcount
                # is not reliable for INSERT ... ON CONFLICT across versions.
                if result.fetchone() is not None:
                    return EventClaim(
                        event_id, project_id, installation_id, "new", None, content_reference
                    )
                existing = connection.execute(
                    select(ConnectorEventInbox).where(
                        ConnectorEventInbox.event_id == event_id,
                        ConnectorEventInbox.project_id == project_id,
                        ConnectorEventInbox.installation_id == installation_id,
                    )
                ).fetchone()
                if existing is None:
                    raise RuntimeError("event claim did not produce or find an inbox row")
            if str(existing.body_hash) != body_hash:
                connection.execute(
                    update(ConnectorEventInbox)
                    .where(
                        ConnectorEventInbox.event_id == event_id,
                        ConnectorEventInbox.project_id == project_id,
                        ConnectorEventInbox.installation_id == installation_id,
                    )
                    .values(
                        conflict_count=ConnectorEventInbox.conflict_count + 1,
                        conflict_last_seen_at=now,
                        updated_at=now,
                    )
                )
                conflict = True
            if conflict:
                pass
            else:
                outcome = (
                    "replayed"
                    if existing.accepted_outcome in {"accepted", "replayed"}
                    else (
                        "new"
                        if existing.accepted_outcome in {"failed", "cancelled"}
                        else "in_progress"
                    )
                )
                return EventClaim(
                    event_id,
                    project_id,
                    installation_id,
                    outcome,
                    existing.accepted_outcome,
                    str(existing.content_reference),
                )
        raise IdempotencyConflict("event body hash conflicts with the accepted identity")

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
    ) -> CursorRecord | None:
        if outcome not in {"accepted", "replayed", "failed", "cancelled"}:
            raise ValueError("event completion requires a terminal outcome")
        now = _now()
        with self._database.connection() as connection:
            event = connection.execute(
                select(ConnectorEventInbox).where(
                    ConnectorEventInbox.event_id == event_id,
                    ConnectorEventInbox.project_id == project_id,
                    ConnectorEventInbox.installation_id == installation_id,
                )
            ).fetchone()
            if event is None or str(event.body_hash) != body_hash:
                raise IdempotencyConflict(
                    "event identity is not owned by this project installation"
                )
            if event.accepted_outcome in {"accepted", "replayed"}:
                return self._cursor(connection, project_id, installation_id)
            cursor = connection.execute(
                select(ConnectorCursor).where(
                    ConnectorCursor.installation_id == installation_id,
                    ConnectorCursor.project_id == project_id,
                )
            ).fetchone()
            current_revision = 0 if cursor is None else int(cursor.revision)
            if (
                expected_cursor_revision is not None
                and current_revision != expected_cursor_revision
            ):
                raise RevisionConflict("cursor revision conflict")
            connection.execute(
                update(ConnectorEventInbox)
                .where(
                    ConnectorEventInbox.event_id == event_id,
                    ConnectorEventInbox.project_id == project_id,
                    ConnectorEventInbox.installation_id == installation_id,
                    ConnectorEventInbox.accepted_outcome.is_(None),
                )
                .values(accepted_outcome=outcome, accepted_at=now, updated_at=now)
            )
            if outcome != "accepted" or checkpoint is None:
                return self._cursor(connection, project_id, installation_id)
            next_revision = current_revision + 1
            if cursor is None:
                connection.execute(
                    insert(ConnectorCursor).values(
                        installation_id=installation_id,
                        project_id=project_id,
                        checkpoint=checkpoint,
                        revision=next_revision,
                        updated_at=now,
                    )
                )
            else:
                connection.execute(
                    update(ConnectorCursor)
                    .where(
                        ConnectorCursor.installation_id == installation_id,
                        ConnectorCursor.project_id == project_id,
                        ConnectorCursor.revision == current_revision,
                    )
                    .values(checkpoint=checkpoint, revision=next_revision, updated_at=now)
                )
            return CursorRecord(installation_id, project_id, checkpoint, next_revision, now)

    def get_cursor(self, project_id: str, installation_id: str) -> CursorRecord | None:
        with self._database.connection() as connection:
            return self._cursor(connection, project_id, installation_id)

    def start_run(
        self,
        *,
        project_id: str,
        installation_id: str,
        run_id: str,
        idempotency_key: str,
        retry_of_run_id: str | None = None,
    ) -> SyncRunRecord:
        now = _now()
        with self._database.connection(operation="start_run") as connection:
            self._require_installation(connection, project_id, installation_id)
            existing = connection.execute(
                select(ConnectorSyncRun).where(
                    ConnectorSyncRun.installation_id == installation_id,
                    ConnectorSyncRun.project_id == project_id,
                    ConnectorSyncRun.idempotency_key == idempotency_key,
                )
            ).fetchone()
            if existing is not None:
                return _run(existing)
            try:
                connection.execute(
                    insert(ConnectorSyncRun).values(
                        run_id=run_id,
                        installation_id=installation_id,
                        project_id=project_id,
                        status="running",
                        started_at=now,
                        terminal_at=None,
                        terminal_outcome=None,
                        revision=1,
                        event_count=0,
                        replay_count=0,
                        dead_letter_id=None,
                        idempotency_key=idempotency_key,
                        retry_of_run_id=retry_of_run_id,
                        failure_code=None,
                        failure_detail=None,
                        created_at=now,
                        updated_at=now,
                    )
                )
            except DataError:
                _LOGGER.error("connector run persistence rejected bounded values; phase=run")
                raise
            try:
                connection.execute(
                    insert(ConnectorSyncAttempt).values(
                        run_id=run_id,
                        attempt_number=1,
                        status="running",
                        started_at=now,
                        terminal_at=None,
                        outcome=None,
                        failure_code=None,
                        failure_detail=None,
                    )
                )
            except DataError:
                _LOGGER.error("connector run persistence rejected bounded values; phase=attempt")
                raise
            row = connection.execute(
                select(ConnectorSyncRun).where(
                    ConnectorSyncRun.run_id == run_id,
                    ConnectorSyncRun.project_id == project_id,
                    ConnectorSyncRun.installation_id == installation_id,
                )
            ).fetchone()
        if row is None:
            raise RuntimeError("run write did not produce a row")
        return _run(row)

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
    ) -> SyncRunRecord:
        now = _now()
        with self._database.connection() as connection:
            row = connection.execute(
                select(ConnectorSyncRun).where(
                    ConnectorSyncRun.run_id == run_id,
                    ConnectorSyncRun.project_id == project_id,
                    ConnectorSyncRun.installation_id == installation_id,
                )
            ).fetchone()
            if row is None:
                raise KeyError("sync run not found")
            if row.terminal_at is not None:
                return _run(row)
            connection.execute(
                update(ConnectorSyncRun)
                .where(
                    ConnectorSyncRun.run_id == run_id,
                    ConnectorSyncRun.project_id == project_id,
                    ConnectorSyncRun.installation_id == installation_id,
                    ConnectorSyncRun.terminal_at.is_(None),
                )
                .values(
                    status=outcome,
                    terminal_at=now,
                    terminal_outcome=outcome,
                    revision=ConnectorSyncRun.revision + 1,
                    failure_code=failure_code,
                    failure_detail=failure_detail,
                    event_count=event_count,
                    replay_count=replay_count,
                    dead_letter_id=dead_letter_id,
                    updated_at=now,
                )
            )
            connection.execute(
                update(ConnectorSyncAttempt)
                .where(
                    ConnectorSyncAttempt.run_id == run_id, ConnectorSyncAttempt.attempt_number == 1
                )
                .values(
                    status=outcome,
                    terminal_at=now,
                    outcome=outcome,
                    failure_code=failure_code,
                    failure_detail=failure_detail,
                )
            )
            updated = connection.execute(
                select(ConnectorSyncRun).where(
                    ConnectorSyncRun.run_id == run_id,
                    ConnectorSyncRun.project_id == project_id,
                    ConnectorSyncRun.installation_id == installation_id,
                )
            ).fetchone()
        if updated is None:
            raise RuntimeError("run finish did not produce a row")
        return _run(updated)

    def get_run(self, project_id: str, installation_id: str, run_id: str) -> SyncRunRecord | None:
        with self._database.connection() as connection:
            row = connection.execute(
                select(ConnectorSyncRun).where(
                    ConnectorSyncRun.run_id == run_id,
                    ConnectorSyncRun.project_id == project_id,
                    ConnectorSyncRun.installation_id == installation_id,
                )
            ).fetchone()
        return _run(row) if row is not None else None

    def list_runs(
        self, project_id: str, installation_id: str, *, limit: int = 50
    ) -> list[SyncRunRecord]:
        bounded_limit = max(1, min(limit, 100))
        with self._database.connection() as connection:
            rows = connection.execute(
                select(ConnectorSyncRun)
                .where(
                    ConnectorSyncRun.project_id == project_id,
                    ConnectorSyncRun.installation_id == installation_id,
                )
                .order_by(ConnectorSyncRun.started_at.desc(), ConnectorSyncRun.run_id)
                .limit(bounded_limit)
            ).fetchall()
        return [_run(row) for row in rows]

    def record_dead_letter(
        self,
        *,
        project_id: str,
        installation_id: str,
        failure_code: str,
        sanitized_detail: str,
        run_id: str | None = None,
        event_id: str | None = None,
    ) -> int:
        if len(sanitized_detail) > 2000:
            raise ValueError("dead-letter detail exceeds the bounded limit")
        with self._database.connection() as connection:
            self._require_installation(connection, project_id, installation_id)
            result = connection.execute(
                insert(ConnectorDeadLetter).values(
                    installation_id=installation_id,
                    project_id=project_id,
                    run_id=run_id,
                    event_id=event_id,
                    failure_code=failure_code,
                    sanitized_detail=sanitized_detail,
                    created_at=_now(),
                    resolved_at=None,
                )
            )
            inserted_key: object | None = (
                result.inserted_primary_key[0] if result.inserted_primary_key else None
            )
        if not isinstance(inserted_key, int):
            raise RuntimeError("dead-letter write did not produce an id")
        return inserted_key

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
    ) -> None:
        with self._database.connection() as connection:
            if installation_id is not None:
                self._require_installation(connection, project_id, installation_id)
            try:
                connection.execute(
                    insert(ConnectorAuditRecord).values(
                        project_id=project_id,
                        installation_id=installation_id,
                        operation=operation,
                        outcome=outcome,
                        actor_reference=actor_reference,
                        correlation_id=correlation_id,
                        revision=revision,
                        recorded_at=_now(),
                    )
                )
            except DataError:
                _LOGGER.error("connector audit persistence rejected bounded values; phase=audit")
                raise

    def list_audit(self, project_id: str, *, limit: int = 50) -> list[dict[str, object]]:
        bounded_limit = max(1, min(limit, 100))
        with self._database.connection() as connection:
            rows = connection.execute(
                select(ConnectorAuditRecord)
                .where(ConnectorAuditRecord.project_id == project_id)
                .order_by(ConnectorAuditRecord.recorded_at.desc())
                .limit(bounded_limit)
            ).fetchall()
        return [
            {
                "operation": str(row.operation),
                "outcome": str(row.outcome),
                "actorReference": str(row.actor_reference),
                "correlationId": str(row.correlation_id),
                "revision": row.revision,
                "recordedAt": row.recorded_at,
            }
            for row in rows
        ]

    @staticmethod
    def _require_installation(connection: Connection, project_id: str, installation_id: str) -> Any:
        row = connection.execute(
            select(ConnectorInstallation.installation_id).where(
                ConnectorInstallation.installation_id == installation_id,
                ConnectorInstallation.project_id == project_id,
            )
        ).fetchone()
        if row is None:
            raise KeyError("connector installation not found")
        return row

    @staticmethod
    def _cursor(
        connection: Connection, project_id: str, installation_id: str
    ) -> CursorRecord | None:
        row = connection.execute(
            select(ConnectorCursor).where(
                ConnectorCursor.installation_id == installation_id,
                ConnectorCursor.project_id == project_id,
            )
        ).fetchone()
        if row is None:
            return None
        return CursorRecord(
            row.installation_id, row.project_id, row.checkpoint, row.revision, row.updated_at
        )
