"""Typed configuration boundary for the credential-free GitHub connector.

The HTTP adapter is added in S11-A07. This module intentionally contains only
the installation contract and safe projection primitives for S11-A06.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from projecta_api.connectors.contracts import (
    ActorHint,
    ConnectorLimits,
    ErrorCode,
    EventType,
    InstallationConfig,
    OpaqueCursor,
    PullEventsCommand,
    PullEventsResult,
    RawEventCandidate,
    SyncOutcome,
    sha256_digest,
)
from projecta_api.connectors.registry import (
    AdapterContext,
    ConnectorDescriptor,
    IdentityHintResult,
    InstallationValidation,
    ResourceResult,
)

GitHubCapability = Literal["read:issues", "read:issue-comments"]
GITHUB_API_ORIGIN = "https://api.github.com"
_OWNER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}$")
_REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


class GitHubPublicIssuesLimits(ConnectorLimits):
    """Connector-specific limits that cannot widen shared server policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    max_requests: int = Field(default=20, ge=1, le=20, alias="maxRequests")
    max_pages_per_stream: int = Field(default=10, ge=1, le=10, alias="maxPagesPerStream")
    first_run_lookback_days: int = Field(default=30, ge=1, le=30, alias="firstRunLookbackDays")


class GitHubPublicIssuesInstallationConfig(BaseModel):
    """Server-owned, typed binding to one exact public GitHub repository."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)
    owner: str = Field(min_length=1, max_length=39)
    repository: str = Field(min_length=1, max_length=100)
    contract_version: Literal["connector-contract.v1"] = Field(
        default="connector-contract.v1", alias="contractVersion"
    )
    capabilities: tuple[GitHubCapability, ...] = (
        "read:issues",
        "read:issue-comments",
    )
    api_origin: Literal["https://api.github.com"] = Field(
        default=GITHUB_API_ORIGIN, alias="apiOrigin"
    )
    limits: GitHubPublicIssuesLimits = Field(default_factory=GitHubPublicIssuesLimits)

    @field_validator("owner")
    @classmethod
    def validate_owner(cls, value: str) -> str:
        return _validate_segment(value, _OWNER_PATTERN)

    @field_validator("repository")
    @classmethod
    def validate_repository(cls, value: str) -> str:
        return _validate_segment(value, _REPOSITORY_PATTERN)

    @model_validator(mode="after")
    def validate_capabilities(self) -> GitHubPublicIssuesInstallationConfig:
        if self.capabilities != ("read:issues", "read:issue-comments"):
            raise ValueError("GitHub Public Issues capabilities are fixed")
        return self

    @property
    def comparison_key(self) -> tuple[str, str]:
        return self.owner.casefold(), self.repository.casefold()

    @property
    def repository_label(self) -> str:
        return f"{self.owner}/{self.repository}"

    def safe_projection(self) -> dict[str, object]:
        """Return bounded configuration metadata safe for a public projection."""
        return {
            "connectorType": "github-public-issues",
            "repositoryLabel": self.repository_label,
            "capabilities": list(self.capabilities),
            "limits": self.limits.model_dump(mode="json", by_alias=True),
            "credentialRequired": False,
        }


GitHubStream = Literal["issues", "issue-comments"]
GitHubParentKind = Literal["issue", "pull-request", "unknown"]


class GitHubCursorError(ValueError):
    """Opaque GitHub cursor is malformed or exceeds the shared contract."""


class GitHubWatermark(BaseModel):
    """Inclusive provider watermark paired with the provider numeric ID."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    updated_at: datetime = Field(alias="updatedAt")
    numeric_id: int = Field(alias="numericId", ge=1, le=2**63 - 1)

    @field_validator("updated_at")
    @classmethod
    def normalize_updated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("watermark timestamp must include a timezone")
        return value.astimezone(UTC)


class GitHubCursor(BaseModel):
    """Versioned independent issue/comment watermarks."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal[1] = 1
    issue: GitHubWatermark | None = None
    comment: GitHubWatermark | None = None


class GitHubCursorCodec:
    """Encode/decode cursors without exposing provider IDs as public handles."""

    @staticmethod
    def encode(cursor: GitHubCursor) -> str:
        value = cursor.model_dump(mode="json", by_alias=True, exclude_none=True)
        body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        encoded = base64.urlsafe_b64encode(body).rstrip(b"=").decode("ascii")
        if len(encoded) > 512:
            raise GitHubCursorError("cursor exceeds contract limit")
        return encoded

    @staticmethod
    def decode(value: str) -> GitHubCursor:
        if not value or len(value) > 512 or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise GitHubCursorError("cursor is invalid")
        try:
            padded = value + "=" * (-len(value) % 4)
            payload = base64.urlsafe_b64decode(padded.encode("ascii"))
            cursor = GitHubCursor.model_validate(json.loads(payload.decode("utf-8")))
        except (ValueError, UnicodeError, json.JSONDecodeError) as error:
            raise GitHubCursorError("cursor is invalid") from error
        if GitHubCursorCodec.encode(cursor) != value:
            raise GitHubCursorError("cursor is not canonical")
        return cursor


def is_after_watermark(
    updated_at: datetime, numeric_id: int, watermark: GitHubWatermark | None
) -> bool:
    """Apply the local strict filter after GitHub's inclusive `since` query."""
    if watermark is None:
        return True
    candidate = (updated_at.astimezone(UTC), numeric_id)
    committed = (watermark.updated_at, watermark.numeric_id)
    return candidate > committed


class GitHubProviderOutputError(ValueError):
    """Provider payload cannot be safely mapped to a canonical event."""


def map_github_issue(
    payload: Mapping[str, object],
    *,
    installation_scope: str,
    config: GitHubPublicIssuesInstallationConfig,
) -> RawEventCandidate | None:
    """Map one issue observation, excluding pull requests deterministically."""
    if "pull_request" in payload:
        return None
    issue_id = _required_positive_int(payload, "id")
    number = _required_positive_int(payload, "number")
    updated_at = _required_timestamp(payload, "updated_at")
    created_at = _required_timestamp(payload, "created_at")
    _validate_repository_url(payload.get("repository_url"), config)
    title = _bounded_text(payload, "title", allow_empty=False)
    body = _bounded_optional_text(payload, "body")
    state = _bounded_choice(payload, "state", {"open", "closed"})
    labels = _safe_labels(payload.get("labels"))
    content = _canonical_bytes(
        {
            "kind": "issue",
            "number": number,
            "title": title,
            "body": body,
            "state": state,
            "labels": labels,
        }
    )
    return _candidate(
        resource_kind="issue",
        provider_id=issue_id,
        updated_at=updated_at,
        created_at=created_at,
        content=content,
        actor=_actor_hint(payload.get("user")),
        installation_scope=installation_scope,
    )


def map_github_issue_comment(
    payload: Mapping[str, object],
    *,
    installation_scope: str,
    config: GitHubPublicIssuesInstallationConfig,
    parent_kind: GitHubParentKind,
) -> RawEventCandidate | None:
    """Map a comment only when its parent is proven to be a bound issue."""
    if parent_kind != "issue":
        if parent_kind not in {"pull-request", "unknown"}:
            raise GitHubProviderOutputError("invalid parent classification")
        return None
    comment_id = _required_positive_int(payload, "id")
    updated_at = _required_timestamp(payload, "updated_at")
    created_at = _required_timestamp(payload, "created_at")
    issue_url = payload.get("issue_url")
    if not isinstance(issue_url, str) or not _is_bound_issue_url(issue_url, config):
        raise GitHubProviderOutputError("comment parent is outside the bound repository")
    issue_number = _required_positive_int_from_url(issue_url)
    body = _bounded_optional_text(payload, "body")
    content = _canonical_bytes(
        {
            "kind": "issue-comment",
            "issueNumber": issue_number,
            "body": body,
        }
    )
    return _candidate(
        resource_kind="issue-comment",
        provider_id=comment_id,
        updated_at=updated_at,
        created_at=created_at,
        content=content,
        actor=_actor_hint(payload.get("user")),
        installation_scope=installation_scope,
    )


def _candidate(
    *,
    resource_kind: str,
    provider_id: int,
    updated_at: datetime,
    created_at: datetime,
    content: bytes,
    actor: ActorHint | None,
    installation_scope: str,
) -> RawEventCandidate:
    revision_key = f"github-public-issues|{installation_scope}|{resource_kind}|{provider_id}|{updated_at.isoformat()}"
    event_id = "evt-" + hashlib.sha256(revision_key.encode("utf-8")).hexdigest()[:32]
    event_type: EventType = "source.created" if updated_at == created_at else "source.updated"
    reference_key = f"github-public-issues|{installation_scope}|{resource_kind}|{provider_id}"
    external_reference = "github://" + resource_kind + "/" + hashlib.sha256(
        reference_key.encode("utf-8")
    ).hexdigest()[:32]
    return RawEventCandidate(
        eventId=event_id,
        eventType=event_type,
        externalReference=external_reference,
        actorHint=actor,
        occurredAt=updated_at,
        contentType="application/json",
        contentBytes=content,
    )


def _canonical_bytes(value: Mapping[str, object]) -> bytes:
    content = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    if len(content) > 1024 * 1024:
        raise GitHubProviderOutputError("mapped evidence exceeds event limit")
    return content


def _required_positive_int(payload: Mapping[str, object], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > 2**63 - 1:
        raise GitHubProviderOutputError("provider identifier is invalid")
    return value


def _required_positive_int_from_url(value: str) -> int:
    match = re.search(r"/issues/(\d+)$", urlsplit(value).path)
    if match is None:
        raise GitHubProviderOutputError("issue parent identifier is invalid")
    return int(match.group(1))


def _required_timestamp(payload: Mapping[str, object], key: str) -> datetime:
    value = payload.get(key)
    if not isinstance(value, str):
        raise GitHubProviderOutputError("provider timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise GitHubProviderOutputError("provider timestamp is invalid") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise GitHubProviderOutputError("provider timestamp is invalid")
    return parsed.astimezone(UTC)


def _bounded_text(payload: Mapping[str, object], key: str, *, allow_empty: bool) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or len(value) > 16 * 1024:
        raise GitHubProviderOutputError("provider text is invalid")
    if not allow_empty and not value:
        raise GitHubProviderOutputError("provider text is empty")
    if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
        raise GitHubProviderOutputError("provider text contains a control character")
    return value


def _bounded_optional_text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if value is None:
        return ""
    return _bounded_text(payload, key, allow_empty=True)


def _bounded_choice(payload: Mapping[str, object], key: str, choices: set[str]) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or value not in choices:
        raise GitHubProviderOutputError("provider choice is invalid")
    return value


def _safe_labels(value: object) -> list[str]:
    if not isinstance(value, list):
        raise GitHubProviderOutputError("provider labels are invalid")
    items = cast(list[object], value)
    if len(items) > 128:
        raise GitHubProviderOutputError("provider labels are invalid")
    labels: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            raise GitHubProviderOutputError("provider labels are invalid")
        name = cast(dict[str, object], item).get("name")
        if not isinstance(name, str) or len(name) > 256 or any(ord(char) < 32 for char in name):
            raise GitHubProviderOutputError("provider label is invalid")
        labels.append(name)
    return sorted(set(labels))


def _actor_hint(value: object) -> ActorHint | None:
    if not isinstance(value, dict):
        return None
    actor = cast(dict[str, object], value)
    login = actor.get("login")
    provider_id = actor.get("id")
    if login is not None and (not isinstance(login, str) or len(login) > 256):
        raise GitHubProviderOutputError("provider actor is invalid")
    if provider_id is not None and (
        isinstance(provider_id, bool) or not isinstance(provider_id, int) or provider_id < 1
    ):
        raise GitHubProviderOutputError("provider actor is invalid")
    return ActorHint(
        sourceSystem="github",
        externalId=(sha256_digest(str(provider_id).encode("utf-8")) if provider_id is not None else None),
        displayLabel=login,
    )


def _validate_repository_url(value: object, config: GitHubPublicIssuesInstallationConfig) -> None:
    if value is not None and (not isinstance(value, str) or not _is_bound_repo_url(value, config)):
        raise GitHubProviderOutputError("provider repository is outside the installation")


def _is_bound_repo_url(value: str, config: GitHubPublicIssuesInstallationConfig) -> bool:
    parsed = urlsplit(value)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "api.github.com"
        and not parsed.username
        and not parsed.password
        and not parsed.fragment
        and parsed.path.casefold() == f"/repos/{config.owner}/{config.repository}".casefold()
    )


def _is_bound_issue_url(value: str, config: GitHubPublicIssuesInstallationConfig) -> bool:
    parsed = urlsplit(value)
    prefix = f"/repos/{config.owner}/{config.repository}/issues/"
    return (
        parsed.scheme == "https"
        and parsed.hostname == "api.github.com"
        and not parsed.username
        and not parsed.password
        and not parsed.fragment
        and parsed.path.casefold().startswith(prefix.casefold())
        and bool(re.fullmatch(r"\d+", parsed.path.rsplit("/", 1)[-1]))
    )


class GitHubHttpPage(BaseModel):
    """One bounded provider page; the body is never exposed publicly."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)
    status_code: int = Field(ge=100, le=599, alias="statusCode")
    headers: Mapping[str, str]
    body: bytes = Field(max_length=10 * 1024 * 1024)
    next_url: str | None = Field(default=None, alias="nextUrl", max_length=2048)


class GitHubTransportError(RuntimeError):
    """Safe transport error classified later by the connector adapter."""

    def __init__(self, code: str, *, status_code: int | None = None) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(code)


class GitHubFailureMapping(BaseModel):
    """Finite safe outcome returned by provider failure normalization."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    outcome: SyncOutcome
    code: ErrorCode | None = None
    retry_after_seconds: int | None = Field(default=None, ge=0, le=3600, alias="retryAfterSeconds")


def map_github_failure(
    *,
    status_code: int | None = None,
    headers: Mapping[str, str] | None = None,
    transport_error: GitHubTransportError | None = None,
) -> GitHubFailureMapping:
    """Map provider/transport results without exposing body or arbitrary headers."""
    normalized_headers = {key.casefold(): value for key, value in (headers or {}).items()}
    if transport_error is not None:
        mapping = {
            "deadline-exceeded": GitHubFailureMapping(
                outcome="deadline-exceeded", code="ADAPTER_DEADLINE_EXCEEDED"
            ),
            "transport-unavailable": GitHubFailureMapping(
                outcome="unavailable", code="ADAPTER_UNAVAILABLE"
            ),
            "redirect-rejected": GitHubFailureMapping(
                outcome="malformed-output", code="ADAPTER_OUTPUT_INVALID"
            ),
            "pagination-link-invalid": GitHubFailureMapping(
                outcome="malformed-output", code="ADAPTER_OUTPUT_INVALID"
            ),
            "pagination-cycle": GitHubFailureMapping(
                outcome="malformed-output", code="ADAPTER_OUTPUT_INVALID"
            ),
            "response-byte-limit-exceeded": GitHubFailureMapping(outcome="truncated"),
            "page-budget-exceeded": GitHubFailureMapping(outcome="truncated"),
        }
        return mapping.get(
            transport_error.code,
            GitHubFailureMapping(outcome="failed", code="ADAPTER_FAILED"),
        )
    if status_code == 404:
        return GitHubFailureMapping(outcome="invalid-installation", code="ADAPTER_PROVIDER_NOT_FOUND")
    if status_code == 429 or (
        status_code == 403 and normalized_headers.get("x-ratelimit-remaining") == "0"
    ):
        retry_after = _bounded_retry_after(normalized_headers.get("retry-after"))
        return GitHubFailureMapping(
            outcome="rate-limited", code="ADAPTER_RATE_LIMITED", retryAfterSeconds=retry_after
        )
    if status_code == 403:
        return GitHubFailureMapping(outcome="failed", code="ADAPTER_PERMISSION_DENIED")
    if status_code is not None and 500 <= status_code <= 599:
        return GitHubFailureMapping(outcome="unavailable", code="ADAPTER_UNAVAILABLE")
    if status_code in {301, 302, 303, 307, 308, 422}:
        return GitHubFailureMapping(outcome="malformed-output", code="ADAPTER_OUTPUT_INVALID")
    return GitHubFailureMapping(outcome="failed", code="ADAPTER_FAILED")


def _bounded_retry_after(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        seconds = int(value)
    except ValueError:
        return None
    return seconds if 0 <= seconds <= 3600 else None


class GitHubPublicIssuesAdapter:
    """Provider-neutral adapter facade for the bounded GitHub primitives."""

    def __init__(self, transport: GitHubPublicIssuesHttpTransport | None = None) -> None:
        self._transport = transport or GitHubPublicIssuesHttpTransport()

    def descriptor(self) -> ConnectorDescriptor:
        return ConnectorDescriptor(
            connectorType="github-public-issues",
            displayName="GitHub Public Issues",
            capabilities=("inbound-import",),
            limits=ConnectorLimits(),
        )

    async def validate_installation(
        self, config: InstallationConfig, context: AdapterContext
    ) -> InstallationValidation:
        if context.connector_type != "github-public-issues" or config.provider_config is None:
            return InstallationValidation(outcome="invalid", code="ADAPTER_INSTALLATION_INVALID")
        try:
            binding = GitHubPublicIssuesInstallationConfig.model_validate(config.provider_config)
        except ValueError:
            return InstallationValidation(outcome="invalid", code="ADAPTER_INSTALLATION_INVALID")
        if tuple(config.declared_capabilities) != ("inbound-import",):
            return InstallationValidation(outcome="unsupported", code="ADAPTER_CAPABILITY_UNSUPPORTED")
        if binding.api_origin != GITHUB_API_ORIGIN:
            return InstallationValidation(outcome="invalid", code="ADAPTER_SCOPE_INVALID")
        return InstallationValidation(outcome="valid")

    async def pull_events(self, command: PullEventsCommand) -> PullEventsResult:
        try:
            config = GitHubPublicIssuesInstallationConfig.model_validate(command.provider_config or {})
            cursor = (
                GitHubCursorCodec.decode(command.cursor.value) if command.cursor is not None else GitHubCursor()
            )
        except (ValueError, GitHubCursorError):
            return PullEventsResult(
                events=(), sourceBytes=0, outcome="invalid-installation", failureCode="ADAPTER_INSTALLATION_INVALID"
            )
        issue_since = cursor.issue.updated_at if cursor.issue else _initial_lookback(config)
        comment_since = cursor.comment.updated_at if cursor.comment else _initial_lookback(config)
        request_count = 0
        downloaded_bytes = 0
        remaining_bytes = min(command.max_bytes, config.limits.max_run_bytes)
        visited_next_urls: set[str] = set()
        issue_items: list[Mapping[str, object]] = []
        comment_items: list[Mapping[str, object]] = []
        streams: tuple[tuple[GitHubStream, datetime, list[Mapping[str, object]]], ...] = (
            ("issues", issue_since, issue_items),
            ("issue-comments", comment_since, comment_items),
        )
        for stream, since, target in streams:
            page_number = 1
            next_url: str | None = None
            while True:
                request_count += 1
                if request_count > config.limits.max_requests:
                    return _github_pull_partial(
                        command, config, cursor, issue_items, comment_items, downloaded_bytes
                    )
                if remaining_bytes <= 0:
                    return _github_pull_partial(
                        command, config, cursor, issue_items, comment_items, downloaded_bytes
                    )
                if next_url is not None:
                    if next_url in visited_next_urls:
                        return _github_pull_failure(
                            "malformed-output", "ADAPTER_OUTPUT_INVALID"
                        )
                    visited_next_urls.add(next_url)
                try:
                    page = await self._transport.fetch_page(
                        config,
                        stream,
                        since=since,
                        page=page_number,
                        deadline=command.deadline,
                        max_bytes=remaining_bytes,
                        next_url=next_url,
                    )
                except GitHubTransportError as error:
                    failure = map_github_failure(transport_error=error)
                    if error.code in {"response-byte-limit-exceeded", "page-budget-exceeded"}:
                        return _github_pull_partial(
                            command,
                            config,
                            cursor,
                            issue_items,
                            comment_items,
                            downloaded_bytes,
                        )
                    return _github_pull_failure(failure.outcome, failure.code)
                if page.status_code != 200:
                    failure = map_github_failure(status_code=page.status_code, headers=page.headers)
                    return _github_pull_failure(failure.outcome, failure.code)
                try:
                    body = json.loads(page.body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    return _github_pull_failure("malformed-output", "ADAPTER_OUTPUT_INVALID")
                if not isinstance(body, list):
                    return _github_pull_failure("malformed-output", "ADAPTER_OUTPUT_INVALID")
                if len(page.body) > remaining_bytes:
                    return _github_pull_partial(
                        command,
                        config,
                        cursor,
                        issue_items,
                        comment_items,
                        downloaded_bytes,
                    )
                downloaded_bytes += len(page.body)
                remaining_bytes -= len(page.body)
                for item in cast(list[object], body):
                    if not isinstance(item, dict):
                        return _github_pull_failure("malformed-output", "ADAPTER_OUTPUT_INVALID")
                    target.append(cast(dict[str, object], item))
                if page.next_url is None:
                    break
                if page.next_url in visited_next_urls:
                    return _github_pull_failure("malformed-output", "ADAPTER_OUTPUT_INVALID")
                page_number += 1
                next_url = page.next_url
        try:
            return _map_github_streams(
                command,
                config,
                cursor,
                issue_items,
                comment_items,
                source_bytes=downloaded_bytes,
            )
        except GitHubProviderOutputError:
            return _github_pull_failure("malformed-output", "ADAPTER_OUTPUT_INVALID")

    async def fetch_resource(self, external_reference: str, context: AdapterContext) -> ResourceResult:
        raise ValueError("ADAPTER_REFERENCE_INVALID")

    async def resolve_identity_hint(
        self, external_reference: str, context: AdapterContext
    ) -> IdentityHintResult:
        return IdentityHintResult(state="none")


def _initial_lookback(config: GitHubPublicIssuesInstallationConfig) -> datetime:
    return datetime.now(UTC) - timedelta(days=config.limits.first_run_lookback_days)


def _github_pull_failure(
    outcome: SyncOutcome, code: ErrorCode | None = None
) -> PullEventsResult:
    return PullEventsResult(events=(), sourceBytes=0, outcome=outcome, failureCode=code)


def _github_pull_partial(
    command: PullEventsCommand,
    config: GitHubPublicIssuesInstallationConfig,
    cursor: GitHubCursor,
    issue_items: list[Mapping[str, object]],
    comment_items: list[Mapping[str, object]],
    source_bytes: int,
) -> PullEventsResult:
    """Keep valid observations from earlier pages while refusing cursor advancement."""
    try:
        partial = _map_github_streams(
            command,
            config,
            cursor,
            issue_items,
            comment_items,
            source_bytes=source_bytes,
        )
    except GitHubProviderOutputError:
        return _github_pull_failure("malformed-output", "ADAPTER_OUTPUT_INVALID")
    return partial.model_copy(update={"outcome": "truncated", "next_cursor": None})


def _map_github_streams(
    command: PullEventsCommand,
    config: GitHubPublicIssuesInstallationConfig,
    cursor: GitHubCursor,
    issue_items: list[Mapping[str, object]],
    comment_items: list[Mapping[str, object]],
    *,
    source_bytes: int = 0,
) -> PullEventsResult:
    issue_items.sort(
        key=lambda item: (_required_timestamp(item, "updated_at"), _required_positive_int(item, "id"))
    )
    comment_items.sort(
        key=lambda item: (_required_timestamp(item, "updated_at"), _required_positive_int(item, "id"))
    )
    pull_request_numbers = {
        _required_positive_int(item, "number")
        for item in issue_items
        if "pull_request" in item
    }
    issue_numbers = {
        _required_positive_int(item, "number")
        for item in issue_items
        if "pull_request" not in item
    }
    issue_items = [
        item
        for item in issue_items
        if is_after_watermark(
            _required_timestamp(item, "updated_at"),
            _required_positive_int(item, "id"),
            cursor.issue,
        )
    ]
    comment_items = [
        item
        for item in comment_items
        if is_after_watermark(
            _required_timestamp(item, "updated_at"),
            _required_positive_int(item, "id"),
            cursor.comment,
        )
    ]
    events: list[RawEventCandidate] = []
    event_bytes = 0
    issue_watermark = cursor.issue
    comment_watermark = cursor.comment
    truncated = False
    for item in issue_items:
        issue_id = _required_positive_int(item, "id")
        issue_updated = _required_timestamp(item, "updated_at")
        issue_watermark = GitHubWatermark(updatedAt=issue_updated, numericId=issue_id)
        mapped = map_github_issue(item, installation_scope=command.installation_id, config=config)
        if mapped is None:
            continue
        if len(events) >= command.max_events or event_bytes + len(mapped.content_bytes) > command.max_bytes:
            truncated = True
            break
        events.append(mapped)
        event_bytes += len(mapped.content_bytes)
    if not truncated:
        for item in comment_items:
            comment_id = _required_positive_int(item, "id")
            comment_updated = _required_timestamp(item, "updated_at")
            comment_watermark = GitHubWatermark(updatedAt=comment_updated, numericId=comment_id)
            issue_url = item.get("issue_url")
            parent_number = _required_positive_int_from_url(issue_url) if isinstance(issue_url, str) else 0
            parent_kind: GitHubParentKind = (
                "pull-request" if parent_number in pull_request_numbers else
                "issue" if parent_number in issue_numbers else "unknown"
            )
            mapped = map_github_issue_comment(
                item,
                installation_scope=command.installation_id,
                config=config,
                parent_kind=parent_kind,
            )
            if mapped is None:
                if parent_kind == "unknown":
                    truncated = True
                continue
            if len(events) >= command.max_events or event_bytes + len(mapped.content_bytes) > command.max_bytes:
                truncated = True
                break
            events.append(mapped)
            event_bytes += len(mapped.content_bytes)
    next_cursor = None if truncated else OpaqueCursor(
        value=GitHubCursorCodec.encode(GitHubCursor(issue=issue_watermark, comment=comment_watermark))
    )
    return PullEventsResult(
        events=tuple(events),
        nextCursor=next_cursor,
        sourceBytes=source_bytes,
        outcome="truncated" if truncated else ("succeeded" if events else "empty"),
    )


class GitHubPublicIssuesHttpTransport:
    """Fixed-origin, one-attempt GitHub REST transport."""

    _USER_AGENT = "Projecta/0.7"
    _API_VERSION = "2026-03-10"
    def __init__(self, *, http_transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._client = httpx.AsyncClient(
            follow_redirects=False,
            max_redirects=0,
            timeout=None,
            transport=http_transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch_page(
        self,
        config: GitHubPublicIssuesInstallationConfig,
        stream: GitHubStream,
        *,
        since: datetime | None,
        page: int,
        deadline: datetime,
        max_bytes: int | None = None,
        next_url: str | None = None,
    ) -> GitHubHttpPage:
        if page < 1 or page > config.limits.max_pages_per_stream:
            raise GitHubTransportError("page-budget-exceeded")
        if next_url is None:
            path = _stream_path(config, stream)
            params = _stream_params(stream, since, page)
            url = f"{GITHUB_API_ORIGIN}{path}"
        else:
            validated_next = _validate_next_link(next_url, config, stream)
            url = f"{GITHUB_API_ORIGIN}{validated_next}"
            params = None
        remaining = (deadline.astimezone(UTC) - datetime.now(UTC)).total_seconds()
        if remaining <= 0:
            raise GitHubTransportError("deadline-exceeded")
        byte_limit: int = max_bytes if max_bytes is not None else config.limits.max_run_bytes
        if byte_limit < 1 or byte_limit > config.limits.max_run_bytes:
            raise GitHubTransportError("byte-budget-invalid")
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": self._USER_AGENT,
            "X-GitHub-Api-Version": self._API_VERSION,
        }
        try:
            async with asyncio.timeout(remaining):
                async with self._client.stream(
                    "GET", url, params=params, headers=headers
                ) as response:
                    response_headers = {
                        key.lower(): value for key, value in response.headers.items()
                    }
                    if response.status_code != 200:
                        if 300 <= response.status_code < 400:
                            raise GitHubTransportError(
                                "redirect-rejected", status_code=response.status_code
                            )
                        return GitHubHttpPage(
                            statusCode=response.status_code,
                            headers=response_headers,
                            body=b"",
                        )
                    body = await _read_bounded(response.aiter_bytes(), byte_limit)
                    next_header = response_headers.get("link")
                    next_page = _extract_next_link(next_header) if next_header else None
                    if next_page is not None:
                        next_page = _validate_next_link(next_page, config, stream)
                    return GitHubHttpPage(
                        statusCode=response.status_code,
                        headers=response_headers,
                        body=body,
                        nextUrl=next_page,
                    )
        except TimeoutError as error:
            raise GitHubTransportError("deadline-exceeded") from error
        except httpx.HTTPError as error:
            raise GitHubTransportError("transport-unavailable") from error


async def _read_bounded(chunks: AsyncIterator[bytes], limit: int) -> bytes:
    parts: list[bytes] = []
    total = 0
    async for chunk in chunks:
        total += len(chunk)
        if total > limit:
            raise GitHubTransportError("response-byte-limit-exceeded")
        parts.append(chunk)
    return b"".join(parts)


def _stream_path(config: GitHubPublicIssuesInstallationConfig, stream: GitHubStream) -> str:
    suffix = "issues" if stream == "issues" else "issues/comments"
    return f"/repos/{config.owner}/{config.repository}/{suffix}"


def _stream_params(stream: GitHubStream, since: datetime | None, page: int) -> dict[str, str]:
    params = {"sort": "updated", "direction": "asc", "per_page": "100", "page": str(page)}
    if stream == "issues":
        params["state"] = "all"
    if since is not None:
        params["since"] = since.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return params


def _extract_next_link(value: str) -> str | None:
    if len(value) > 2048:
        raise GitHubTransportError("pagination-link-invalid")
    links = [part.strip() for part in value.split(",") if part.strip()]
    for link in links:
        match = re.fullmatch(r'<([^>]+)>\s*;\s*rel="next"', link)
        if match:
            return match.group(1)
    return None


def _validate_next_link(
    value: str, config: GitHubPublicIssuesInstallationConfig, stream: GitHubStream
) -> str:
    if len(value) > 2048:
        raise GitHubTransportError("pagination-link-invalid")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.github.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or parsed.port is not None
    ):
        raise GitHubTransportError("pagination-link-invalid")
    expected_path = _stream_path(config, stream)
    if parsed.path.casefold() != expected_path.casefold():
        raise GitHubTransportError("pagination-link-invalid")
    try:
        query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
    except ValueError as error:
        raise GitHubTransportError("pagination-link-invalid") from error
    allowed = {"sort", "direction", "since", "per_page", "page"}
    if stream == "issues":
        allowed.add("state")
    if any(key not in allowed or len(values) != 1 for key, values in query.items()):
        raise GitHubTransportError("pagination-link-invalid")
    if stream == "issues" and query.get("state") != ["all"]:
        raise GitHubTransportError("pagination-link-invalid")
    if stream == "issue-comments" and "state" in query:
        raise GitHubTransportError("pagination-link-invalid")
    if query.get("sort") != ["updated"] or query.get("direction") != ["asc"]:
        raise GitHubTransportError("pagination-link-invalid")
    try:
        per_page = int(query.get("per_page", ["100"])[0])
        page = int(query.get("page", ["1"])[0])
    except ValueError as error:
        raise GitHubTransportError("pagination-link-invalid") from error
    if not 1 <= per_page <= 100 or page < 1:
        raise GitHubTransportError("pagination-link-invalid")
    if "since" in query:
        _parse_timestamp(query["since"][0])
    safe_query = urlencode(sorted((key, values[0]) for key, values in query.items()))
    return f"{expected_path}?{safe_query}"


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise GitHubTransportError("pagination-link-invalid") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise GitHubTransportError("pagination-link-invalid")
    return parsed.astimezone(UTC)


def _validate_segment(value: str, pattern: re.Pattern[str]) -> str:
    normalized = value.strip()
    if normalized != value or any(ord(char) < 32 for char in normalized):
        raise ValueError("repository scope contains invalid whitespace or control characters")
    if "%" in normalized or "/" in normalized or "\\" in normalized:
        raise ValueError("repository scope must be one path segment")
    if normalized in {".", ".."} or not pattern.fullmatch(normalized):
        raise ValueError("repository scope is invalid")
    return normalized
