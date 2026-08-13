"""Opaque connector secret-reference binding over the approved SecretStore port."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import SecretStr

from projecta_api.configuration.ports import (
    SecretScope,
    SecretStore,
    VersionedSecretStore,
)
from projecta_api.operational.audit import SecurityAuditSink, emit_safe
from projecta_api.operational.ports import InstallationRecord
from projecta_api.secrets.openbao import OpenBaoSecretError

_SECRET_REFERENCE = re.compile(r"^secret_[A-Za-z0-9_-]{10,128}$")


class ConnectorSecretError(RuntimeError):
    """Safe secret boundary failure without reference, project, or plaintext."""

    def __init__(self, code: str) -> None:
        self.code = code if code in {
            "SECRET_REFERENCE_INVALID",
            "SECRET_SCOPE_FORBIDDEN",
            "SECRET_UNAVAILABLE",
            "SECRET_SEALED",
            "SECRET_UNAUTHORIZED",
            "SECRET_MISSING",
            "SECRET_REVOKED",
            "SECRET_VERSION_STALE",
            "SECRET_INVALID_SCOPE",
        } else "SECRET_REFERENCE_INVALID"
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class ConnectorSecretBinding:
    project_id: str
    installation_id: str
    reference: str
    scope: SecretScope | None = None


class ConnectorSecretPolicy:
    """Validate and resolve only the reference bound to an authorized installation."""

    def __init__(
        self,
        secret_store: SecretStore | VersionedSecretStore,
        audit_sink: SecurityAuditSink | None = None,
    ) -> None:
        self._secret_store = secret_store
        self._audit_sink = audit_sink

    @staticmethod
    def validate_reference(reference: str | None) -> str:
        if reference is None or not _SECRET_REFERENCE.fullmatch(reference):
            raise ConnectorSecretError("SECRET_REFERENCE_INVALID")
        return reference

    def bind(
        self,
        project_id: str,
        installation_id: str,
        reference: str | None,
        *,
        connector_type: str = "json-mock",
        provider_tenant: str = "default",
        installation_revision: int = 1,
    ) -> ConnectorSecretBinding:
        scope = SecretScope(
            project_id,
            installation_id,
            connector_type,
            provider_tenant,
            installation_revision,
        )
        return ConnectorSecretBinding(
            project_id=project_id,
            installation_id=installation_id,
            reference=self.validate_reference(reference),
            scope=scope,
        )

    def resolve_for_installation(
        self, project_id: str, installation: InstallationRecord
    ) -> SecretStr:
        if installation.project_id != project_id or not installation.secret_reference:
            raise ConnectorSecretError("SECRET_SCOPE_FORBIDDEN")
        reference = self.validate_reference(installation.secret_reference)
        try:
            if isinstance(self._secret_store, VersionedSecretStore):
                scope = SecretScope(
                    project_id,
                    installation.installation_id,
                    installation.connector_type,
                    _provider_tenant(installation),
                    installation.revision,
                )
                result = self._secret_store.resolve_scoped(scope, reference).secret
            else:
                result = self._secret_store.resolve(reference)
            emit_safe(
                self._audit_sink,
                category="secret",
                action="secret.resolve",
                outcome="succeeded",
                correlation_id=f"secret-{installation.revision}",
                project_id=project_id,
                revision=installation.revision,
            )
            return result
        except OpenBaoSecretError as exc:
            emit_safe(
                self._audit_sink,
                category="secret",
                action="secret.resolve",
                outcome="failed",
                correlation_id=f"secret-{installation.revision}",
                project_id=project_id,
                revision=installation.revision,
            )
            raise ConnectorSecretError(_map_secret_error(exc.code)) from exc
        except ValueError as exc:
            emit_safe(
                self._audit_sink,
                category="secret",
                action="secret.resolve",
                outcome="failed",
                correlation_id=f"secret-{installation.revision}",
                project_id=project_id,
                revision=installation.revision,
            )
            raise ConnectorSecretError("SECRET_INVALID_SCOPE") from exc
        except Exception as exc:  # noqa: BLE001 - store failures are intentionally finite.
            emit_safe(
                self._audit_sink,
                category="secret",
                action="secret.resolve",
                outcome="failed",
                correlation_id=f"secret-{installation.revision}",
                project_id=project_id,
                revision=installation.revision,
            )
            raise ConnectorSecretError("SECRET_UNAVAILABLE") from exc


def _provider_tenant(installation: InstallationRecord) -> str:
    value = installation.capability_snapshot.get("providerTenant", "default")
    return value if isinstance(value, str) and value else "default"


def _map_secret_error(code: str) -> str:
    return {
        "SEALED": "SECRET_SEALED",
        "UNAVAILABLE": "SECRET_UNAVAILABLE",
        "UNAUTHORIZED": "SECRET_UNAUTHORIZED",
        "MISSING": "SECRET_MISSING",
        "REVOKED": "SECRET_REVOKED",
        "STALE": "SECRET_VERSION_STALE",
        "INVALID_SCOPE": "SECRET_INVALID_SCOPE",
        "ROTATION_CONFLICT": "SECRET_VERSION_STALE",
        "REFERENCE_INVALID": "SECRET_REFERENCE_INVALID",
        "SCOPE_REQUIRED": "SECRET_SCOPE_FORBIDDEN",
    }.get(code, "SECRET_UNAVAILABLE")
