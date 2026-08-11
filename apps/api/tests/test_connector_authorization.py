"""Negative and positive policy tests for the connector principal boundary."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from projecta_api.config import Settings
from projecta_api.connectors.authorization import (
    ConnectorAuthorizationError,
    ConnectorAuthorizationRequest,
    ConnectorPolicy,
    DeterministicTestPrincipalAdapter,
    LocalConnectorPrincipalAdapter,
    public_authorization_problem,
)
from projecta_api.context import TrustedActorContext
from projecta_api.operational.ports import InstallationRecord, SyncRunRecord

NOW = datetime.now(UTC)


def installation(
    project_id: str = "alpha", *, enabled: bool = True, revision: int = 2
) -> InstallationRecord:
    return InstallationRecord(
        installation_id="install-alpha",
        project_id=project_id,
        connector_type="json-mock",
        capability_snapshot={"capabilities": ["inbound-import"]},
        secret_reference=None,
        enabled=enabled,
        revision=revision,
        created_at=NOW,
        updated_at=NOW,
    )


class InstallationSpy:
    def __init__(self, value: InstallationRecord | None) -> None:
        self.value = value
        self.calls = 0

    def get_installation(self, project_id: str, installation_id: str) -> InstallationRecord | None:
        self.calls += 1
        if self.value is not None and self.value.project_id == project_id:
            return self.value
        return None


class RunSpy:
    def __init__(self, value: SyncRunRecord | None) -> None:
        self.value = value

    def get_run(self, project_id: str, installation_id: str, run_id: str) -> SyncRunRecord | None:
        return self.value


def context(actor: str = "actor-1") -> TrustedActorContext:
    return TrustedActorContext(actor, "request-1", "operation-1")


@pytest.mark.asyncio
async def test_principal_is_server_owned_and_carries_correlation() -> None:
    adapter = DeterministicTestPrincipalAdapter(
        actor_id="actor-1", allowed_projects=("alpha", "beta"), admin=True
    )
    principal = await adapter.resolve(
        ConnectorAuthorizationRequest("catalog.read", context())
    )
    assert principal.actor_id == "actor-1"
    assert principal.allowed_projects == ("alpha", "beta")
    assert principal.auth_source == "test"
    assert principal.request_id == "request-1"
    assert principal.operation_id == "operation-1"

    with pytest.raises(ConnectorAuthorizationError) as error:
        await adapter.resolve(ConnectorAuthorizationRequest("catalog.read", context("forged")))
    assert error.value.code == "AUTH_PRINCIPAL_REQUIRED"
    assert "forged" not in str(error.value)


def test_local_experience_adapter_is_disabled_in_production() -> None:
    with pytest.raises(ConnectorAuthorizationError, match="AUTH_ADAPTER_DISABLED"):
        LocalConnectorPrincipalAdapter(Settings(runtime_mode="production"))


@pytest.mark.asyncio
async def test_catalog_and_reader_operations_are_independent_from_admin() -> None:
    lookup = InstallationSpy(installation())
    reader = DeterministicTestPrincipalAdapter(
        actor_id="actor-1", allowed_projects=("alpha",), admin=False
    )
    policy = ConnectorPolicy(reader, lookup)
    catalog = await policy.authorize(ConnectorAuthorizationRequest("catalog.read", context()))
    assert catalog.project_id is None
    read = await policy.authorize(
        ConnectorAuthorizationRequest(
            "installation.read", context(), project_id="alpha", installation_id="install-alpha"
        )
    )
    assert read.installation is not None
    with pytest.raises(ConnectorAuthorizationError) as error:
        await policy.authorize(
            ConnectorAuthorizationRequest(
                "installation.create", context(), project_id="alpha", connector_type="json-mock"
            )
        )
    assert error.value.code == "PROJECT_FORBIDDEN"


@pytest.mark.asyncio
async def test_cross_project_is_rejected_before_installation_lookup() -> None:
    lookup = InstallationSpy(installation())
    policy = ConnectorPolicy(
        DeterministicTestPrincipalAdapter(actor_id="actor-1", allowed_projects=("alpha",)), lookup
    )
    with pytest.raises(ConnectorAuthorizationError) as error:
        await policy.authorize(
            ConnectorAuthorizationRequest(
                "installation.read", context(), project_id="beta", installation_id="install-alpha"
            )
        )
    assert error.value.code == "PROJECT_FORBIDDEN"
    assert lookup.calls == 0
    assert "beta" not in str(error.value)
    assert public_authorization_problem(error.value, "request-safe") == {
        "code": "PROJECT_FORBIDDEN",
        "detail": "The project is not available to this actor.",
        "requestId": "request-safe",
    }


@pytest.mark.asyncio
async def test_stale_revision_disabled_installation_and_capability_fail_closed() -> None:
    lookup = InstallationSpy(installation(enabled=False))
    policy = ConnectorPolicy(
        DeterministicTestPrincipalAdapter(actor_id="actor-1", allowed_projects=("alpha",)), lookup
    )
    with pytest.raises(ConnectorAuthorizationError) as stale:
        await policy.authorize(
            ConnectorAuthorizationRequest(
                "installation.enable",
                context(),
                project_id="alpha",
                installation_id="install-alpha",
                expected_installation_revision=1,
            )
        )
    assert stale.value.code == "PROJECT_SELECTION_STALE"

    with pytest.raises(ConnectorAuthorizationError) as disabled:
        await policy.authorize(
            ConnectorAuthorizationRequest(
                "sync.run",
                context(),
                project_id="alpha",
                installation_id="install-alpha",
                expected_installation_revision=2,
                idempotency_key="run-1",
            )
        )
    assert disabled.value.code == "INVALID_LIFECYCLE_STATE"

    lookup.value = installation(enabled=True)
    assert lookup.value is not None
    lookup.value = replace(lookup.value, capability_snapshot={"capabilities": []})
    with pytest.raises(ConnectorAuthorizationError) as unsupported:
        await policy.authorize(
            ConnectorAuthorizationRequest(
                "sync.run",
                context(),
                project_id="alpha",
                installation_id="install-alpha",
                expected_installation_revision=2,
                idempotency_key="run-2",
            )
        )
    assert unsupported.value.code == "INVALID_REQUEST"


@pytest.mark.asyncio
async def test_retry_requires_failed_run_revision_and_new_idempotency_key() -> None:
    lookup = InstallationSpy(installation())
    run = SyncRunRecord(
        run_id="run-1",
        installation_id="install-alpha",
        project_id="alpha",
        status="failed",
        started_at=NOW,
        terminal_at=NOW,
        terminal_outcome="failed",
        revision=4,
        retry_of_run_id=None,
        failure_code="EVIDENCE_UNAVAILABLE",
        failure_detail="safe",
    )
    policy = ConnectorPolicy(
        DeterministicTestPrincipalAdapter(actor_id="actor-1", allowed_projects=("alpha",)),
        lookup,
        RunSpy(run),
    )
    allowed = await policy.authorize(
        ConnectorAuthorizationRequest(
            "sync.retry",
            context(),
            project_id="alpha",
            installation_id="install-alpha",
            expected_installation_revision=2,
            run_id="run-1",
            expected_run_revision=4,
            idempotency_key="retry-1",
        )
    )
    assert allowed.run is run
    with pytest.raises(ConnectorAuthorizationError, match="PROJECT_SELECTION_STALE"):
        await policy.authorize(
            ConnectorAuthorizationRequest(
                "sync.retry",
                context(),
                project_id="alpha",
                installation_id="install-alpha",
                expected_installation_revision=2,
                run_id="run-1",
                expected_run_revision=3,
                idempotency_key="retry-2",
            )
        )
    with pytest.raises(ConnectorAuthorizationError, match="INVALID_REQUEST"):
        await policy.authorize(
            ConnectorAuthorizationRequest(
                "sync.run",
                context(),
                project_id="alpha",
                installation_id="install-alpha",
                expected_installation_revision=2,
            )
        )
