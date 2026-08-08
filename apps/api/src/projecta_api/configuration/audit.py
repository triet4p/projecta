"""Redacted configuration audit records."""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

from projecta_api.configuration.storage import OperationalDatabase, utc_now


class ConfigurationAudit:
    """Persist and log only the allowlisted configuration audit fields."""

    def __init__(self, database: OperationalDatabase, logger: logging.Logger | None = None) -> None:
        self._database = database
        self._logger = logger or logging.getLogger(__name__)

    def record(
        self,
        *,
        scope: str,
        actor_id: str,
        request_id: str,
        operation: str,
        outcome: str,
        provider_type: str | None = None,
        base_url: str | None = None,
        revision_before: int | None = None,
        revision_after: int | None = None,
        latency_ms: int | None = None,
    ) -> None:
        host = _safe_host(base_url)
        self._database.execute(
            """
            INSERT INTO configuration_audit(
                scope, actor_id, request_id, operation,
                profile_revision_before, profile_revision_after,
                provider_type, provider_host, outcome, latency_ms, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scope,
                actor_id,
                request_id,
                operation,
                revision_before,
                revision_after,
                provider_type,
                host,
                outcome,
                latency_ms,
                utc_now(),
            ),
        )
        self._logger.info(
            "configuration.audit operation=%s outcome=%s scope=%s actor=%s request=%s revisionBefore=%s revisionAfter=%s provider=%s host=%s latencyMs=%s",
            operation,
            outcome,
            scope,
            actor_id,
            request_id,
            revision_before,
            revision_after,
            provider_type,
            host,
            latency_ms,
        )


def _safe_host(base_url: str | None) -> str | None:
    """Return only the hostname, never credentials, query, path, or fragments."""
    if not base_url:
        return None
    return urlsplit(base_url).hostname
