"""Public connector API contract tests for F45/F47/F50 boundaries."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from projecta_api.config import Settings
from projecta_api.connectors.authorization import (
    ConnectorAuthorizationError,
    ConnectorAuthorizationRequest,
    ConnectorPolicy,
    DeterministicTestPrincipalAdapter,
)
from projecta_api.connectors.contracts import InstallationSnapshot
from projecta_api.connectors.json_mock import JsonMockAdapter, JsonMockFixture
from projecta_api.connectors.orchestration import SyncResult
from projecta_api.connectors.public_api import ConnectorRuntime, connector_handle
from projecta_api.connectors.registry import ConnectorRegistry
from projecta_api.context import TrustedActorContext
from projecta_api.main import create_app
from projecta_api.operational.ports import InstallationRecord, SyncRunRecord
from projecta_api.project_workspace import opaque_project_handle

NOW = datetime(2026, 8, 10, tzinfo=UTC)


class Repository:
    def __init__(self) -> None:
        self.installation = InstallationRecord(
            "install-a", "project-a", "json-mock",
            {"capabilities": ["inbound-import"], "fixtureReference": "fixture://project-a"},
            None, True, 1, NOW, NOW,
        )
        self.run = SyncRunRecord(
            "run-a", "install-a", "project-a", "succeeded", NOW, NOW, "succeeded", 2, None, None, None
        )

    def get_installation(self, project_id: str, installation_id: str):
        return self.installation if (project_id, installation_id) == ("project-a", "install-a") else None

    def list_installations(self, project_id: str, *, limit: int = 50, offset: int = 0):
        return [self.installation][offset : offset + limit] if project_id == "project-a" else []

    def list_runs(self, project_id: str, installation_id: str, *, limit: int = 50):
        return [self.run][:limit] if (project_id, installation_id) == ("project-a", "install-a") else []

    def get_run(self, project_id: str, installation_id: str, run_id: str):
        return self.run if (project_id, installation_id, run_id) == ("project-a", "install-a", "run-a") else None


class InstallationService:
    async def create(self, context, request):
        return InstallationSnapshot(
            installationId="install-a", projectId=context.project_id, connectorType="json-mock",
            capabilities=("inbound-import",), enabled=False, revision=1,
            fixtureReference=request.fixture_reference,
        )

    async def update(self, context, project_id, installation_id, patch):
        return InstallationSnapshot(
            installationId=installation_id, projectId=project_id, connectorType="json-mock",
            capabilities=("inbound-import",), enabled=True, revision=2,
            fixtureReference="fixture://project-a",
        )

    async def enable_or_disable(self, context, project_id, installation_id, expected_revision, enabled):
        return InstallationSnapshot(
            installationId=installation_id, projectId=project_id, connectorType="json-mock",
            capabilities=("inbound-import",), enabled=enabled, revision=expected_revision + 1,
            fixtureReference="fixture://project-a",
        )


class Orchestrator:
    async def run(self, context, command, source_committer=None):
        return SyncResult(runId="run-a", outcome="succeeded", eventCount=1, replayCount=0)

    async def retry(self, context, command, source_committer=None):
        return SyncResult(runId="run-a", outcome="replayed", eventCount=0, replayCount=1)


class SemanticClient:
    async def capture(self, context, key, request):
        raise AssertionError("public projection test must not bypass the orchestrator")


def _runtime(*, admin: bool = True) -> ConnectorRuntime:
    fixture = JsonMockFixture.model_validate(
        {
            "fixtureVersion": "json-mock.v1",
            "connectorType": "json-mock",
            "resources": [
                {
                    "externalReference": "fixture://project-a/message-001",
                    "occurredAt": NOW.isoformat(),
                    "eventType": "source.created",
                    "contentType": "application/json",
                    "content": {"title": "Import", "items": [{"type": "task", "text": "Review"}]},
                }
            ],
        }
    )
    registry = ConnectorRegistry()
    registry.register(JsonMockAdapter(fixture))
    repository = Repository()
    policy = ConnectorPolicy(
        DeterministicTestPrincipalAdapter(
            actor_id="actor-a", allowed_projects=("project-a",), admin=admin
        ),
        repository,
        repository,
    )
    return ConnectorRuntime(
        repository,
        registry,
        InstallationService(),
        Orchestrator(),
        policy,
        object(),
        SemanticClient(),
    )


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        runtime_mode="headless",
        trusted_context_secret="test-secret",
        PROJECTA_LLM_TYPE="openai-response",
        PROJECTA_LLM_BASE_URL="https://api.deepseek.com",
        PROJECTA_LLM_API_KEY="test-key",
        PROJECTA_LLM_MODEL="test-model",
    )


def _headers() -> dict[str, str]:
    return {
        "X-Projecta-Project-Id": "project-a",
        "X-Projecta-Actor-Id": "actor-a",
        "X-Projecta-Context-Secret": "test-secret",
        "X-Projecta-Selection-Handle": opaque_project_handle("project-a"),
        "X-Request-Id": "req-public-01",
    }


@pytest.mark.asyncio
async def test_catalog_and_installation_projection_are_finite_and_opaque() -> None:
    app = create_app(_settings(), SemanticClient(), connector_runtime=_runtime())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        catalog = await client.get("/v1/connectors/catalog", headers=_headers())
        installations = await client.get(
            f"/v1/projects/{opaque_project_handle('project-a')}/connectors/installations", headers=_headers()
        )

    assert catalog.status_code == 200
    assert catalog.json()["items"][0]["connectorType"] == "json-mock"
    assert installations.status_code == 200
    body = installations.json()["items"][0]
    assert body["handle"] == connector_handle("project-a", "install-a")
    assert "install-a" not in installations.text
    assert "project-a" not in installations.text
    assert "fixtureReference" not in installations.text


@pytest.mark.asyncio
async def test_run_projection_uses_selected_project_and_truthful_terminal_state() -> None:
    app = create_app(_settings(), SemanticClient(), connector_runtime=_runtime())
    handle = connector_handle("project-a", "install-a")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/v1/projects/{opaque_project_handle('project-a')}/connectors/installations/{handle}/runs",
            headers=_headers() | {"Idempotency-Key": "public-run-key-001"},
            json={"expectedInstallationRevision": 1},
        )

    assert response.status_code == 202
    assert response.json()["state"] == "succeeded"
    assert response.json()["eventCount"] == 1
    assert "run-a" not in response.text


@pytest.mark.asyncio
async def test_wrong_project_selection_does_not_leak_installation_existence() -> None:
    app = create_app(_settings(), SemanticClient(), connector_runtime=_runtime())
    handle = connector_handle("project-a", "install-a")
    headers = _headers() | {"X-Projecta-Selection-Handle": "project-b-handle"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/v1/projects/project-b-handle/connectors/installations/{handle}", headers=headers
        )

    assert response.status_code == 404
    assert "install-a" not in response.text
    assert "project-a" not in response.text


@pytest.mark.asyncio
async def test_connector_reader_cannot_install_github_public_issues() -> None:
    repository = Repository()
    policy = ConnectorPolicy(
        DeterministicTestPrincipalAdapter(
            actor_id="actor-a", allowed_projects=("project-a",), admin=False
        ),
        repository,
        repository,
    )

    with pytest.raises(ConnectorAuthorizationError, match="PROJECT_FORBIDDEN"):
        await policy.authorize(
            ConnectorAuthorizationRequest(
                action="installation.create",
                actor_context=TrustedActorContext("actor-a", "req-auth", "op-auth"),
                project_id="project-a",
                connector_type="github-public-issues",
            )
        )


class LifecycleRepository:
    """Mutable installation state so enable/disable transitions stay observable."""

    def __init__(self) -> None:
        self.record = InstallationRecord(
            "install-a",
            "project-a",
            "json-mock",
            {"capabilities": ["inbound-import"], "fixtureReference": "fixture://project-a"},
            None,
            False,
            1,
            NOW,
            NOW,
        )

    def get_installation(self, project_id: str, installation_id: str):
        return (
            self.record
            if (project_id, installation_id) == ("project-a", "install-a")
            else None
        )

    def list_installations(self, project_id: str, *, limit: int = 50, offset: int = 0):
        return [self.record][offset : offset + limit] if project_id == "project-a" else []

    def list_runs(self, project_id: str, installation_id: str, *, limit: int = 50):
        return []

    def get_run(self, project_id: str, installation_id: str, run_id: str):
        return None


class LifecycleInstallationService:
    """Apply enable/disable to the mutable record like the real service does."""

    def __init__(self, repository: LifecycleRepository) -> None:
        self._repository = repository

    async def create(self, context, request):
        raise AssertionError("lifecycle test only toggles an existing installation")

    async def update(self, context, project_id, installation_id, patch):
        raise AssertionError("lifecycle test only toggles an existing installation")

    async def enable_or_disable(
        self, context, project_id, installation_id, expected_revision, enabled
    ):
        current = self._repository.get_installation(project_id, installation_id)
        assert current is not None
        updated = replace(current, enabled=enabled, revision=expected_revision + 1)
        self._repository.record = updated
        return InstallationSnapshot(
            installationId=installation_id,
            projectId=project_id,
            connectorType=updated.connector_type,
            capabilities=("inbound-import",),
            enabled=enabled,
            revision=updated.revision,
            fixtureReference="fixture://project-a",
        )


def _lifecycle_runtime() -> ConnectorRuntime:
    repository = LifecycleRepository()
    registry = ConnectorRegistry()
    policy = ConnectorPolicy(
        DeterministicTestPrincipalAdapter(
            actor_id="actor-a", allowed_projects=("project-a",), admin=True
        ),
        repository,
        repository,
    )
    return ConnectorRuntime(
        repository,
        registry,
        LifecycleInstallationService(repository),
        object(),  # type: ignore[arg-type]
        policy,
        object(),  # type: ignore[arg-type]
        SemanticClient(),
    )


@pytest.mark.asyncio
async def test_enable_and_disable_routes_transition_the_composed_installation() -> None:
    app = create_app(_settings(), SemanticClient(), connector_runtime=_lifecycle_runtime())
    handle = connector_handle("project-a", "install-a")
    base = (
        f"/v1/projects/{opaque_project_handle('project-a')}"
        f"/connectors/installations/{handle}"
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        enabled = await client.post(
            f"{base}/enable",
            headers=_headers(),
            json={"expectedInstallationRevision": 1},
        )
        disabled = await client.post(
            f"{base}/disable",
            headers=_headers(),
            json={"expectedInstallationRevision": 2},
        )

    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True
    assert enabled.json()["revision"] == 2
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False
    assert disabled.json()["revision"] == 3
