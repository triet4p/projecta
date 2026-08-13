"""S11-A06 typed GitHub installation and setup-handle tests."""

import pytest

from projecta_api.connectors.github_public_issues import (
    GITHUB_API_ORIGIN,
    GitHubPublicIssuesInstallationConfig,
)
from projecta_api.connectors.github_public_issues_setup import (
    GitHubPublicIssuesSetupError,
    InMemoryGitHubPublicIssuesSetupRegistry,
)
from projecta_api.connectors.installation_service import (
    ConnectorInstallationService,
    InstallationMutation,
)
from projecta_api.connectors.registry import (
    AdapterContext,
    ConnectorRegistry,
    InstallationValidation,
)
from projecta_api.context import TrustedActorContext
from projecta_api.operational.ports import InstallationRecord


def test_github_config_is_fixed_origin_finite_and_safely_projectable() -> None:
    config = GitHubPublicIssuesInstallationConfig(owner="SyntheticOwner", repository="fake-repo")

    assert config.api_origin == GITHUB_API_ORIGIN
    assert config.comparison_key == ("syntheticowner", "fake-repo")
    assert config.limits.max_requests == 20
    assert config.limits.max_events == 100
    projection = config.safe_projection()
    assert projection["repositoryLabel"] == "SyntheticOwner/fake-repo"
    assert projection["credentialRequired"] is False
    assert "providerConfig" not in projection


@pytest.mark.parametrize(
    "field,value",
    [
        ("owner", "https://api.github.com"),
        ("owner", "owner/repository"),
        ("owner", "owner%2Frepository"),
        ("repository", ".."),
        ("repository", "repo?state=all"),
        ("repository", "repo\\path"),
        ("repository", "repo with spaces"),
    ],
)
def test_github_config_rejects_urls_path_syntax_and_query_input(
    field: str, value: str
) -> None:
    values = {"owner": "owner", "repository": "repo"}
    values[field] = value

    with pytest.raises(ValueError):
        GitHubPublicIssuesInstallationConfig(**values)


def test_github_setup_handle_is_project_bound_single_use_and_typed() -> None:
    registry = InMemoryGitHubPublicIssuesSetupRegistry()
    config = GitHubPublicIssuesInstallationConfig(owner="owner", repository="repo")
    handle = registry.issue("project-1", "actor-1", "install-1", config)

    consumed = registry.consume(handle, "project-1", "actor-1", 1)
    assert consumed.config == config

    with pytest.raises(GitHubPublicIssuesSetupError):
        registry.consume(handle, "project-1", "actor-1", 1)


def test_github_setup_handle_cannot_cross_project() -> None:
    registry = InMemoryGitHubPublicIssuesSetupRegistry()
    config = GitHubPublicIssuesInstallationConfig(owner="owner", repository="repo")
    handle = registry.issue("project-1", "actor-1", "install-1", config)

    with pytest.raises(GitHubPublicIssuesSetupError):
        registry.consume(handle, "project-2", "actor-1", 1)


def test_github_setup_handle_cannot_transfer_between_actors_or_revisions() -> None:
    registry = InMemoryGitHubPublicIssuesSetupRegistry()
    config = GitHubPublicIssuesInstallationConfig(owner="owner", repository="repo")
    handle = registry.issue("project-1", "actor-1", "install-1", config, expected_revision=2)

    with pytest.raises(GitHubPublicIssuesSetupError):
        registry.consume(handle, "project-1", "actor-2", 2)
    with pytest.raises(GitHubPublicIssuesSetupError):
        registry.consume(handle, "project-1", "actor-1", 1)
    assert registry.consume(handle, "project-1", "actor-1", 2).expected_revision == 2


class _Policy:
    async def authorize(self, _: object) -> object:
        return type("Authorized", (), {"installation": None})()


class _Repository:
    def __init__(self) -> None:
        self.record: InstallationRecord | None = None

    def upsert_installation(self, **values: object) -> InstallationRecord:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        self.record = InstallationRecord(
            str(values["installation_id"]),
            str(values["project_id"]),
            str(values["connector_type"]),
            values["capability_snapshot"],  # type: ignore[arg-type]
            values["secret_reference"],  # type: ignore[arg-type]
            bool(values["enabled"]),
            1,
            now,
            now,
        )
        return self.record


class _GitHubAdapter:
    def descriptor(self) -> object:
        from projecta_api.connectors.contracts import ConnectorDescriptor

        return ConnectorDescriptor(
            connectorType="github-public-issues",
            displayName="GitHub Public Issues",
            capabilities=("inbound-import",),
        )

    async def validate_installation(
        self, _: object, __: AdapterContext
    ) -> InstallationValidation:
        return InstallationValidation(outcome="valid")


@pytest.mark.asyncio
async def test_installation_service_consumes_typed_github_setup_handle() -> None:
    setup = InMemoryGitHubPublicIssuesSetupRegistry()
    config = GitHubPublicIssuesInstallationConfig(owner="owner", repository="repo")
    handle = setup.issue("project-1", "actor-1", "install-github", config)
    repository = _Repository()
    registry = ConnectorRegistry()
    registry.register(_GitHubAdapter())  # type: ignore[arg-type]
    service = ConnectorInstallationService(
        repository,  # type: ignore[arg-type]
        _Policy(),  # type: ignore[arg-type]
        registry,
        github_setup_resolver=setup,
    )

    snapshot = await service.create(
        TrustedActorContext("actor-1", "request-1", "operation-1"),
        InstallationMutation(
            installationId="ignored-generated-id",
            projectId="project-1",
            connectorType="github-public-issues",
            githubSetupHandle=handle,
        ),
    )

    assert snapshot.installation_id == "install-github"
    assert repository.record is not None
    stored = repository.record.capability_snapshot["providerConfig"]
    assert stored["owner"] == "owner"  # type: ignore[index]
    assert stored["repository"] == "repo"  # type: ignore[index]
    assert "secretReference" not in stored  # type: ignore[operator]
