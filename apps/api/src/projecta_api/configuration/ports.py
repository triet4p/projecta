"""Ports separating application composition from configuration sources."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

from pydantic import SecretStr

from projecta_api.configuration.models import LLMConfigurationSnapshot
from projecta_api.context import TrustedRequestContext


class RuntimeConfigurationProvider(Protocol):
    """Resolve one provider-neutral LLM snapshot for application composition."""

    def resolve_llm(self, context: TrustedRequestContext | None = None) -> LLMConfigurationSnapshot:
        """Return an immutable server-only configuration snapshot."""
        ...


class SecretStore(Protocol):
    """Provider-neutral opaque-reference secret boundary."""

    def create(self, secret: SecretStr) -> str:
        """Persist a secret and return an opaque reference."""
        ...

    def resolve(self, reference: str) -> SecretStr:
        """Resolve an opaque reference for server-side use only."""
        ...

    def delete(self, reference: str | None) -> None:
        """Delete a reference idempotently."""
        ...


SecretStatus = Literal[
    "ready",
    "sealed",
    "unavailable",
    "unauthorized",
    "missing",
    "revoked",
    "stale",
    "invalid-scope",
    "rotation-conflict",
]


@dataclass(frozen=True, slots=True)
class SecretScope:
    """Projecta-owned scope; provider paths never cross this boundary."""

    project_id: str
    installation_id: str
    connector_type: str
    provider_tenant: str
    installation_revision: int

    def __post_init__(self) -> None:
        values = (self.project_id, self.installation_id, self.connector_type, self.provider_tenant)
        if any(not value or len(value) > 128 or "/" in value or "\\" in value for value in values):
            raise ValueError("secret scope contains an invalid segment")
        if self.installation_revision < 1:
            raise ValueError("secret scope revision must be positive")

    @property
    def path(self) -> str:
        return (
            "projecta/connector/v1/"
            f"{self.project_id}/{self.installation_id}/{self.connector_type}/"
            f"{self.provider_tenant}/r{self.installation_revision}"
        )


@dataclass(frozen=True, slots=True)
class SecretSnapshot:
    """Immutable in-memory snapshot for one connector operation."""

    reference: str
    version: int
    scope: SecretScope
    secret: SecretStr
    created_at: datetime


@runtime_checkable
class VersionedSecretStore(Protocol):
    """Scoped, versioned runtime secret boundary used by production connectors."""

    def create_scoped(self, scope: SecretScope, secret: SecretStr) -> SecretSnapshot: ...

    def resolve_scoped(
        self, scope: SecretScope, reference: str, version: int | None = None
    ) -> SecretSnapshot: ...

    def rotate_scoped(self, scope: SecretScope, reference: str, secret: SecretStr) -> SecretSnapshot: ...

    def revoke_scoped(self, scope: SecretScope, reference: str, version: int | None = None) -> None: ...

    def readiness(self) -> SecretStatus: ...
