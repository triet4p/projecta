from datetime import UTC, datetime

from projecta_api.connectors.public_api import _catalog_item, _snapshot_response
from projecta_api.connectors.registry import ConnectorDescriptor
from projecta_api.operational.audit import InMemorySecurityAuditSink, emit_safe
from projecta_api.operational.ports import InstallationRecord


def test_teams_public_projection_is_finite_and_provider_neutral() -> None:
    item = _catalog_item(
        ConnectorDescriptor(
            connectorType="teams",
            displayName="Microsoft Teams read-only channel",
            capabilities=("inbound-import",),
        )
    )
    body = item.model_dump(by_alias=True)
    assert body["connectorType"] == "teams"
    assert body["setupMode"] == "operator-setup"
    assert "tenant" not in str(body).lower() or "tenant/team/channel" in body["consentGuidance"]
    assert "secretReference" not in str(body)


def test_teams_installation_hides_fixture_and_secret_reference() -> None:
    record = InstallationRecord(
        "install-internal", "project-internal", "teams",
        {"capabilities": ["inbound-import"], "fixtureReference": "fixture://teams/install-internal"},
        "secret_internal_only", False, 3,
        datetime.now(UTC), datetime.now(UTC),
    )
    body = _snapshot_response("request-safe", record).model_dump(by_alias=True)
    serialized = str(body)
    assert body["setupStatus"] == "ready"
    assert body["fixtureConfigured"] is False
    assert "install-internal" not in serialized
    assert "secret_internal_only" not in serialized
    assert "fixtureReference" not in serialized


def test_security_audit_hashes_scopes_and_uses_safe_labels() -> None:
    sink = InMemorySecurityAuditSink()
    emit_safe(
        sink,
        category="secret",
        action="secret.resolve",
        outcome="succeeded",
        correlation_id="request-1",
        project_id="project-sensitive",
        actor_id="user-sensitive",
        revision=4,
    )
    event = sink.events[0]
    assert event.project_scope and "project-sensitive" not in event.project_scope
    assert event.actor_scope and "user-sensitive" not in event.actor_scope
    assert event.action == "secret.resolve"
    assert event.revision == 4
