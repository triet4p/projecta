"""Single-use operator setup handles for Teams installations."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Protocol

from sqlalchemy import insert, update

from projecta_api.operational.database import ConnectorDatabase
from projecta_api.operational.schema import TeamsSetupHandle


class TeamsSetupError(RuntimeError):
    """Finite setup failure that never exposes the supplied handle."""


@dataclass(frozen=True, slots=True)
class TeamsSetupRecord:
    project_id: str
    installation_id: str
    provider_config: dict[str, object]
    expires_at: datetime


class TeamsSetupResolver(Protocol):
    def consume(self, handle: str, project_id: str) -> TeamsSetupRecord: ...


class InMemoryTeamsSetupRegistry:
    """Deterministic single-use registry for tests."""

    def __init__(self) -> None:
        self._records: dict[str, TeamsSetupRecord] = {}
        self._lock = RLock()

    def issue(
        self,
        project_id: str,
        installation_id: str,
        provider_config: dict[str, object],
        *,
        ttl_seconds: int = 600,
    ) -> str:
        handle = "setup_" + secrets.token_urlsafe(24)
        record = TeamsSetupRecord(
            project_id,
            installation_id,
            dict(provider_config),
            datetime.now(UTC) + timedelta(seconds=max(60, min(ttl_seconds, 3600))),
        )
        with self._lock:
            self._records[_digest(handle)] = record
        return handle

    def consume(self, handle: str, project_id: str) -> TeamsSetupRecord:
        with self._lock:
            key = _digest(handle)
            record = self._records.get(key)
            if record is not None and record.project_id == project_id:
                del self._records[key]
        if record is None or record.project_id != project_id or record.expires_at <= datetime.now(UTC):
            raise TeamsSetupError("TEAMS_SETUP_INVALID")
        return record


class PostgresTeamsSetupRegistry:
    """Persist only a handle digest and non-secret provider binding."""

    def __init__(self, database: ConnectorDatabase) -> None:
        self._database = database

    def issue(
        self,
        project_id: str,
        installation_id: str,
        provider_config: dict[str, object],
        *,
        ttl_seconds: int = 600,
    ) -> str:
        handle = "setup_" + secrets.token_urlsafe(24)
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=max(60, min(ttl_seconds, 3600)))
        with self._database.connection(operation="teams_setup_issue") as connection:
            connection.execute(
                insert(TeamsSetupHandle).values(
                    setup_hash=_digest(handle),
                    project_id=project_id,
                    installation_id=installation_id,
                    provider_config=dict(provider_config),
                    expires_at=expires_at,
                    consumed_at=None,
                    created_at=now,
                )
            )
        return handle

    def consume(self, handle: str, project_id: str) -> TeamsSetupRecord:
        now = datetime.now(UTC)
        with self._database.connection(operation="teams_setup_consume") as connection:
            row = connection.execute(
                update(TeamsSetupHandle)
                .where(
                    TeamsSetupHandle.setup_hash == _digest(handle),
                    TeamsSetupHandle.project_id == project_id,
                    TeamsSetupHandle.consumed_at.is_(None),
                    TeamsSetupHandle.expires_at > now,
                )
                .values(consumed_at=now)
                .returning(
                    TeamsSetupHandle.project_id,
                    TeamsSetupHandle.installation_id,
                    TeamsSetupHandle.provider_config,
                    TeamsSetupHandle.expires_at,
                )
            ).one_or_none()
        if row is None:
            raise TeamsSetupError("TEAMS_SETUP_INVALID")
        return TeamsSetupRecord(
            str(row.project_id),
            str(row.installation_id),
            dict(row.provider_config),
            row.expires_at,
        )


def _digest(handle: str) -> str:
    if not handle.startswith("setup_") or not 16 <= len(handle) <= 128:
        raise TeamsSetupError("TEAMS_SETUP_INVALID")
    return hashlib.sha256(handle.encode("utf-8")).hexdigest()
