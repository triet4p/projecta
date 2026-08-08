"""Ports separating application composition from configuration sources."""

from typing import Protocol

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
