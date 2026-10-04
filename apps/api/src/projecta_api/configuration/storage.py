"""Small SQLite operational persistence baseline for Sprint 7."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock

from pydantic import AnyHttpUrl

from projecta_api.configuration.errors import ConfigurationConflict
from projecta_api.configuration.models import LLMProfile


def utc_now() -> str:
    """Return a stable, timezone-aware operational timestamp."""
    return datetime.now(UTC).isoformat()


class OperationalDatabase:
    """Own one SQLite connection and apply idempotent operational migrations."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = RLock()
        self._connection = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._connection.row_factory = sqlite3.Row
        with self._lock:
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS secret_records (
                    secret_reference TEXT PRIMARY KEY,
                    ciphertext BLOB NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS llm_profiles (
                    scope TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    provider_type TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    model TEXT NOT NULL,
                    active INTEGER NOT NULL,
                    revision INTEGER NOT NULL,
                    credential_configured INTEGER NOT NULL,
                    secret_reference TEXT,
                    health TEXT NOT NULL,
                    last_checked_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(secret_reference) REFERENCES secret_records(secret_reference)
                );
                CREATE TABLE IF NOT EXISTS configuration_audit (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    profile_revision_before INTEGER,
                    profile_revision_after INTEGER,
                    provider_type TEXT,
                    provider_host TEXT,
                    outcome TEXT NOT NULL,
                    latency_ms INTEGER,
                    recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS local_suggestion_workflows (
                    workflow_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    source_version_digest TEXT NOT NULL,
                    source_version_revision INTEGER NOT NULL CHECK (source_version_revision >= 1),
                    item_handle_digest TEXT NOT NULL,
                    item_revision INTEGER NOT NULL CHECK (item_revision >= 1),
                    evidence_digest TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN (
                        'new', 'pending', 'failed', 'proposed', 'edited',
                        'confirmed', 'rejected', 'abstained'
                    )),
                    proposal_json TEXT,
                    proposal_revision INTEGER NOT NULL DEFAULT 0 CHECK (proposal_revision >= 0),
                    current_attempt_digest TEXT,
                    attempt_started_at TEXT,
                    model_id TEXT,
                    error_code TEXT,
                    latest_receipt_digest TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (
                        project_id, source_version_digest, source_version_revision,
                        item_handle_digest, item_revision, evidence_digest
                    )
                );
                CREATE TABLE IF NOT EXISTS local_suggestion_attempts (
                    attempt_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    actor_digest TEXT NOT NULL,
                    workflow_id TEXT NOT NULL,
                    idempotency_digest TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('pending', 'completed', 'failed')),
                    error_code TEXT,
                    requested_at TEXT NOT NULL,
                    UNIQUE (project_id, actor_digest, idempotency_digest),
                    FOREIGN KEY (workflow_id) REFERENCES local_suggestion_workflows(workflow_id)
                );
                CREATE INDEX IF NOT EXISTS ix_local_suggestion_attempts_budget
                    ON local_suggestion_attempts(project_id, actor_digest, requested_at);
                CREATE TABLE IF NOT EXISTS local_suggestion_budget_counters (
                    project_id TEXT NOT NULL,
                    scope TEXT NOT NULL CHECK (scope IN ('user', 'project')),
                    scope_digest TEXT NOT NULL,
                    window_date TEXT NOT NULL,
                    request_count INTEGER NOT NULL CHECK (request_count >= 0),
                    PRIMARY KEY (project_id, scope, scope_digest, window_date)
                );
                CREATE TABLE IF NOT EXISTS authoring_cost_events (
                    event_id TEXT PRIMARY KEY,
                    project_digest TEXT NOT NULL,
                    actor_digest TEXT NOT NULL,
                    workflow_digest TEXT,
                    workflow_kind TEXT NOT NULL CHECK (workflow_kind IN ('entity', 'relation')),
                    event_type TEXT NOT NULL CHECK (event_type IN (
                        'manual_workflow', 'local_request', 'local_attempt',
                        'manual_edit', 'review', 'accepted_assertion'
                    )),
                    attempt_digest TEXT,
                    receipt_digest TEXT,
                    assertion_digest TEXT,
                    decision TEXT CHECK (decision IN ('confirm', 'edit', 'reject', 'abstain')),
                    local_inference_units INTEGER NOT NULL DEFAULT 0
                        CHECK (local_inference_units >= 0),
                    correction_category TEXT CHECK (
                        correction_category IN ('unchanged', 'minor', 'major')
                    ),
                    correction_dimensions TEXT NOT NULL DEFAULT '[]',
                    semantic_edit_count INTEGER NOT NULL DEFAULT 0
                        CHECK (semantic_edit_count >= 0),
                    review_latency_ms INTEGER CHECK (
                        review_latency_ms IS NULL OR review_latency_ms BETWEEN 0 AND 31536000000
                    ),
                    occurred_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_authoring_cost_scope_workflow
                    ON authoring_cost_events(project_digest, actor_digest, workflow_digest);
                CREATE TRIGGER IF NOT EXISTS authoring_cost_events_append_only_update
                    BEFORE UPDATE ON authoring_cost_events
                    BEGIN SELECT RAISE(ABORT, 'authoring_cost_events is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS authoring_cost_events_append_only_delete
                    BEFORE DELETE ON authoring_cost_events
                    BEGIN SELECT RAISE(ABORT, 'authoring_cost_events is append-only'); END;
                """
            )
            self._connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (1, utc_now()),
            )
            self._connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (2, utc_now()),
            )
            self._connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (3, utc_now()),
            )

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Run one short serialized transaction."""
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                yield self._connection
            except Exception:
                self._connection.rollback()
                raise
            else:
                self._connection.commit()

    @contextmanager
    def read_transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Hold one consistent, serialized SQLite read snapshot."""
        with self._lock:
            self._connection.execute("BEGIN")
            try:
                yield self._connection
            except BaseException:
                self._connection.rollback()
                raise
            else:
                self._connection.commit()

    def execute(self, sql: str, parameters: Sequence[object] = ()) -> sqlite3.Cursor:
        """Execute one statement under the database lock."""
        with self._lock:
            return self._connection.execute(sql, parameters)

    def close(self) -> None:
        """Close the operational connection during application shutdown."""
        with self._lock:
            self._connection.close()


@dataclass(frozen=True, slots=True)
class StoredLLMProfile:
    """Database row with the secret locator kept server-side."""

    scope: str
    profile_id: str
    provider_type: str
    base_url: str
    model: str
    active: bool
    revision: int
    credential_configured: bool
    secret_reference: str | None
    health: str
    last_checked_at: str | None
    created_at: str
    updated_at: str

    def public_model(self) -> LLMProfile:
        """Return the redacted profile response model."""
        return LLMProfile(
            profileId=self.profile_id,
            providerType=self.provider_type,  # type: ignore[arg-type]
            baseUrl=AnyHttpUrl(self.base_url),
            model=self.model,
            active=self.active,
            revision=self.revision,
            credentialConfigured=self.credential_configured,
            health=self.health,  # type: ignore[arg-type]
            lastCheckedAt=self.last_checked_at,
            createdAt=self.created_at,
            updatedAt=self.updated_at,
        )


class LLMProfileRepository:
    """Persist one active profile per trusted project scope."""

    def __init__(self, database: OperationalDatabase) -> None:
        self._database = database

    def get_active(self, scope: str) -> StoredLLMProfile | None:
        row = self._database.execute(
            "SELECT * FROM llm_profiles WHERE scope = ? AND active = 1", (scope,)
        ).fetchone()
        return _profile_from_row(row) if row is not None else None

    def upsert(
        self,
        *,
        scope: str,
        profile_id: str,
        provider_type: str,
        base_url: str,
        model: str,
        secret_reference: str,
        expected_revision: int | None,
    ) -> StoredLLMProfile:
        """Create or replace an active profile with optimistic concurrency."""
        now = utc_now()
        with self._database.transaction() as connection:
            current_row = connection.execute(
                "SELECT * FROM llm_profiles WHERE scope = ?", (scope,)
            ).fetchone()
            current = _profile_from_row(current_row) if current_row is not None else None
            if expected_revision is not None and (
                current is None or current.revision != expected_revision
            ):
                raise ConfigurationConflict()
            revision = 1 if current is None else current.revision + 1
            created_at = now if current is None else current.created_at
            connection.execute(
                """
                INSERT INTO llm_profiles(
                    scope, profile_id, provider_type, base_url, model, active,
                    revision, credential_configured, secret_reference, health,
                    last_checked_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 1, ?, 1, ?, 'unknown', NULL, ?, ?)
                ON CONFLICT(scope) DO UPDATE SET
                    profile_id = excluded.profile_id,
                    provider_type = excluded.provider_type,
                    base_url = excluded.base_url,
                    model = excluded.model,
                    active = 1,
                    revision = excluded.revision,
                    credential_configured = 1,
                    secret_reference = excluded.secret_reference,
                    health = 'unknown',
                    last_checked_at = NULL,
                    updated_at = excluded.updated_at
                """,
                (
                    scope,
                    profile_id,
                    provider_type,
                    base_url,
                    model,
                    revision,
                    secret_reference,
                    created_at,
                    now,
                ),
            )
        result = self.get_active(scope)
        if result is None:
            raise RuntimeError("profile write did not produce an active row")
        return result

    def remove(self, scope: str, expected_revision: int | None) -> StoredLLMProfile | None:
        """Deactivate the active profile and return its prior secret locator."""
        now = utc_now()
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM llm_profiles WHERE scope = ? AND active = 1", (scope,)
            ).fetchone()
            current = _profile_from_row(row) if row is not None else None
            if current is None:
                if expected_revision is not None:
                    raise ConfigurationConflict()
                return None
            if expected_revision is not None and current.revision != expected_revision:
                raise ConfigurationConflict()
            connection.execute(
                """
                UPDATE llm_profiles
                SET active = 0, credential_configured = 0, secret_reference = NULL,
                    revision = ?, updated_at = ?, health = 'unavailable'
                WHERE scope = ?
                """,
                (current.revision + 1, now, scope),
            )
        return current

    def update_health(
        self, scope: str, revision: int, health: str, last_checked_at: str
    ) -> StoredLLMProfile | None:
        """Persist a bounded connection outcome only for the checked revision."""
        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE llm_profiles
                SET health = ?, last_checked_at = ?, updated_at = ?
                WHERE scope = ? AND active = 1 AND revision = ?
                """,
                (health, last_checked_at, utc_now(), scope, revision),
            )
        return self.get_active(scope)


def _profile_from_row(row: sqlite3.Row) -> StoredLLMProfile:
    """Convert a SQLite row without leaking arbitrary database values."""
    return StoredLLMProfile(
        scope=str(row["scope"]),
        profile_id=str(row["profile_id"]),
        provider_type=str(row["provider_type"]),
        base_url=str(row["base_url"]),
        model=str(row["model"]),
        active=bool(row["active"]),
        revision=int(row["revision"]),
        credential_configured=bool(row["credential_configured"]),
        secret_reference=(str(row["secret_reference"]) if row["secret_reference"] else None),
        health=str(row["health"]),
        last_checked_at=(str(row["last_checked_at"]) if row["last_checked_at"] else None),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )
