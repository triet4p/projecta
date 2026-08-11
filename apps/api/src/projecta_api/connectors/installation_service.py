"""Project-scoped installation lifecycle owned by the application service."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from projecta_api.connectors.authorization import (
    ConnectorAuthorizationRequest,
    ConnectorPolicy,
)
from projecta_api.connectors.contracts import (
    ConnectorCapability,
    ConnectorType,
    InstallationConfig,
    InstallationSnapshot,
)
from projecta_api.connectors.registry import AdapterContext, ConnectorRegistry
from projecta_api.connectors.secrets import ConnectorSecretPolicy
from projecta_api.context import TrustedActorContext
from projecta_api.operational.ports import ConnectorOperationalRepository, InstallationRecord


class InstallationMutation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    installation_id: str = Field(alias="installationId", min_length=1, max_length=128)
    project_id: str = Field(alias="projectId", min_length=1, max_length=128)
    connector_type: Literal["json-mock"] = Field(alias="connectorType")
    fixture_reference: str = Field(alias="fixtureReference", min_length=1, max_length=512)
    capabilities: tuple[ConnectorCapability, ...] = ("inbound-import",)
    secret_reference: str | None = Field(default=None, alias="secretReference")
    expected_revision: int | None = Field(default=None, alias="expectedRevision", ge=1)


class InstallationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    fixture_reference: str | None = Field(default=None, alias="fixtureReference", max_length=512)
    capabilities: tuple[ConnectorCapability, ...] | None = None
    secret_reference: str | None = Field(default=None, alias="secretReference")
    expected_revision: int = Field(alias="expectedRevision", ge=1)


class ConnectorInstallationService:
    """Lifecycle service that rechecks policy and adapter capability on every mutation."""

    def __init__(
        self,
        repository: ConnectorOperationalRepository,
        policy: ConnectorPolicy,
        registry: ConnectorRegistry,
        secret_policy: ConnectorSecretPolicy | None = None,
    ) -> None:
        self._repository = repository
        self._policy = policy
        self._registry = registry
        self._secret_policy = secret_policy

    async def create(
        self, context: TrustedActorContext, request: InstallationMutation
    ) -> InstallationSnapshot:
        await self._policy.authorize(
            ConnectorAuthorizationRequest(
                action="installation.create",
                actor_context=context,
                project_id=request.project_id,
                connector_type=request.connector_type,
            )
        )
        adapter = self._registry.resolve(request.connector_type)
        descriptor = adapter.descriptor()
        self._validate_capabilities(request.capabilities, descriptor.capabilities)
        config = InstallationConfig(
            fixtureReference=request.fixture_reference,
            declaredCapabilities=request.capabilities,
        )
        validation = await adapter.validate_installation(
            config,
            AdapterContext(
                projectId=request.project_id,
                installationId=request.installation_id,
                connectorType=request.connector_type,
                correlationId=context.request_id,
                deadline=_deadline(),
            ),
        )
        if validation.outcome != "valid":
            raise ValueError(validation.code or "ADAPTER_INSTALLATION_INVALID")
        if request.secret_reference is not None:
            if self._secret_policy is None:
                raise ValueError("SECRET_REFERENCE_INVALID")
            self._secret_policy.validate_reference(request.secret_reference)
        record = await asyncio.to_thread(
            self._repository.upsert_installation,
            project_id=request.project_id,
            installation_id=request.installation_id,
            connector_type=request.connector_type,
            capability_snapshot={
                "capabilities": list(request.capabilities),
                "fixtureReference": request.fixture_reference,
            },
            secret_reference=request.secret_reference,
            enabled=False,
            expected_revision=None,
            audit_operation="installation.create",
            actor_reference=context.actor_id,
            correlation_id=context.request_id,
        )
        return _snapshot(record)

    async def read(
        self, context: TrustedActorContext, project_id: str, installation_id: str
    ) -> InstallationSnapshot:
        authorized = await self._policy.authorize(
            ConnectorAuthorizationRequest(
                action="installation.read",
                actor_context=context,
                project_id=project_id,
                installation_id=installation_id,
            )
        )
        if authorized.installation is None:
            raise KeyError("connector installation not found")
        return _snapshot(authorized.installation)

    async def update(
        self,
        context: TrustedActorContext,
        project_id: str,
        installation_id: str,
        patch: InstallationPatch,
    ) -> InstallationSnapshot:
        authorized = await self._policy.authorize(
            ConnectorAuthorizationRequest(
                action="installation.update",
                actor_context=context,
                project_id=project_id,
                installation_id=installation_id,
                expected_installation_revision=patch.expected_revision,
            )
        )
        current = authorized.installation
        if current is None:
            raise KeyError("connector installation not found")
        fixture_reference = patch.fixture_reference or _fixture_reference(current)
        capabilities = patch.capabilities or _capabilities(current)
        adapter = self._registry.resolve(current.connector_type)
        self._validate_capabilities(capabilities, adapter.descriptor().capabilities)
        validation = await adapter.validate_installation(
            InstallationConfig(
                fixtureReference=fixture_reference,
                declaredCapabilities=capabilities,
            ),
            AdapterContext(
                projectId=project_id,
                installationId=installation_id,
                connectorType=current.connector_type,
                correlationId=context.request_id,
                deadline=_deadline(),
            ),
        )
        if validation.outcome != "valid":
            raise ValueError(validation.code or "ADAPTER_INSTALLATION_INVALID")
        if patch.secret_reference is not None:
            if self._secret_policy is None:
                raise ValueError("SECRET_REFERENCE_INVALID")
            self._secret_policy.validate_reference(patch.secret_reference)
        record = await asyncio.to_thread(
            self._repository.upsert_installation,
            project_id=project_id,
            installation_id=installation_id,
            connector_type=current.connector_type,
            capability_snapshot={
                "capabilities": list(capabilities),
                "fixtureReference": fixture_reference,
            },
            secret_reference=patch.secret_reference
            if patch.secret_reference is not None
            else current.secret_reference,
            enabled=current.enabled,
            expected_revision=patch.expected_revision,
            audit_operation="installation.update",
            actor_reference=context.actor_id,
            correlation_id=context.request_id,
        )
        return _snapshot(record)

    async def enable_or_disable(
        self,
        context: TrustedActorContext,
        project_id: str,
        installation_id: str,
        expected_revision: int,
        enabled: bool,
    ) -> InstallationSnapshot:
        action = "installation.enable" if enabled else "installation.disable"
        authorized = await self._policy.authorize(
            ConnectorAuthorizationRequest(
                action=action,
                actor_context=context,
                project_id=project_id,
                installation_id=installation_id,
                expected_installation_revision=expected_revision,
            )
        )
        current = authorized.installation
        if current is None:
            raise KeyError("connector installation not found")
        record = await asyncio.to_thread(
            self._repository.upsert_installation,
            project_id=project_id,
            installation_id=installation_id,
            connector_type=current.connector_type,
            capability_snapshot=current.capability_snapshot,
            secret_reference=current.secret_reference,
            enabled=enabled,
            expected_revision=expected_revision,
            audit_operation=action,
            actor_reference=context.actor_id,
            correlation_id=context.request_id,
        )
        return _snapshot(record)

    async def enable(
        self,
        context: TrustedActorContext,
        project_id: str,
        installation_id: str,
        expected_revision: int,
    ) -> InstallationSnapshot:
        return await self.enable_or_disable(
            context, project_id, installation_id, expected_revision, True
        )

    async def disable(
        self,
        context: TrustedActorContext,
        project_id: str,
        installation_id: str,
        expected_revision: int,
    ) -> InstallationSnapshot:
        return await self.enable_or_disable(
            context, project_id, installation_id, expected_revision, False
        )

    @staticmethod
    def _validate_capabilities(
        requested: tuple[ConnectorCapability, ...], supported: tuple[ConnectorCapability, ...]
    ) -> None:
        if (
            len(set(requested)) != len(requested)
            or not requested
            or not set(requested).issubset(set(supported))
        ):
            raise ValueError("ADAPTER_CAPABILITY_UNSUPPORTED")


def _fixture_reference(record: InstallationRecord) -> str:
    value = record.capability_snapshot.get("fixtureReference")
    if not isinstance(value, str):
        raise ValueError("ADAPTER_INSTALLATION_INVALID")
    return value


def _capabilities(record: InstallationRecord) -> tuple[ConnectorCapability, ...]:
    value = record.capability_snapshot.get("capabilities")
    if not isinstance(value, list):
        raise ValueError("ADAPTER_INSTALLATION_INVALID")
    return tuple(item for item in value if isinstance(item, str))  # type: ignore[return-value]


def _snapshot(record: InstallationRecord) -> InstallationSnapshot:
    return InstallationSnapshot(
        installationId=record.installation_id,
        projectId=record.project_id,
        connectorType=cast(ConnectorType, record.connector_type),
        capabilities=_capabilities(record),
        enabled=record.enabled,
        revision=record.revision,
        fixtureReference=_fixture_reference(record),
        secretConfigured=record.secret_reference is not None,
    )


def _deadline():
    return datetime.now(UTC) + timedelta(seconds=30)
