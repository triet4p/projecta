"""S11-A08/A09/A15 deterministic GitHub issue and comment mapping tests."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from projecta_api.connectors.contracts import OpaqueCursor, PullEventsCommand
from projecta_api.connectors.github_public_issues import (
    GitHubCursor,
    GitHubCursorCodec,
    GitHubHttpPage,
    GitHubProviderOutputError,
    GitHubPublicIssuesAdapter,
    GitHubPublicIssuesInstallationConfig,
    GitHubTransportError,
    GitHubWatermark,
    is_after_watermark,
    map_github_failure,
    map_github_issue,
    map_github_issue_comment,
)


def _config() -> GitHubPublicIssuesInstallationConfig:
    return GitHubPublicIssuesInstallationConfig(owner="owner", repository="repo")


def _issue(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": 101,
        "number": 7,
        "title": "Synthetic issue",
        "body": "Synthetic bounded body",
        "state": "open",
        "labels": [{"name": "synthetic"}],
        "created_at": "2026-08-13T01:00:00Z",
        "updated_at": "2026-08-13T01:00:00Z",
        "repository_url": "https://api.github.com/repos/owner/repo",
        "user": {"id": 42, "login": "fake-user"},
    }
    payload.update(overrides)
    return payload


def _comment(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": 202,
        "body": "Synthetic comment",
        "created_at": "2026-08-13T01:00:00Z",
        "updated_at": "2026-08-13T01:00:00Z",
        "issue_url": "https://api.github.com/repos/owner/repo/issues/7",
        "user": {"id": 43, "login": "fake-commenter"},
    }
    payload.update(overrides)
    return payload


def test_sanitized_issue_fixture_maps_and_excludes_pull_request() -> None:
    fixture = json.loads(
        (Path(__file__).parents[3] / "evaluation/sprint-11/github-public-issues/issues-page-1.json").read_text()
    )
    config = GitHubPublicIssuesInstallationConfig(owner="example-owner", repository="example-repo")
    mapped = [
        map_github_issue(item, installation_scope="install-fixture", config=config)
        for item in fixture
    ]

    assert mapped[0] is not None
    assert mapped[1] is None


def test_issue_mapping_is_canonical_opaque_and_non_authoritative() -> None:
    first = map_github_issue(_issue(), installation_scope="install-1", config=_config())
    second = map_github_issue(_issue(), installation_scope="install-1", config=_config())

    assert first is not None and second is not None
    assert first.event_id == second.event_id
    assert first.content_bytes == second.content_bytes
    assert first.event_type == "source.created"
    assert first.external_reference.startswith("github://issue/")
    assert first.actor_hint is not None
    assert first.actor_hint.source_system == "github"
    assert first.actor_hint.external_id != "42"


def test_issue_edit_creates_distinct_updated_revision() -> None:
    original = map_github_issue(_issue(), installation_scope="install-1", config=_config())
    edited = map_github_issue(
        _issue(body="edited", updated_at="2026-08-13T02:00:00Z"),
        installation_scope="install-1",
        config=_config(),
    )

    assert original is not None and edited is not None
    assert original.event_id != edited.event_id
    assert edited.event_type == "source.updated"
    assert edited.occurred_at == datetime(2026, 8, 13, 2, tzinfo=UTC)


def test_pull_request_issue_shape_is_excluded() -> None:
    assert map_github_issue(
        _issue(pull_request={"url": "https://api.github.com/repos/owner/repo/pulls/7"}),
        installation_scope="install-1",
        config=_config(),
    ) is None


def test_comment_mapping_requires_bound_issue_parent() -> None:
    mapped = map_github_issue_comment(
        _comment(), installation_scope="install-1", config=_config(), parent_kind="issue"
    )
    assert mapped is not None
    assert mapped.external_reference.startswith("github://issue-comment/")
    assert map_github_issue_comment(
        _comment(), installation_scope="install-1", config=_config(), parent_kind="pull-request"
    ) is None
    assert map_github_issue_comment(
        _comment(), installation_scope="install-1", config=_config(), parent_kind="unknown"
    ) is None


def test_mapping_rejects_malformed_or_cross_repository_output() -> None:
    with pytest.raises(GitHubProviderOutputError):
        map_github_issue(
            _issue(repository_url="https://api.github.com/repos/other/repo"),
            installation_scope="install-1",
            config=_config(),
        )
    with pytest.raises(GitHubProviderOutputError):
        map_github_issue(
            _issue(updated_at="not-a-timestamp"),
            installation_scope="install-1",
            config=_config(),
        )
    with pytest.raises(GitHubProviderOutputError):
        map_github_issue_comment(
            _comment(issue_url="https://api.github.com/repos/other/repo/issues/7"),
            installation_scope="install-1",
            config=_config(),
            parent_kind="issue",
        )


def test_cursor_is_canonical_opaque_and_keeps_independent_stream_watermarks() -> None:
    cursor = GitHubCursor(
        issue=GitHubWatermark(updatedAt="2026-08-13T01:00:00Z", numericId=7),
        comment=GitHubWatermark(updatedAt="2026-08-13T02:00:00Z", numericId=8),
    )

    encoded = GitHubCursorCodec.encode(cursor)
    assert GitHubCursorCodec.decode(encoded) == cursor
    assert "2026-08-13" not in encoded
    assert GitHubCursorCodec.encode(GitHubCursor(issue=cursor.issue)) != encoded


def test_cursor_overlap_discards_only_tuples_at_or_before_committed_watermark() -> None:
    watermark = GitHubWatermark(updatedAt="2026-08-13T01:00:00Z", numericId=7)

    assert not is_after_watermark(datetime(2026, 8, 13, 1, tzinfo=UTC), 6, watermark)
    assert not is_after_watermark(datetime(2026, 8, 13, 1, tzinfo=UTC), 7, watermark)
    assert is_after_watermark(datetime(2026, 8, 13, 1, tzinfo=UTC), 8, watermark)
    assert is_after_watermark(datetime(2026, 8, 13, 2, tzinfo=UTC), 1, watermark)


def test_cursor_rejects_noncanonical_or_malformed_values() -> None:
    with pytest.raises(ValueError):
        GitHubCursorCodec.decode("not a cursor")
    with pytest.raises(ValueError):
        GitHubCursorCodec.decode("e30")


def test_failure_mapping_is_finite_and_rate_metadata_is_bounded() -> None:
    assert map_github_failure(status_code=404).outcome == "invalid-installation"
    assert map_github_failure(status_code=403).code == "ADAPTER_PERMISSION_DENIED"
    rate = map_github_failure(
        status_code=403,
        headers={"X-RateLimit-Remaining": "0", "Retry-After": "60", "X-Secret": "hidden"},
    )
    assert rate.outcome == "rate-limited"
    assert rate.retry_after_seconds == 60
    assert map_github_failure(status_code=429).outcome == "rate-limited"
    assert map_github_failure(status_code=503).outcome == "unavailable"
    assert map_github_failure(
        transport_error=GitHubTransportError("pagination-link-invalid")
    ).code == "ADAPTER_OUTPUT_INVALID"
    assert map_github_failure(
        transport_error=GitHubTransportError("response-byte-limit-exceeded")
    ).outcome == "truncated"


def test_failure_mapping_does_not_accept_unbounded_retry_after() -> None:
    assert map_github_failure(status_code=429, headers={"Retry-After": "999999"}).retry_after_seconds is None
    assert map_github_failure(status_code=429, headers={"Retry-After": "not-a-number"}).retry_after_seconds is None


def test_github_adapter_descriptor_is_finite_and_provider_neutral() -> None:
    descriptor = GitHubPublicIssuesAdapter().descriptor()

    assert descriptor.connector_type == "github-public-issues"
    assert descriptor.capabilities == ("inbound-import",)
    assert descriptor.contract_version == "connector-contract.v1"


@pytest.mark.asyncio
async def test_github_adapter_maps_both_streams_and_returns_opaque_cursor() -> None:
    fixture_root = Path(__file__).parents[3] / "evaluation/sprint-11/github-public-issues"
    issues = fixture_root.joinpath("issues-page-1.json").read_bytes()
    comments = fixture_root.joinpath("comments-page-1.json").read_bytes()

    class FixtureTransport:
        async def fetch_page(self, config, stream, **kwargs):
            return GitHubHttpPage(
                statusCode=200,
                headers={},
                body=issues if stream == "issues" else comments,
            )

    fixture_config = GitHubPublicIssuesInstallationConfig(
        owner="example-owner", repository="example-repo"
    )
    command = PullEventsCommand(
        installationId="install-github",
        projectId="project-a",
        fixtureReference="fixture://github-public-issues/install-github",
        max_events=100,
        max_bytes=10 * 1024 * 1024,
        deadline=datetime.now(UTC),
        correlationId="req-github-fixture",
        operationId="op-github-fixture",
        capability="inbound-import",
        providerConfig=fixture_config.model_dump(mode="json", by_alias=True),
    )
    result = await GitHubPublicIssuesAdapter(FixtureTransport()).pull_events(command)

    assert result.outcome == "succeeded"
    assert len(result.events) == 2
    assert result.next_cursor is not None
    assert "2026-08-13" not in result.next_cursor.value


@pytest.mark.asyncio
async def test_github_adapter_does_not_advance_cursor_on_truncation_or_malformed_output() -> None:
    class FixtureTransport:
        def __init__(self, body: bytes) -> None:
            self.body = body

        async def fetch_page(self, config, stream, **kwargs):
            return GitHubHttpPage(statusCode=200, headers={}, body=self.body)

    fixture_root = Path(__file__).parents[3] / "evaluation/sprint-11/github-public-issues"
    body = fixture_root.joinpath("issues-page-1.json").read_bytes()
    config = GitHubPublicIssuesInstallationConfig(owner="example-owner", repository="example-repo")
    command = PullEventsCommand(
        installationId="install-github",
        projectId="project-a",
        fixtureReference="fixture://github-public-issues/install-github",
        max_events=1,
        max_bytes=10 * 1024 * 1024,
        deadline=datetime.now(UTC),
        correlationId="req-github-bound",
        operationId="op-github-bound",
        capability="inbound-import",
        providerConfig=config.model_dump(mode="json", by_alias=True),
    )
    truncated = await GitHubPublicIssuesAdapter(FixtureTransport(body)).pull_events(command)
    assert truncated.outcome == "truncated"
    assert truncated.next_cursor is None

    malformed = await GitHubPublicIssuesAdapter(FixtureTransport(b"{}" )).pull_events(
        command.model_copy(update={"max_events": 100})
    )
    assert malformed.outcome == "malformed-output"
    assert malformed.failure_code == "ADAPTER_OUTPUT_INVALID"


@pytest.mark.asyncio
async def test_adapter_filters_committed_overlap_before_mapping_and_watermarking() -> None:
    fixture_root = Path(__file__).parents[3] / "evaluation/sprint-11/github-public-issues"
    issues = fixture_root.joinpath("issues-page-1.json").read_bytes()
    comments = fixture_root.joinpath("comments-page-1.json").read_bytes()

    class FixtureTransport:
        async def fetch_page(self, config, stream, **kwargs):
            return GitHubHttpPage(
                statusCode=200,
                headers={},
                body=issues if stream == "issues" else comments,
            )

    config = GitHubPublicIssuesInstallationConfig(owner="example-owner", repository="example-repo")
    cursor = GitHubCursor(
        issue=GitHubWatermark(updatedAt="2026-08-13T01:00:00Z", numericId=1101)
    )
    command = PullEventsCommand(
        installationId="install-github",
        projectId="project-a",
        fixtureReference="fixture://github-public-issues/install-github",
        cursor=OpaqueCursor(value=GitHubCursorCodec.encode(cursor)),
        deadline=datetime.now(UTC),
        correlationId="req-github-overlap",
        operationId="op-github-overlap",
        capability="inbound-import",
        providerConfig=config.model_dump(mode="json", by_alias=True),
    )
    result = await GitHubPublicIssuesAdapter(FixtureTransport()).pull_events(command)

    assert result.outcome == "succeeded"
    assert len(result.events) == 1
    assert result.events[0].event_type == "source.created"
    assert result.next_cursor is not None
    next_cursor = GitHubCursorCodec.decode(result.next_cursor.value)
    assert next_cursor.issue is not None and next_cursor.issue.numeric_id == 1102
    assert next_cursor.comment is not None and next_cursor.comment.numeric_id == 2201


@pytest.mark.asyncio
async def test_adapter_applies_one_raw_byte_budget_across_pages() -> None:
    class PagingTransport:
        async def fetch_page(self, config, stream, *, next_url=None, **kwargs):
            return GitHubHttpPage(
                statusCode=200,
                headers={},
                body=b"[]",
                nextUrl=(
                    "/repos/owner/repo/issues?direction=asc&page=2&per_page=100&sort=updated&state=all"
                    if next_url is None and stream == "issues"
                    else None
                ),
            )

    config = GitHubPublicIssuesInstallationConfig(owner="owner", repository="repo")
    command = PullEventsCommand(
        installationId="install-github",
        projectId="project-a",
        fixtureReference="fixture://github-public-issues/install-github",
        max_bytes=3,
        deadline=datetime.now(UTC),
        correlationId="req-github-budget",
        operationId="op-github-budget",
        capability="inbound-import",
        providerConfig=config.model_dump(mode="json", by_alias=True),
    )
    result = await GitHubPublicIssuesAdapter(PagingTransport()).pull_events(command)

    assert result.outcome == "truncated"
    assert result.source_bytes == 2
    assert result.next_cursor is None


@pytest.mark.asyncio
async def test_adapter_rejects_pagination_cycles() -> None:
    class CyclicTransport:
        async def fetch_page(self, config, stream, *, next_url=None, **kwargs):
            link = "/repos/owner/repo/issues?direction=asc&page=2&per_page=100&sort=updated&state=all"
            return GitHubHttpPage(statusCode=200, headers={}, body=b"[]", nextUrl=link)

    config = GitHubPublicIssuesInstallationConfig(owner="owner", repository="repo")
    command = PullEventsCommand(
        installationId="install-github",
        projectId="project-a",
        fixtureReference="fixture://github-public-issues/install-github",
        deadline=datetime.now(UTC),
        correlationId="req-github-cycle",
        operationId="op-github-cycle",
        capability="inbound-import",
        providerConfig=config.model_dump(mode="json", by_alias=True),
    )
    result = await GitHubPublicIssuesAdapter(CyclicTransport()).pull_events(command)

    assert result.outcome == "malformed-output"
    assert result.failure_code == "ADAPTER_OUTPUT_INVALID"
