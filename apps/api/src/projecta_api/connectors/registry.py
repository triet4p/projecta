"""Explicit connector registry and provider-neutral adapter port."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from projecta_api.connectors.contracts import (
    ConnectorDescriptor,
    InstallationConfig,
    PullEventsCommand,
    PullEventsResult,
)


class AdapterContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    project_id: str = Field(alias="projectId")
    installation_id: str = Field(alias="installationId")
    connector_type: str = Field(alias="connectorType")
    correlation_id: str = Field(alias="correlationId")
    deadline: datetime


class InstallationValidation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    outcome: str = Field(pattern="^(valid|invalid|unsupported|unavailable|cancelled|deadline-exceeded)$")
    code: str | None = Field(default=None, max_length=64)


class ResourceResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    content_type: str = Field(alias="contentType", max_length=64)
    content_bytes: bytes = Field(alias="contentBytes", max_length=1024 * 1024)
    content_hash: str = Field(alias="contentHash", max_length=71)


class IdentityHintResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    state: str = Field(pattern="^(none|ambiguous|hint)$")
    source_system: str | None = Field(default=None, alias="sourceSystem", max_length=128)
    external_id: str | None = Field(default=None, alias="externalId", max_length=512)
    display_label: str | None = Field(default=None, alias="displayLabel", max_length=512)


class ConnectorAdapter(Protocol):
    """Provider-neutral adapter surface; no Semantic Core or filesystem client."""

    def descriptor(self) -> ConnectorDescriptor: ...

    async def validate_installation(
        self, config: InstallationConfig, context: AdapterContext
    ) -> InstallationValidation: ...

    async def pull_events(self, command: PullEventsCommand) -> PullEventsResult: ...

    async def fetch_resource(
        self, external_reference: str, context: AdapterContext
    ) -> ResourceResult: ...

    async def resolve_identity_hint(
        self, external_reference: str, context: AdapterContext
    ) -> IdentityHintResult: ...


class ConnectorRegistryError(RuntimeError):
    """Finite registry error without provider or resource details."""

    def __init__(self, code: str) -> None:
        self.code = code if code in {"ADAPTER_UNKNOWN_TYPE", "ADAPTER_DUPLICATE_REGISTRATION"} else "ADAPTER_CONTRACT_UNSUPPORTED"
        super().__init__(self.code)


class ConnectorRegistry:
    """Resolve only adapters registered by application composition."""

    def __init__(self) -> None:
        self._adapters: dict[str, ConnectorAdapter] = {}

    def register(self, adapter: ConnectorAdapter) -> None:
        descriptor = adapter.descriptor()
        connector_type = descriptor.connector_type
        if connector_type in self._adapters:
            raise ConnectorRegistryError("ADAPTER_DUPLICATE_REGISTRATION")
        self._adapters[connector_type] = adapter

    def resolve(self, connector_type: str) -> ConnectorAdapter:
        adapter = self._adapters.get(connector_type)
        if adapter is None:
            raise ConnectorRegistryError("ADAPTER_UNKNOWN_TYPE")
        return adapter

    def catalog(self) -> tuple[ConnectorDescriptor, ...]:
        return tuple(self._adapters[key].descriptor() for key in sorted(self._adapters))

    def capabilities(self, connector_type: str) -> frozenset[str]:
        return frozenset(self.resolve(connector_type).descriptor().capabilities)
