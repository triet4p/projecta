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
    InstallationConfig,
    InstallationSnapshot,
)
from projecta_api.connectors.github_public_issues_setup import GitHubPublicIssuesSetupResolver
from projecta_api.connectors.registry import AdapterContext, ConnectorRegistry
from projecta_api.connectors.secrets import ConnectorSecretPolicy
from projecta_api.connectors.teams_setup import TeamsSetupResolver
from projecta_api.context import TrustedActorContext
from projecta_api.operational.ports import ConnectorOperationalRepository, InstallationRecord


class InstallationMutation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    installation_id: str = Field(alias="installationId", min_length=1, max_length=128)
    project_id: str = Field(alias="projectId", min_length=1, max_length=128)
    connector_type: Literal["json-mock", "teams", "github-public-issues"] = Field(alias="connectorType")
    fixture_reference: str = Field(default="fixture://teams", alias="fixtureReference", min_length=1, max_length=512)
    capabilities: tuple[ConnectorCapability, ...] = ("inbound-import",)
    secret_reference: str | None = Field(default=None, alias="secretReference")
    provider_config: dict[str, object] | None = Field(default=None, alias="providerConfig")
    teams_setup_handle: str | None = Field(default=None, alias="teamsSetupHandle", min_length=10, max_length=128)
    github_setup_handle: str | None = Field(
        default=None, alias="githubSetupHandle", min_length=10, max_length=128
    )
    expected_revision: int | None = Field(default=None, alias="expectedRevision", ge=1)


class InstallationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    fixture_reference: str | None = Field(default=None, alias="fixtureReference", max_length=512)
    capabilities: tuple[ConnectorCapability, ...] | None = None
    secret_reference: str | None = Field(default=None, alias="secretReference")
    provider_config: dict[str, object] | None = Field(default=None, alias="providerConfig")
    teams_setup_handle: str | None = Field(default=None, alias="teamsSetupHandle", min_length=10, max_length=128)
    github_setup_handle: str | None = Field(
        default=None, alias="githubSetupHandle", min_length=10, max_length=128
    )
    expected_revision: int = Field(alias="expectedRevision", ge=1)


class ConnectorInstallationService:
    """Lifecycle service that rechecks policy and adapter capability on every mutation."""

    def __init__(
        self,
        repository: ConnectorOperationalRepository,
        policy: ConnectorPolicy,
        registry: ConnectorRegistry,
        secret_policy: ConnectorSecretPolicy | None = None,
        teams_setup_resolver: TeamsSetupResolver | None = None,
        github_setup_resolver: GitHubPublicIssuesSetupResolver | None = None,
    ) -> None:
        self._repository = repository
        self._policy = policy
        self._registry = registry
        self._secret_policy = secret_policy
        self._teams_setup_resolver = teams_setup_resolver
        self._github_setup_resolver = github_setup_resolver

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
        provider_config = request.provider_config
        fixture_reference = request.fixture_reference
        secret_reference = request.secret_reference
        installation_id = request.installation_id
        if request.connector_type == "teams":
            if request.teams_setup_handle is None or self._teams_setup_resolver is None:
                raise ValueError("ADAPTER_CONFIGURATION_UNAVAILABLE")
            setup = self._teams_setup_resolver.consume(
                request.teams_setup_handle, request.project_id
            )
            installation_id = setup.installation_id
            provider_config = setup.provider_config
            fixture_reference = "fixture://teams/" + installation_id
            configured_secret = provider_config.get("secretReference")
            secret_reference = configured_secret if isinstance(configured_secret, str) else None
        elif request.connector_type == "github-public-issues":
            if request.github_setup_handle is None or self._github_setup_resolver is None:
                raise ValueError("ADAPTER_CONFIGURATION_UNAVAILABLE")
            if request.provider_config is not None or request.secret_reference is not None:
                raise ValueError("ADAPTER_CONFIGURATION_UNAVAILABLE")
            setup = self._github_setup_resolver.consume(
                request.github_setup_handle,
                request.project_id,
                context.actor_id,
                request.expected_revision or 1,
            )
            installation_id = setup.installation_id
            provider_config = setup.config.model_dump(mode="json", by_alias=True)
            fixture_reference = "fixture://github-public-issues/" + installation_id
            secret_reference = None
        config = InstallationConfig(
            fixtureReference=fixture_reference,
            declaredCapabilities=request.capabilities,
            providerConfig=provider_config,
        )
        validation = await adapter.validate_installation(
            config,
            AdapterContext(
                projectId=request.project_id,
                installationId=installation_id,
                connectorType=request.connector_type,
                correlationId=context.request_id,
                deadline=_deadline(),
            ),
        )
        if validation.outcome != "valid":
            raise ValueError(validation.code or "ADAPTER_INSTALLATION_INVALID")
        if secret_reference is not None:
            if self._secret_policy is None:
                raise ValueError("SECRET_REFERENCE_INVALID")
            self._secret_policy.validate_reference(secret_reference)
        record = await asyncio.to_thread(
            self._repository.upsert_installation,
            project_id=request.project_id,
            installation_id=installation_id,
            connector_type=request.connector_type,
            capability_snapshot={
                "capabilities": list(request.capabilities),
                "fixtureReference": fixture_reference,
                "providerTenant": _provider_tenant_config(provider_config),
                "providerConfig": provider_config,
            },
            secret_reference=secret_reference,
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
        provider_config = patch.provider_config or _provider_config(current)
        secret_reference = patch.secret_reference if patch.secret_reference is not None else current.secret_reference
        if current.connector_type == "teams":
            if patch.teams_setup_handle is None:
                if patch.provider_config is not None or patch.secret_reference is not None or patch.fixture_reference is not None:
                    raise ValueError("ADAPTER_CONFIGURATION_UNAVAILABLE")
                provider_config = _provider_config(current)
                secret_reference = current.secret_reference
                fixture_reference = _fixture_reference(current)
            else:
                if self._teams_setup_resolver is None:
                    raise ValueError("ADAPTER_CONFIGURATION_UNAVAILABLE")
                setup = self._teams_setup_resolver.consume(patch.teams_setup_handle, project_id)
                if setup.installation_id != installation_id:
                    raise ValueError("ADAPTER_CONFIGURATION_UNAVAILABLE")
                provider_config = setup.provider_config
                fixture_reference = "fixture://teams/" + installation_id
                configured_secret = provider_config.get("secretReference")
                secret_reference = configured_secret if isinstance(configured_secret, str) else None
        elif current.connector_type == "github-public-issues":
            if patch.github_setup_handle is None:
                if (
                    patch.provider_config is not None
                    or patch.secret_reference is not None
                    or patch.fixture_reference is not None
                ):
                    raise ValueError("ADAPTER_CONFIGURATION_UNAVAILABLE")
            else:
                if self._github_setup_resolver is None:
                    raise ValueError("ADAPTER_CONFIGURATION_UNAVAILABLE")
                setup = self._github_setup_resolver.consume(
                    patch.github_setup_handle,
                    project_id,
                    context.actor_id,
                    patch.expected_revision,
                )
                if setup.installation_id != installation_id:
                    raise ValueError("ADAPTER_CONFIGURATION_UNAVAILABLE")
                provider_config = setup.config.model_dump(mode="json", by_alias=True)
                fixture_reference = "fixture://github-public-issues/" + installation_id
                secret_reference = None
        adapter = self._registry.resolve(current.connector_type)
        self._validate_capabilities(capabilities, adapter.descriptor().capabilities)
        validation = await adapter.validate_installation(
            InstallationConfig(
                fixtureReference=fixture_reference,
                declaredCapabilities=capabilities,
                providerConfig=provider_config,
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
        if secret_reference is not None:
            if self._secret_policy is None:
                raise ValueError("SECRET_REFERENCE_INVALID")
            self._secret_policy.validate_reference(secret_reference)
        record = await asyncio.to_thread(
            self._repository.upsert_installation,
            project_id=project_id,
            installation_id=installation_id,
            connector_type=current.connector_type,
            capability_snapshot={
                "capabilities": list(capabilities),
                "fixtureReference": fixture_reference,
                "providerTenant": _provider_tenant_config(provider_config),
                "providerConfig": provider_config,
            },
            secret_reference=secret_reference,
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


def _provider_tenant(record: InstallationRecord) -> str:
    value = record.capability_snapshot.get("providerTenant", "default")
    return value if isinstance(value, str) and value else "default"


def _provider_tenant_config(value: dict[str, object] | None) -> str:
    if value is None:
        return "default"
    tenant = value.get("tenantId")
    return tenant if isinstance(tenant, str) and tenant else "default"


def _provider_config(record: InstallationRecord) -> dict[str, object] | None:
    value = record.capability_snapshot.get("providerConfig")
    return cast(dict[str, object], value) if isinstance(value, dict) else None


def _snapshot(record: InstallationRecord) -> InstallationSnapshot:
    return InstallationSnapshot(
        installationId=record.installation_id,
        projectId=record.project_id,
        connectorType=cast(Literal["json-mock", "teams", "github-public-issues"], record.connector_type),
        capabilities=_capabilities(record),
        enabled=record.enabled,
        revision=record.revision,
        fixtureReference=_fixture_reference(record),
        secretConfigured=record.secret_reference is not None,
    )


def _deadline():
    return datetime.now(UTC) + timedelta(seconds=30)
