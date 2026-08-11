"""Secret-reference scope and leak-negative tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import SecretStr

from projecta_api.config import Settings
from projecta_api.connectors.authorization import (
    ConnectorAuthorizationError,
    LocalConnectorPrincipalAdapter,
)
from projecta_api.connectors.secrets import ConnectorSecretError, ConnectorSecretPolicy
from projecta_api.operational.ports import InstallationRecord
from projecta_api.startup import validate_startup


class SecretSpy:
    def __init__(self) -> None:
        self.values = {"secret_abcdefghij": SecretStr("raw-credential")}
        self.resolved: list[str] = []

    def create(self, secret: SecretStr) -> str:
        raise AssertionError("connector policy must not create credentials")

    def resolve(self, reference: str) -> SecretStr:
        self.resolved.append(reference)
        if reference not in self.values:
            raise RuntimeError("not found")
        return self.values[reference]

    def delete(self, reference: str | None) -> None:
        raise AssertionError("connector policy must not delete credentials")


def install(project_id: str = "alpha", reference: str | None = "secret_abcdefghij") -> InstallationRecord:
    now = datetime.now(UTC)
    return InstallationRecord(
        installation_id="install-1",
        project_id=project_id,
        connector_type="json-mock",
        capability_snapshot={"capabilities": ["inbound-import"]},
        secret_reference=reference,
        enabled=True,
        revision=1,
        created_at=now,
        updated_at=now,
    )


def test_only_opaque_secret_references_are_accepted() -> None:
    policy = ConnectorSecretPolicy(SecretSpy())
    assert policy.validate_reference("secret_abcdefghij") == "secret_abcdefghij"
    with pytest.raises(ConnectorSecretError, match="SECRET_REFERENCE_INVALID"):
        policy.validate_reference("raw-credential")
    with pytest.raises(ConnectorSecretError, match="SECRET_REFERENCE_INVALID"):
        policy.validate_reference("../secret_abcdefghij")


def test_resolution_is_bound_to_the_authorized_project_installation() -> None:
    store = SecretSpy()
    policy = ConnectorSecretPolicy(store)
    secret = policy.resolve_for_installation("alpha", install())
    assert secret.get_secret_value() == "raw-credential"
    assert store.resolved == ["secret_abcdefghij"]
    with pytest.raises(ConnectorSecretError, match="SECRET_SCOPE_FORBIDDEN") as error:
        policy.resolve_for_installation("beta", install())
    assert "beta" not in str(error.value)
    with pytest.raises(ConnectorSecretError, match="SECRET_SCOPE_FORBIDDEN"):
        policy.resolve_for_installation("alpha", install("beta"))


def test_missing_or_unavailable_reference_is_safe() -> None:
    policy = ConnectorSecretPolicy(SecretSpy())
    with pytest.raises(ConnectorSecretError, match="SECRET_SCOPE_FORBIDDEN"):
        policy.resolve_for_installation("alpha", install(reference=None))
    with pytest.raises(ConnectorSecretError, match="SECRET_UNAVAILABLE") as error:
        policy.resolve_for_installation("alpha", install(reference="secret_klmnopqrst"))
    assert "raw-credential" not in str(error.value)


def test_local_connector_adapter_rejects_production_startup() -> None:
    with pytest.raises(ConnectorAuthorizationError, match="AUTH_ADAPTER_DISABLED"):
        LocalConnectorPrincipalAdapter(
            Settings(
                runtime_mode="production",
                trusted_context_secret="production-context",
                experience_actor_id="actor",
                experience_project_catalog="alpha",
            )
        )
    problems = validate_startup(
        Settings(
            runtime_mode="production",
            trusted_context_secret="production-context",
            connector_local_admin_enabled=True,
        )
    )
    assert any(problem.code == "CONNECTOR_LOCAL_AUTH_DISABLED_IN_PRODUCTION" for problem in problems)
