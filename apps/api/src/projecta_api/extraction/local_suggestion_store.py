"""Private operational cache, budgets, and decision state for local suggestions."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal, cast

from projecta_api.configuration.storage import OperationalDatabase
from projecta_api.extraction.authoring_telemetry import (
    AuthoringTelemetryRepository,
    CorrectionDimension,
    WorkflowKind,
)
from projecta_api.extraction.review_receipts import ReviewDecisionReceiptRecord


@dataclass(frozen=True, slots=True)
class LocalSuggestionKey:
    """Server-resolved cache identity; persisted identifiers are digested."""

    project_id: str
    source_version_id: str
    source_version_revision: int
    item_handle: str
    item_revision: int
    evidence_digest: str

    @property
    def workflow_id(self) -> str:
        return "ls1_" + _digest(_stable_json(_cache_fields(self)))

    @property
    def request_digest(self) -> str:
        return _digest(_stable_json(_cache_fields(self)))


@dataclass(frozen=True, slots=True)
class LocalSuggestionBudget:
    user_limit: int
    user_remaining: int
    project_limit: int
    project_remaining: int
    resets_at: datetime


@dataclass(frozen=True, slots=True)
class StoredLocalSuggestion:
    workflow_id: str
    state: str
    proposal_json: str | None
    revision: int
    source_version_revision: int
    evidence_digest: str
    model_id: str | None
    error_code: str | None
    receipt_digest: str | None


@dataclass(frozen=True, slots=True)
class LocalSuggestionRead:
    suggestion: StoredLocalSuggestion | None
    budget: LocalSuggestionBudget


@dataclass(frozen=True, slots=True)
class LocalSuggestionReservation:
    state: Literal["reserved", "cached", "in-progress", "failed", "budget-exhausted"]
    suggestion: StoredLocalSuggestion
    budget: LocalSuggestionBudget
    attempt_digest: str | None = None


class LocalSuggestionStoreConflict(ValueError):
    """Raised when a local suggestion replay or revision is stale or conflicting."""


class LocalSuggestionRepository:
    """Atomically deduplicate and budget explicit local suggestion requests."""

    _LEASE = timedelta(seconds=90)

    def __init__(self, database: OperationalDatabase) -> None:
        self._database = database
        self.telemetry = AuthoringTelemetryRepository(database)

    def read(
        self,
        key: LocalSuggestionKey,
        actor_id: str,
        *,
        now: datetime,
        user_limit: int,
        project_limit: int,
    ) -> LocalSuggestionRead:
        actor_digest = _digest(actor_id)
        window = _window_date(now)
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM local_suggestion_workflows WHERE workflow_id = ?",
                (key.workflow_id,),
            ).fetchone()
            budget = _budget(
                connection, key.project_id, actor_digest, window, user_limit, project_limit
            )
        return LocalSuggestionRead(_stored(row), budget)

    def propose_manual(
        self,
        key: LocalSuggestionKey,
        proposal_json: str,
        actor_id: str,
        workflow_kind: WorkflowKind,
        *,
        now: datetime,
    ) -> StoredLocalSuggestion:
        """Persist a deterministic, zero-inference proposal without consuming a model budget."""
        timestamp = now.isoformat()
        with self._database.transaction() as connection:
            inserted = connection.execute(
                """
                INSERT OR IGNORE INTO local_suggestion_workflows(
                    workflow_id, project_id, source_version_digest, source_version_revision,
                    item_handle_digest, item_revision, evidence_digest, state, proposal_json,
                    proposal_revision, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'proposed', ?, 1, ?, ?)
                """,
                (
                    key.workflow_id,
                    key.project_id,
                    _digest(key.source_version_id),
                    key.source_version_revision,
                    _digest(key.item_handle),
                    key.item_revision,
                    key.evidence_digest,
                    proposal_json,
                    timestamp,
                    timestamp,
                ),
            )
            if inserted.rowcount:
                self.telemetry.append_manual_workflow(
                    connection, key.project_id, actor_id, key.workflow_id, workflow_kind, now=now
                )
            row = connection.execute(
                "SELECT * FROM local_suggestion_workflows "
                "WHERE workflow_id = ? AND project_id = ?",
                (key.workflow_id, key.project_id),
            ).fetchone()
        result = _stored(row)
        if result is None:
            raise LocalSuggestionStoreConflict("manual suggestion was not persisted")
        return result

    def get_by_workflow_id(
        self, workflow_id: str, project_id: str
    ) -> StoredLocalSuggestion | None:
        """Read one workflow only inside its project boundary."""
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM local_suggestion_workflows "
                "WHERE workflow_id = ? AND project_id = ?",
                (workflow_id, project_id),
            ).fetchone()
        return _stored(row)


    def reserve(
        self,
        key: LocalSuggestionKey,
        actor_id: str,
        idempotency_key: str,
        *,
        retry: bool,
        now: datetime,
        user_limit: int,
        project_limit: int,
        workflow_kind: WorkflowKind = "entity",
    ) -> LocalSuggestionReservation:
        actor_digest = _digest(actor_id)
        idempotency_digest = _digest(f"{key.project_id}\0{actor_digest}\0{idempotency_key}")
        request_digest = _digest(_stable_json({"cache": key.request_digest, "retry": retry}))
        window = _window_date(now)
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO local_suggestion_workflows(
                    workflow_id, project_id, source_version_digest, source_version_revision,
                    item_handle_digest, item_revision, evidence_digest, state,
                    proposal_revision, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'new', 0, ?, ?)
                """,
                (
                    key.workflow_id,
                    key.project_id,
                    _digest(key.source_version_id),
                    key.source_version_revision,
                    _digest(key.item_handle),
                    key.item_revision,
                    key.evidence_digest,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            attempt = connection.execute(
                """
                SELECT request_digest, state, error_code FROM local_suggestion_attempts
                WHERE project_id = ? AND actor_digest = ? AND idempotency_digest = ?
                """,
                (key.project_id, actor_digest, idempotency_digest),
            ).fetchone()
            row = connection.execute(
                "SELECT * FROM local_suggestion_workflows WHERE workflow_id = ?",
                (key.workflow_id,),
            ).fetchone()
            record = _stored(row)
            assert record is not None
            budget = _budget(
                connection, key.project_id, actor_digest, window, user_limit, project_limit
            )

            if attempt is not None:
                if str(attempt["request_digest"]) != request_digest:
                    raise LocalSuggestionStoreConflict("idempotency key belongs to another request")
                attempt_state = str(attempt["state"])
                reservation_state: Literal["in-progress", "failed", "cached"] = (
                    "in-progress"
                    if attempt_state == "pending"
                    else "failed"
                    if attempt_state == "failed"
                    else "cached"
                )
                return LocalSuggestionReservation(reservation_state, record, budget)

            if record.state in {"proposed", "edited", "confirmed", "rejected"}:
                return LocalSuggestionReservation("cached", record, budget)
            if record.state == "abstained" and not retry:
                return LocalSuggestionReservation("cached", record, budget)
            if record.state == "failed" and not retry:
                return LocalSuggestionReservation("failed", record, budget)
            if retry and record.state not in {"failed", "abstained", "pending"}:
                return LocalSuggestionReservation("cached", record, budget)
            if record.state == "new" and retry:
                raise LocalSuggestionStoreConflict("retry requires a prior failed or abstained request")
            if record.state == "pending":
                started = _parse_timestamp(
                    connection.execute(
                        "SELECT attempt_started_at FROM local_suggestion_workflows WHERE workflow_id = ?",
                        (key.workflow_id,),
                    ).fetchone()[0]
                )
                if not retry or started is None or now - started < self._LEASE:
                    return LocalSuggestionReservation("in-progress", record, budget)
                connection.execute(
                    """
                    UPDATE local_suggestion_attempts SET state = 'failed', error_code = 'attempt_expired'
                    WHERE project_id = ? AND idempotency_digest = ?
                    """,
                    (key.project_id, str(row["current_attempt_digest"])),
                )

            self.telemetry.append_local_request(
                connection,
                key.project_id,
                actor_id,
                key.workflow_id,
                workflow_kind,
                idempotency_digest,
                request_digest,
                now=now,
            )
            if budget.user_remaining < 1 or budget.project_remaining < 1:
                return LocalSuggestionReservation("budget-exhausted", record, budget)

            _increment_budget(connection, "user", "", actor_digest, window)
            _increment_budget(connection, "project", key.project_id, "project", window)
            attempt_id = _digest(f"{key.workflow_id}\0{idempotency_digest}")
            connection.execute(
                """
                INSERT INTO local_suggestion_attempts(
                    attempt_id, project_id, actor_digest, workflow_id, idempotency_digest,
                    request_digest, state, requested_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (
                    attempt_id,
                    key.project_id,
                    actor_digest,
                    key.workflow_id,
                    idempotency_digest,
                    request_digest,
                    now.isoformat(),
                ),
            )
            connection.execute(
                """
                UPDATE local_suggestion_workflows
                SET state = 'pending', current_attempt_digest = ?, attempt_started_at = ?,
                    error_code = NULL, updated_at = ?
                WHERE workflow_id = ?
                """,
                (idempotency_digest, now.isoformat(), now.isoformat(), key.workflow_id),
            )
            updated = connection.execute(
                "SELECT * FROM local_suggestion_workflows WHERE workflow_id = ?",
                (key.workflow_id,),
            ).fetchone()
            next_budget = _budget(
                connection, key.project_id, actor_digest, window, user_limit, project_limit
            )
            return LocalSuggestionReservation(
                "reserved", _stored(updated), next_budget, idempotency_digest  # type: ignore[arg-type]
            )

    def complete(
        self,
        key: LocalSuggestionKey,
        attempt_digest: str,
        proposal_json: str,
        state: Literal["proposed", "abstained"],
        model_id: str,
        *,
        now: datetime,
    ) -> StoredLocalSuggestion:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT proposal_revision FROM local_suggestion_workflows "
                "WHERE workflow_id = ? AND state = 'pending' AND current_attempt_digest = ?",
                (key.workflow_id, attempt_digest),
            ).fetchone()
            if row is None:
                raise LocalSuggestionStoreConflict("suggestion request is no longer current")
            connection.execute(
                """
                UPDATE local_suggestion_workflows
                SET state = ?, proposal_json = ?, proposal_revision = ?, model_id = ?,
                    error_code = NULL, current_attempt_digest = NULL, attempt_started_at = NULL,
                    updated_at = ?
                WHERE workflow_id = ? AND current_attempt_digest = ?
                """,
                (
                    state,
                    proposal_json,
                    int(row["proposal_revision"]) + 1,
                    model_id,
                    now.isoformat(),
                    key.workflow_id,
                    attempt_digest,
                ),
            )
            connection.execute(
                "UPDATE local_suggestion_attempts SET state = 'completed' "
                "WHERE project_id = ? AND workflow_id = ? AND idempotency_digest = ?",
                (key.project_id, key.workflow_id, attempt_digest),
            )
            stored = connection.execute(
                "SELECT * FROM local_suggestion_workflows WHERE workflow_id = ?",
                (key.workflow_id,),
            ).fetchone()
        result = _stored(stored)
        if result is None:
            raise LocalSuggestionStoreConflict("suggestion request was not persisted")
        return result

    def fail(
        self,
        key: LocalSuggestionKey,
        attempt_digest: str,
        error_code: str,
        *,
        now: datetime,
    ) -> StoredLocalSuggestion:
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE local_suggestion_workflows
                SET state = 'failed', proposal_json = NULL, model_id = NULL, error_code = ?,
                    current_attempt_digest = NULL, attempt_started_at = NULL, updated_at = ?
                WHERE workflow_id = ? AND state = 'pending' AND current_attempt_digest = ?
                """,
                (error_code, now.isoformat(), key.workflow_id, attempt_digest),
            )
            connection.execute(
                "UPDATE local_suggestion_attempts SET state = 'failed', error_code = ? "
                "WHERE project_id = ? AND workflow_id = ? AND idempotency_digest = ?",
                (error_code, key.project_id, key.workflow_id, attempt_digest),
            )
            stored = connection.execute(
                "SELECT * FROM local_suggestion_workflows WHERE workflow_id = ?",
                (key.workflow_id,),
            ).fetchone()
        result = _stored(stored)
        if result is None:
            raise LocalSuggestionStoreConflict("suggestion request was not persisted")
        return result

    def decide(
        self,
        key: LocalSuggestionKey,
        expected_revision: int,
        decision: Literal["edit", "confirm", "reject"],
        proposal_json: str | None,
        actor_id: str,
        workflow_kind: WorkflowKind,
        receipt: ReviewDecisionReceiptRecord,
        *,
        correction_dimensions: Sequence[CorrectionDimension] = (),
        semantic_edit_count: int = 0,
        now: datetime,
    ) -> StoredLocalSuggestion:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM local_suggestion_workflows WHERE workflow_id = ?",
                (key.workflow_id,),
            ).fetchone()
            record = _stored(row)
            if (
                record is None
                or record.state not in {"proposed", "edited"}
                or record.revision != expected_revision
            ):
                raise LocalSuggestionStoreConflict("suggestion decision is stale or no longer pending")
            if decision == "edit" and proposal_json is None:
                raise LocalSuggestionStoreConflict("edited proposal is required")
            next_state = "edited" if decision == "edit" else "confirmed" if decision == "confirm" else "rejected"
            next_revision = record.revision + 1 if decision == "edit" else record.revision
            if receipt.decision != decision:
                raise LocalSuggestionStoreConflict("review receipt does not match suggestion decision")
            proposal_started = (
                _parse_timestamp(str(row["updated_at"])) if row is not None else None
            )
            review_latency_ms = (
                int((receipt.occurred_at - proposal_started).total_seconds() * 1000)
                if proposal_started is not None and receipt.occurred_at >= proposal_started
                else None
            )
            next_proposal = proposal_json if decision == "edit" else record.proposal_json
            connection.execute(
                """
                UPDATE local_suggestion_workflows
                SET state = ?, proposal_json = ?, proposal_revision = ?,
                    latest_receipt_digest = ?, updated_at = ?
                WHERE workflow_id = ? AND proposal_revision = ?
                """,
                (
                    next_state,
                    next_proposal,
                    next_revision,
                    receipt.receipt_digest,
                    now.isoformat(),
                    key.workflow_id,
                    expected_revision,
                ),
            )
            updated = connection.execute(
                "SELECT * FROM local_suggestion_workflows WHERE workflow_id = ?",
                (key.workflow_id,),
            ).fetchone()
            self.telemetry.append_review(
                connection,
                key.project_id,
                actor_id,
                key.workflow_id,
                workflow_kind,
                receipt,
                correction_dimensions=correction_dimensions,
                semantic_edit_count=semantic_edit_count,
                review_latency_ms=review_latency_ms,
            )
        result = _stored(updated)
        if result is None:
            raise LocalSuggestionStoreConflict("suggestion decision was not persisted")
        return result


def _cache_fields(key: LocalSuggestionKey) -> dict[str, object]:
    return {
        "project": key.project_id,
        "sourceDigest": _digest(key.source_version_id),
        "sourceRevision": key.source_version_revision,
        "itemDigest": _digest(key.item_handle),
        "itemRevision": key.item_revision,
        "evidenceDigest": key.evidence_digest,
    }


def _stored(row: sqlite3.Row | Mapping[str, object] | None) -> StoredLocalSuggestion | None:
    if row is None:
        return None
    typed_row: Mapping[str, object] = (
        cast(Mapping[str, object], dict(row)) if isinstance(row, sqlite3.Row) else row
    )
    return StoredLocalSuggestion(
        workflow_id=_row_text(typed_row["workflow_id"]),
        state=_row_text(typed_row["state"]),
        proposal_json=_row_optional_text(typed_row["proposal_json"]),
        revision=_row_int(typed_row["proposal_revision"]),
        source_version_revision=_row_int(typed_row["source_version_revision"]),
        evidence_digest=_row_text(typed_row["evidence_digest"]),
        model_id=_row_optional_text(typed_row["model_id"]),
        error_code=_row_optional_text(typed_row["error_code"]),
        receipt_digest=_row_optional_text(typed_row["latest_receipt_digest"]),
    )


def _row_text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("stored suggestion field must be text")
    return value


def _row_optional_text(value: object) -> str | None:
    if value is None:
        return None
    return _row_text(value)


def _row_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("stored suggestion field must be an integer")
    return value


def _budget(
    connection: sqlite3.Connection,
    project_id: str,
    actor_digest: str,
    window: date,
    user_limit: int,
    project_limit: int,
) -> LocalSuggestionBudget:
    user_count = _counter(connection, "", "user", actor_digest, window)
    project_count = _counter(connection, project_id, "project", "project", window)
    next_day = datetime.combine(window + timedelta(days=1), time.min, tzinfo=UTC)
    return LocalSuggestionBudget(
        user_limit=user_limit,
        user_remaining=max(0, user_limit - user_count),
        project_limit=project_limit,
        project_remaining=max(0, project_limit - project_count),
        resets_at=next_day,
    )


def _counter(
    connection: sqlite3.Connection, project_id: str, scope: str, scope_digest: str, window: date
) -> int:
    row = connection.execute(
        """
        SELECT request_count FROM local_suggestion_budget_counters
        WHERE project_id = ? AND scope = ? AND scope_digest = ? AND window_date = ?
        """,
        (project_id, scope, scope_digest, window.isoformat()),
    ).fetchone()
    return int(row["request_count"]) if row is not None else 0


def _increment_budget(
    connection: sqlite3.Connection, scope: str, project_id: str, scope_digest: str, window: date
) -> None:
    connection.execute(
        """
        INSERT INTO local_suggestion_budget_counters(
            project_id, scope, scope_digest, window_date, request_count
        ) VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(project_id, scope, scope_digest, window_date)
        DO UPDATE SET request_count = request_count + 1
        """,
        (project_id, scope, scope_digest, window.isoformat()),
    )


def _window_date(now: datetime) -> date:
    return now.astimezone(UTC).date()


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _stable_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8", "strict"
    )


def _digest(value: str | bytes) -> str:
    payload = value.encode("utf-8", "strict") if isinstance(value, str) else value
    return hashlib.sha256(payload).hexdigest()
