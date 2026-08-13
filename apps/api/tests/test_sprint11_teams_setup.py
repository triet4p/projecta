"""Operator setup and stable Teams credential-scope tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from projecta_api.configuration.ports import SecretScope
from projecta_api.connectors.contracts import PullEventsCommand
from projecta_api.connectors.installation_service import (
    ConnectorInstallationService,
    InstallationMutation,
    InstallationPatch,
)
from projecta_api.connectors.registry import ConnectorRegistry
from projecta_api.connectors.secrets import ConnectorSecretPolicy
from projecta_api.connectors.teams import (
    TeamsAdapter,
    TeamsInstallationConfig,
    _GraphResponse,
)
from projecta_api.connectors.teams_setup import (
    InMemoryTeamsSetupRegistry,
    TeamsSetupError,
)
from projecta_api.context import TrustedActorContext
from projecta_api.operational.ports import InstallationRecord
from projecta_api.secrets.openbao import InMemoryOpenBaoTransport, OpenBaoSecretStore


class _Policy:
    def __init__(self) -> None:
        self.installation: InstallationRecord | None = None

    async def authorize(self, _: object) -> Any:
        return type("Authorized", (), {"installation": self.installation})()


class _Repository:
    def __init__(self, policy: _Policy) -> None:
        self.policy = policy

    def upsert_installation(self, **values: object) -> InstallationRecord:
        current = self.policy.installation
        now = datetime.now(UTC)
        record = InstallationRecord(
            str(values["installation_id"]),
            str(values["project_id"]),
            str(values["connector_type"]),
            cast(dict[str, object], values["capability_snapshot"]),
            cast(str | None, values["secret_reference"]),
            bool(values["enabled"]),
            1 if current is None else current.revision + 1,
            current.created_at if current else now,
            now,
        )
        self.policy.installation = record
        return record


class _Credentials:
    def __init__(self) -> None:
        self.scopes: list[SecretScope] = []

    async def get_token(self, scope: SecretScope, _: str, __: datetime) -> str:
        self.scopes.append(scope)
        return "token"


class _Graph:
    async def get(
        self,
        _: str,
        __: str,
        ___: object,
        ____: datetime,
    ) -> _GraphResponse:
        return _GraphResponse(200, {"value": []}, {})


def _provider_config() -> dict[str, object]:
    return {
        "tenantId": "tenant-1",
        "teamId": "team-1",
        "channelId": "channel-1",
        "secretReference": "secret_abcdefghijk",
        "credentialRevision": 1,
        "capabilities": ["inbound-import"],
    }


def test_setup_handle_is_project_bound_single_use_and_expiring() -> None:
    registry = InMemoryTeamsSetupRegistry()
    handle = registry.issue("project-1", "install-fixed", _provider_config())
    with pytest.raises(TeamsSetupError, match="TEAMS_SETUP_INVALID"):
        registry.consume(handle, "project-2")
    replacement = registry.issue("project-1", "install-fixed", _provider_config())
    assert registry.consume(replacement, "project-1").installation_id == "install-fixed"
    with pytest.raises(TeamsSetupError, match="TEAMS_SETUP_INVALID"):
        registry.consume(replacement, "project-1")


@pytest.mark.asyncio
async def test_enable_revision_does_not_change_credential_scope() -> None:
    setup = InMemoryTeamsSetupRegistry()
    handle = setup.issue("project-1", "install-fixed", _provider_config())
    policy = _Policy()
    repository = _Repository(policy)
    registry = ConnectorRegistry()
    credentials = _Credentials()
    registry.register(TeamsAdapter(cast(Any, credentials), cast(Any, _Graph())))
    service = ConnectorInstallationService(
        cast(Any, repository),
        cast(Any, policy),
        registry,
        ConnectorSecretPolicy(OpenBaoSecretStore(InMemoryOpenBaoTransport())),
        setup,
    )
    context = TrustedActorContext("actor-1", "request-1", "operation-1")
    created = await service.create(
        context,
        InstallationMutation(
            installationId="ignored-generated-id",
            projectId="project-1",
            connectorType="teams",
            teamsSetupHandle=handle,
        ),
    )
    assert created.installation_id == "install-fixed"
    enabled = await service.enable(context, "project-1", "install-fixed", created.revision)
    assert enabled.revision == 2

    current = policy.installation
    assert current is not None
    binding = TeamsInstallationConfig.model_validate(current.capability_snapshot["providerConfig"])
    assert binding.credential_revision == 1
    command = PullEventsCommand(
        installationId="install-fixed",
        projectId="project-1",
        fixtureReference="fixture://teams/install-fixed",
        max_events=100,
        max_bytes=10 * 1024 * 1024,
        deadline=datetime.now(UTC) + timedelta(seconds=30),
        correlationId="request-1",
        operationId="operation-1",
        capability="inbound-import",
        installationRevision=enabled.revision,
        providerConfig=current.capability_snapshot["providerConfig"],
    )
    result = await registry.resolve("teams").pull_events(command)
    assert result.outcome == "empty"
    assert credentials.scopes[0].installation_revision == 1

    with pytest.raises(ValueError, match="ADAPTER_CONFIGURATION_UNAVAILABLE"):
        await service.update(
            context,
            "project-1",
            "install-fixed",
            InstallationPatch(
                expectedRevision=enabled.revision,
                providerConfig={**_provider_config(), "tenantId": "browser-injected"},
            ),
        )
