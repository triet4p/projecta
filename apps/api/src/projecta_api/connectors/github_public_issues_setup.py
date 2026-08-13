"""Single-use server setup handles for GitHub Public Issues installations."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Protocol

from sqlalchemy import insert, update

from projecta_api.connectors.github_public_issues import GitHubPublicIssuesInstallationConfig
from projecta_api.operational.database import ConnectorDatabase
from projecta_api.operational.schema import GitHubPublicIssuesSetupHandle


class GitHubPublicIssuesSetupError(RuntimeError):
    """Finite setup failure that never exposes the supplied handle or config."""


@dataclass(frozen=True, slots=True)
class GitHubPublicIssuesSetupRecord:
    project_id: str
    actor_id: str
    installation_id: str
    expected_revision: int
    config: GitHubPublicIssuesInstallationConfig
    expires_at: datetime


class GitHubPublicIssuesSetupResolver(Protocol):
    def consume(
        self, handle: str, project_id: str, actor_id: str, expected_revision: int
    ) -> GitHubPublicIssuesSetupRecord: ...


class InMemoryGitHubPublicIssuesSetupRegistry:
    """Deterministic single-use setup registry for local and unit-test flows."""

    def __init__(self) -> None:
        self._records: dict[str, GitHubPublicIssuesSetupRecord] = {}
        self._lock = RLock()

    def issue(
        self,
        project_id: str,
        actor_id: str,
        installation_id: str,
        config: GitHubPublicIssuesInstallationConfig,
        *,
        expected_revision: int = 1,
        ttl_seconds: int = 600,
    ) -> str:
        handle = "setup_" + secrets.token_urlsafe(24)
        record = GitHubPublicIssuesSetupRecord(
            project_id,
            actor_id,
            installation_id,
            expected_revision,
            config,
            datetime.now(UTC) + timedelta(seconds=max(60, min(ttl_seconds, 3600))),
        )
        with self._lock:
            self._records[_digest(handle)] = record
        return handle

    def consume(
        self, handle: str, project_id: str, actor_id: str, expected_revision: int
    ) -> GitHubPublicIssuesSetupRecord:
        with self._lock:
            key = _digest(handle)
            record = self._records.get(key)
            if (
                record is not None
                and record.project_id == project_id
                and record.actor_id == actor_id
                and record.expected_revision == expected_revision
            ):
                del self._records[key]
        if (
            record is None
            or record.project_id != project_id
            or record.actor_id != actor_id
            or record.expected_revision != expected_revision
            or record.expires_at <= datetime.now(UTC)
        ):
            raise GitHubPublicIssuesSetupError("GITHUB_SETUP_INVALID")
        return record


class PostgresGitHubPublicIssuesSetupRegistry:
    """Persist only a handle digest and the typed non-secret repository binding."""

    def __init__(self, database: ConnectorDatabase) -> None:
        self._database = database

    def issue(
        self,
        project_id: str,
        actor_id: str,
        installation_id: str,
        config: GitHubPublicIssuesInstallationConfig,
        *,
        expected_revision: int = 1,
        ttl_seconds: int = 600,
    ) -> str:
        handle = "setup_" + secrets.token_urlsafe(24)
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=max(60, min(ttl_seconds, 3600)))
        with self._database.connection(operation="github_setup_issue") as connection:
            connection.execute(
                insert(GitHubPublicIssuesSetupHandle).values(
                    setup_hash=_digest(handle),
                    project_id=project_id,
                    actor_id=actor_id,
                    installation_id=installation_id,
                    expected_revision=expected_revision,
                    provider_config=config.model_dump(mode="json", by_alias=True),
                    expires_at=expires_at,
                    consumed_at=None,
                    created_at=now,
                )
            )
        return handle

    def consume(
        self, handle: str, project_id: str, actor_id: str, expected_revision: int
    ) -> GitHubPublicIssuesSetupRecord:
        now = datetime.now(UTC)
        with self._database.connection(operation="github_setup_consume") as connection:
            row = connection.execute(
                update(GitHubPublicIssuesSetupHandle)
                .where(
                    GitHubPublicIssuesSetupHandle.setup_hash == _digest(handle),
                    GitHubPublicIssuesSetupHandle.project_id == project_id,
                    GitHubPublicIssuesSetupHandle.actor_id == actor_id,
                    GitHubPublicIssuesSetupHandle.expected_revision == expected_revision,
                    GitHubPublicIssuesSetupHandle.consumed_at.is_(None),
                    GitHubPublicIssuesSetupHandle.expires_at > now,
                )
                .values(consumed_at=now)
                .returning(
                    GitHubPublicIssuesSetupHandle.project_id,
                    GitHubPublicIssuesSetupHandle.actor_id,
                    GitHubPublicIssuesSetupHandle.installation_id,
                    GitHubPublicIssuesSetupHandle.expected_revision,
                    GitHubPublicIssuesSetupHandle.provider_config,
                    GitHubPublicIssuesSetupHandle.expires_at,
                )
            ).one_or_none()
        if row is None:
            raise GitHubPublicIssuesSetupError("GITHUB_SETUP_INVALID")
        return GitHubPublicIssuesSetupRecord(
            str(row.project_id),
            str(row.actor_id),
            str(row.installation_id),
            int(row.expected_revision),
            GitHubPublicIssuesInstallationConfig.model_validate(row.provider_config),
            row.expires_at,
        )


def _digest(handle: str) -> str:
    if not handle.startswith("setup_") or not 16 <= len(handle) <= 128:
        raise GitHubPublicIssuesSetupError("GITHUB_SETUP_INVALID")
    return hashlib.sha256(handle.encode("utf-8")).hexdigest()
