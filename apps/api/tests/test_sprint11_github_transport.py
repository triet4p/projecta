"""S11-A07 fixed-origin and bounded GitHub transport tests."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from projecta_api.connectors.github_public_issues import (
    GitHubPublicIssuesHttpTransport,
    GitHubPublicIssuesInstallationConfig,
    GitHubTransportError,
)


def _config() -> GitHubPublicIssuesInstallationConfig:
    return GitHubPublicIssuesInstallationConfig(owner="owner", repository="repo")


def _deadline() -> datetime:
    return datetime.now(UTC) + timedelta(seconds=5)


@pytest.mark.asyncio
async def test_transport_constructs_fixed_issue_request_and_validates_next_link() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={
                "Link": '<https://api.github.com/repos/owner/repo/issues?page=2&state=all&sort=updated&direction=asc&per_page=100>; rel="next"'
            },
            content=b"[]",
        )

    transport = GitHubPublicIssuesHttpTransport(http_transport=httpx.MockTransport(handler))
    try:
        page = await transport.fetch_page(
            _config(), "issues", since=None, page=1, deadline=_deadline()
        )
    finally:
        await transport.aclose()

    assert page.status_code == 200
    assert page.next_url == "/repos/owner/repo/issues?direction=asc&page=2&per_page=100&sort=updated&state=all"
    assert len(requests) == 1
    assert str(requests[0].url) == "https://api.github.com/repos/owner/repo/issues?sort=updated&direction=asc&per_page=100&page=1&state=all"
    assert requests[0].headers["accept"] == "application/vnd.github+json"
    assert requests[0].headers["x-github-api-version"] == "2026-03-10"


@pytest.mark.asyncio
async def test_transport_rejects_malicious_pagination_without_redirect_or_retry() -> None:
    calls = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            headers={"Link": '<https://evil.example/repos/owner/repo/issues?page=2>; rel="next"'},
            content=b"[]",
        )

    transport = GitHubPublicIssuesHttpTransport(http_transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(GitHubTransportError, match="pagination-link-invalid"):
            await transport.fetch_page(
                _config(), "issues", since=None, page=1, deadline=_deadline()
            )
    finally:
        await transport.aclose()

    assert calls == 1


@pytest.mark.asyncio
async def test_transport_rejects_http_redirect_without_following_it() -> None:
    calls = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(302, headers={"Location": "https://evil.example/"})

    transport = GitHubPublicIssuesHttpTransport(http_transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(GitHubTransportError, match="redirect-rejected"):
            await transport.fetch_page(
                _config(), "issues", since=None, page=1, deadline=_deadline()
            )
    finally:
        await transport.aclose()

    assert calls == 1


@pytest.mark.asyncio
async def test_transport_enforces_byte_limit_and_absolute_deadline() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"1234")

    transport = GitHubPublicIssuesHttpTransport(http_transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(GitHubTransportError, match="response-byte-limit-exceeded"):
            await transport.fetch_page(
                _config(), "issue-comments", since=None, page=1, deadline=_deadline(), max_bytes=3
            )
        with pytest.raises(GitHubTransportError, match="deadline-exceeded"):
            await transport.fetch_page(
                _config(),
                "issue-comments",
                since=None,
                page=1,
                deadline=datetime.now(UTC) - timedelta(seconds=1),
            )
    finally:
        await transport.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "next_url",
    [
        "http://api.github.com/repos/owner/repo/issues?page=2&sort=updated&direction=asc&per_page=100&state=all",
        "https://user:password@api.github.com/repos/owner/repo/issues?page=2&sort=updated&direction=asc&per_page=100&state=all",
        "https://api.github.com/repos/other/repo/issues?page=2&sort=updated&direction=asc&per_page=100&state=all",
        "https://api.github.com/repos/owner/repo/pulls?page=2&sort=updated&direction=asc&per_page=100&state=all",
        "https://api.github.com/repos/owner/repo/issues?page=2&sort=updated&direction=asc&per_page=100&state=all&unknown=x",
        "https://api.github.com/repos/owner/repo/issues?page=2&page=3&sort=updated&direction=asc&per_page=100&state=all",
    ],
)
async def test_transport_rejects_ssrf_and_pagination_scope_variants(next_url: str) -> None:
    transport = GitHubPublicIssuesHttpTransport(
        http_transport=httpx.MockTransport(lambda _: httpx.Response(500))
    )
    try:
        with pytest.raises(GitHubTransportError, match="pagination-link-invalid"):
            await transport.fetch_page(
                _config(),
                "issues",
                since=None,
                page=1,
                deadline=_deadline(),
                next_url=next_url,
            )
    finally:
        await transport.aclose()


@pytest.mark.asyncio
async def test_transport_maps_page_budget_to_finite_truncation_signal() -> None:
    transport = GitHubPublicIssuesHttpTransport()
    try:
        with pytest.raises(GitHubTransportError, match="page-budget-exceeded"):
            await transport.fetch_page(
                _config(),
                "issues",
                since=None,
                page=11,
                deadline=_deadline(),
            )
    finally:
        await transport.aclose()
