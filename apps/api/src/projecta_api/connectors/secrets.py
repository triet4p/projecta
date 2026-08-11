"""Opaque connector secret-reference binding over the approved SecretStore port."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import SecretStr

from projecta_api.configuration.ports import SecretStore
from projecta_api.operational.ports import InstallationRecord

_SECRET_REFERENCE = re.compile(r"^secret_[A-Za-z0-9_-]{10,128}$")


class ConnectorSecretError(RuntimeError):
    """Safe secret boundary failure without reference, project, or plaintext."""

    def __init__(self, code: str) -> None:
        self.code = code if code in {
            "SECRET_REFERENCE_INVALID",
            "SECRET_SCOPE_FORBIDDEN",
            "SECRET_UNAVAILABLE",
        } else "SECRET_REFERENCE_INVALID"
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class ConnectorSecretBinding:
    project_id: str
    installation_id: str
    reference: str


class ConnectorSecretPolicy:
    """Validate and resolve only the reference bound to an authorized installation."""

    def __init__(self, secret_store: SecretStore) -> None:
        self._secret_store = secret_store

    @staticmethod
    def validate_reference(reference: str | None) -> str:
        if reference is None or not _SECRET_REFERENCE.fullmatch(reference):
            raise ConnectorSecretError("SECRET_REFERENCE_INVALID")
        return reference

    def bind(
        self, project_id: str, installation_id: str, reference: str | None
    ) -> ConnectorSecretBinding:
        return ConnectorSecretBinding(
            project_id=project_id,
            installation_id=installation_id,
            reference=self.validate_reference(reference),
        )

    def resolve_for_installation(
        self, project_id: str, installation: InstallationRecord
    ) -> SecretStr:
        if installation.project_id != project_id or not installation.secret_reference:
            raise ConnectorSecretError("SECRET_SCOPE_FORBIDDEN")
        reference = self.validate_reference(installation.secret_reference)
        try:
            return self._secret_store.resolve(reference)
        except Exception as exc:  # noqa: BLE001 - store failures are intentionally finite.
            raise ConnectorSecretError("SECRET_UNAVAILABLE") from exc
