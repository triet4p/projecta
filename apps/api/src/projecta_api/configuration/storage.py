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
                """
            )
            self._connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (1, utc_now()),
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
