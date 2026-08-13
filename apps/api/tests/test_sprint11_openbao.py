"""Deterministic tests for the Sprint 11 OpenBao boundary."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr

from projecta_api.configuration.ports import SecretScope
from projecta_api.connectors.secrets import ConnectorSecretError, ConnectorSecretPolicy
from projecta_api.operational.ports import InstallationRecord
from projecta_api.secrets.approle import FileAppRoleTokenProvider
from projecta_api.secrets.openbao import (
    InMemoryOpenBaoTransport,
    OpenBaoSecretError,
    OpenBaoSecretStore,
)


def _scope(revision: int = 1) -> SecretScope:
    return SecretScope("project-1", "installation-1", "teams", "tenant-1", revision)


def _installation(*, revision: int = 1, tenant: str = "tenant-1") -> InstallationRecord:
    now = datetime.now(UTC)
    return InstallationRecord(
        installation_id="installation-1",
        project_id="project-1",
        connector_type="teams",
        capability_snapshot={"providerTenant": tenant},
        secret_reference="secret_1234567890",
        enabled=True,
        revision=revision,
        created_at=now,
        updated_at=now,
    )


def test_scoped_versions_are_opaque_immutable_and_rotation_safe() -> None:
    store = OpenBaoSecretStore(InMemoryOpenBaoTransport(), cache_ttl_seconds=30)
    first = store.create_scoped(_scope(), SecretStr("runtime-value-one"))

    resolved_first = store.resolve_scoped(_scope(), first.reference)
    rotated = store.rotate_scoped(_scope(), first.reference, SecretStr("runtime-value-two"))
    resolved_current = store.resolve_scoped(_scope(), first.reference)

    assert first.reference.startswith("secret_")
    assert first.secret.get_secret_value() == "runtime-value-one"
    assert resolved_first.version == 1
    assert resolved_first.secret.get_secret_value() == "runtime-value-one"
    assert rotated.version == 2
    assert resolved_current.version == 2
    assert resolved_current.secret.get_secret_value() == "runtime-value-two"
    assert first.scope == resolved_current.scope


def test_scope_isolation_revocation_and_safe_statuses() -> None:
    transport = InMemoryOpenBaoTransport()
    store = OpenBaoSecretStore(transport)
    created = store.create_scoped(_scope(), SecretStr("runtime-value"))

    with pytest.raises(OpenBaoSecretError) as cross_scope:
        store.resolve_scoped(_scope(2), created.reference)
    assert cross_scope.value.code == "MISSING"
    assert str(cross_scope.value) == "MISSING"

    store.revoke_scoped(_scope(), created.reference)
    with pytest.raises(OpenBaoSecretError) as revoked:
        store.resolve_scoped(_scope(), created.reference)
    assert revoked.value.code == "REVOKED"
    assert store.readiness() == "ready"

    transport.seal()
    assert store.readiness() == "sealed"
    with pytest.raises(OpenBaoSecretError, match="SEALED"):
        store.resolve_scoped(_scope(), created.reference)
    transport.unauthorized()
    assert store.readiness() == "unauthorized"
    transport.unavailable()
    assert store.readiness() == "unavailable"


def test_unscoped_legacy_methods_fail_closed() -> None:
    store = OpenBaoSecretStore(InMemoryOpenBaoTransport())
    with pytest.raises(OpenBaoSecretError, match="SCOPE_REQUIRED"):
        store.create(SecretStr("runtime-value"))
    with pytest.raises(OpenBaoSecretError, match="SCOPE_REQUIRED"):
        store.resolve("secret_1234567890")


def test_connector_policy_maps_scoped_failures_without_store_details() -> None:
    transport = InMemoryOpenBaoTransport()
    store = OpenBaoSecretStore(transport, cache_ttl_seconds=0)
    snapshot = store.create_scoped(_scope(), SecretStr("runtime-value"))
    record = replace(_installation(), secret_reference=snapshot.reference)
    policy = ConnectorSecretPolicy(store)

    assert policy.resolve_for_installation("project-1", record).get_secret_value() == "runtime-value"
    transport.seal()
    with pytest.raises(ConnectorSecretError) as error:
        policy.resolve_for_installation("project-1", record)
    assert error.value.code == "SECRET_SEALED"
    assert str(error.value) == "SECRET_SEALED"


class _FakeAppRoleLogin:
    def __init__(self) -> None:
        self.logins: list[tuple[str, str]] = []
        self.renewals: list[str] = []

    def login(self, role_id: str, secret_id: str) -> tuple[str, int]:
        self.logins.append((role_id, secret_id))
        return "workload-token", 120

    def renew(self, token: str) -> tuple[str, int]:
        self.renewals.append(token)
        return "renewed-workload-token", 120


def test_approle_material_is_bootstrap_only_and_tokens_are_bounded(tmp_path) -> None:
    role_file = tmp_path / "role-id"
    secret_file = tmp_path / "secret-id"
    role_file.write_text("role-id", encoding="utf-8")
    secret_file.write_text("single-use-secret-id", encoding="utf-8")
    login = _FakeAppRoleLogin()
    provider = FileAppRoleTokenProvider(role_file, secret_file, login)

    assert provider() == "workload-token"
    assert provider() == "workload-token"
    assert len(login.logins) == 1
    assert login.logins[0] == ("role-id", "single-use-secret-id")

    provider._token = provider._token.__class__(  # type: ignore[union-attr]
        "workload-token",
        datetime.now(UTC) - timedelta(seconds=1),
        datetime.now(UTC) + timedelta(seconds=10),
        datetime.now(UTC) + timedelta(minutes=5),
    )
    assert provider() == "renewed-workload-token"
    assert login.renewals == ["workload-token"]
    provider.invalidate()
    with pytest.raises(OpenBaoSecretError, match="UNAUTHORIZED"):
        provider()
    replacement = FileAppRoleTokenProvider(role_file, secret_file, login)
    assert replacement() == "workload-token"
    assert len(login.logins) == 2
