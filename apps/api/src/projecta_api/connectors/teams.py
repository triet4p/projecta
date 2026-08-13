"""Bounded, read-only Microsoft Teams adapter for one installation scope."""

from __future__ import annotations

import hashlib
import html
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any, Protocol, cast
from urllib.parse import parse_qs, quote, urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from projecta_api.connectors.contracts import (
    ActorHint,
    ConnectorDescriptor,
    ConnectorLimits,
    ContentType,
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
    ConnectorAdapter,
    IdentityHintResult,
    InstallationValidation,
    ResourceResult,
)
from projecta_api.connectors.teams_auth import TeamsCredentialError, TeamsCredentialProvider

_GRAPH_HOST = "graph.microsoft.com"
_GRAPH_PREFIX = "/v1.0/teams/"
_MAX_GRAPH_RESPONSE_BYTES = 10 * 1024 * 1024
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_:@.-]{0,255}$")


class TeamsInstallationConfig(BaseModel):
    """Internal installation binding; provider identifiers never become public DTOs."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    tenant_id: str = Field(alias="tenantId", min_length=1, max_length=128)
    team_id: str = Field(alias="teamId", min_length=1, max_length=256)
    channel_id: str = Field(alias="channelId", min_length=1, max_length=256)
    secret_reference: str = Field(alias="secretReference", min_length=10, max_length=128)
    credential_revision: int = Field(default=1, alias="credentialRevision", ge=1)
    capabilities: tuple[str, ...] = ("inbound-import",)
    max_events: int = Field(default=100, ge=1, le=100)
    max_run_bytes: int = Field(default=10 * 1024 * 1024, ge=1, le=10 * 1024 * 1024)
    max_event_bytes: int = Field(default=1024 * 1024, ge=1, le=1024 * 1024)
    max_replies_per_root: int = Field(default=10, ge=1, le=10)
    max_replies_total: int = Field(default=50, ge=1, le=50)

    @field_validator("tenant_id", "team_id", "channel_id")
    @classmethod
    def validate_provider_id(cls, value: str) -> str:
        if not _SAFE_ID.fullmatch(value) or "/" in value or "\\" in value:
            raise ValueError("Teams installation identifier is invalid")
        return value

    @field_validator("secret_reference")
    @classmethod
    def validate_secret_reference(cls, value: str) -> str:
        if not re.fullmatch(r"secret_[A-Za-z0-9_-]{10,128}", value):
            raise ValueError("Teams secret reference is invalid")
        return value

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != ("inbound-import",):
            raise ValueError("Teams supports only inbound-import")
        return value


@dataclass
class _GraphResponse:
    status_code: int
    body: object
    headers: Mapping[str, str]


class TeamsGraphTransport(Protocol):
    async def get(
        self,
        path: str,
        token: str,
        params: Mapping[str, str] | None,
        deadline: datetime,
    ) -> _GraphResponse: ...


class TeamsProviderError(RuntimeError):
    def __init__(self, code: str) -> None:
        allowed = {
            "CREDENTIAL_INVALID",
            "PERMISSION_DENIED",
            "PROVIDER_NOT_FOUND",
            "RATE_LIMITED",
            "UNAVAILABLE",
            "MALFORMED_OUTPUT",
            "DEADLINE_EXCEEDED",
        }
        self.code = code if code in allowed else "UNAVAILABLE"
        super().__init__(self.code)


class _TeamsContentLimit(RuntimeError):
    """Internal signal for truthful truncation rather than malformed output."""


class HttpTeamsGraphTransport:
    """One-attempt Graph transport with fixed host and no redirect/retry."""

    async def get(
        self,
        path: str,
        token: str,
        params: Mapping[str, str] | None,
        deadline: datetime,
    ) -> _GraphResponse:
        if not _is_graph_path(path):
            raise TeamsProviderError("MALFORMED_OUTPUT")
        remaining = (deadline - datetime.now(UTC)).total_seconds()
        if remaining <= 0:
            raise TeamsProviderError("DEADLINE_EXCEEDED")
        try:
            async with httpx.AsyncClient(
                base_url="https://graph.microsoft.com",
                follow_redirects=False,
                timeout=max(0.1, min(5.0, remaining)),
            ) as client:
                response = await client.get(
                    path,
                    params=params,
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                )
                if len(response.content) > _MAX_GRAPH_RESPONSE_BYTES:
                    raise TeamsProviderError("MALFORMED_OUTPUT")
                body = response.json()
        except httpx.TimeoutException as error:
            raise TeamsProviderError("DEADLINE_EXCEEDED") from error
        except (httpx.HTTPError, ValueError) as error:
            raise TeamsProviderError("UNAVAILABLE") from error
        if response.status_code == 401:
            raise TeamsProviderError("CREDENTIAL_INVALID")
        if response.status_code == 403:
            raise TeamsProviderError("PERMISSION_DENIED")
        if response.status_code == 404:
            raise TeamsProviderError("PROVIDER_NOT_FOUND")
        if response.status_code == 429:
            raise TeamsProviderError("RATE_LIMITED")
        if response.status_code != 200:
            raise TeamsProviderError("UNAVAILABLE")
        return _GraphResponse(response.status_code, body, response.headers)


class TeamsAdapter(ConnectorAdapter):
    """Read one bounded root page and bounded reply pages for one installation."""

    DESCRIPTOR = ConnectorDescriptor(
        connectorType="teams",
        displayName="Microsoft Teams (read-only)",
        capabilities=("inbound-import", "cancellation"),
        limits=ConnectorLimits(),
    )

    def __init__(self, credentials: TeamsCredentialProvider, graph: TeamsGraphTransport) -> None:
        self._credentials = credentials
        self._graph = graph

    def descriptor(self) -> ConnectorDescriptor:
        return self.DESCRIPTOR

    async def validate_installation(
        self, config: InstallationConfig, context: AdapterContext
    ) -> InstallationValidation:
        if context.connector_type != "teams" or config.provider_config is None:
            return InstallationValidation(outcome="invalid", code="ADAPTER_INSTALLATION_INVALID")
        try:
            binding = TeamsInstallationConfig.model_validate(config.provider_config)
        except ValidationError:
            return InstallationValidation(outcome="invalid", code="ADAPTER_INSTALLATION_INVALID")
        if "inbound-import" not in config.declared_capabilities or tuple(config.declared_capabilities) != binding.capabilities:
            return InstallationValidation(outcome="unsupported", code="ADAPTER_CAPABILITY_UNSUPPORTED")
        if binding.credential_revision < 1:
            return InstallationValidation(outcome="invalid", code="ADAPTER_SCOPE_INVALID")
        return InstallationValidation(outcome="valid")

    async def pull_events(self, command: PullEventsCommand) -> PullEventsResult:
        if command.capability != "inbound-import":
            return _failure("unsupported-capability", "ADAPTER_CONTRACT_UNSUPPORTED")
        try:
            binding = TeamsInstallationConfig.model_validate(command.provider_config or {})
            token = await self._credentials.get_token(
                _scope(command, binding), binding.secret_reference, command.deadline
            )
            return await self._pull_bounded(command, binding, token)
        except TeamsCredentialError as error:
            return _credential_failure(error.code)
        except TeamsProviderError as error:
            return _provider_failure(error.code)
        except (ValidationError, ValueError):
            return _failure("malformed-output", "ADAPTER_INSTALLATION_INVALID")

    async def _pull_bounded(
        self, command: PullEventsCommand, binding: TeamsInstallationConfig, token: str
    ) -> PullEventsResult:
        root_path = _messages_path(binding)
        root = await self._get(root_path, token, {"$top": "50"}, command.deadline)
        roots, root_next = _parse_messages(root.body)
        watermark = _cursor_watermark(command.cursor)
        truncated = False
        if root_next is not None:
            _validate_next_link(root_next, binding, root_path)
            truncated = True
        events: list[RawEventCandidate] = []
        source_bytes = 0
        reply_total = 0
        latest_modified: datetime | None = None
        for root_message in roots:
            if _remaining(command.deadline) <= 0:
                return _failure("deadline-exceeded", "ADAPTER_DEADLINE_EXCEEDED")
            try:
                candidate = _candidate(command, binding, root_message, None)
            except _TeamsContentLimit:
                truncated = True
                break
            if watermark is None or candidate.occurred_at > watermark:
                if source_bytes + len(candidate.content_bytes) > binding.max_run_bytes or len(events) >= binding.max_events:
                    truncated = True
                    break
                events.append(candidate)
                source_bytes += len(candidate.content_bytes)
                latest_modified = max(latest_modified or candidate.occurred_at, candidate.occurred_at)
            reply_events, reply_bytes, replies_truncated, _ = await self._replies(
                command, binding, token, root_message, binding.max_replies_total - reply_total
            )
            reply_total += len(reply_events)
            for reply in reply_events:
                if watermark is not None and reply.occurred_at <= watermark:
                    continue
                if len(events) >= binding.max_events or source_bytes + len(reply.content_bytes) > binding.max_run_bytes:
                    truncated = True
                    break
                events.append(reply)
                source_bytes += len(reply.content_bytes)
                latest_modified = max(latest_modified or reply.occurred_at, reply.occurred_at)
            truncated = truncated or replies_truncated or reply_bytes > binding.max_run_bytes
            if reply_total >= binding.max_replies_total:
                truncated = True
            if truncated and len(events) >= binding.max_events:
                break
        next_cursor = None if truncated or latest_modified is None else OpaqueCursor(
            value=f"teams.v1|{latest_modified.isoformat()}|{sha256_digest(str(len(events)).encode())[7:23]}"
        )
        outcome: SyncOutcome = "truncated" if truncated else ("empty" if not events else "succeeded")
        return PullEventsResult(
            events=tuple(events), nextCursor=next_cursor, sourceBytes=source_bytes, outcome=outcome
        )

    async def _replies(
        self,
        command: PullEventsCommand,
        binding: TeamsInstallationConfig,
        token: str,
        root: Mapping[str, object],
        reply_budget: int,
    ) -> tuple[list[RawEventCandidate], int, bool, datetime | None]:
        root_id = _required_text(root, "id")
        path = f"{_messages_path(binding)}/{quote(root_id, safe='')}/replies"
        events: list[RawEventCandidate] = []
        total_bytes = 0
        truncated = False
        latest: datetime | None = None
        next_path: str | None = path
        params: Mapping[str, str] | None = {"$top": "10"}
        per_root_limit = min(binding.max_replies_per_root, max(0, reply_budget))
        while next_path and len(events) < per_root_limit and _remaining(command.deadline) > 0:
            response = await self._get(next_path, token, params, command.deadline)
            messages, next_link = _parse_messages(response.body)
            for message in messages:
                if len(events) >= per_root_limit:
                    truncated = True
                    break
                try:
                    candidate = _candidate(command, binding, message, root_id)
                except _TeamsContentLimit:
                    truncated = True
                    break
                events.append(candidate)
                total_bytes += len(candidate.content_bytes)
                latest = max(latest or candidate.occurred_at, candidate.occurred_at)
            if next_link is None:
                next_path = None
            else:
                next_path = _validate_next_link(next_link, binding, path)
                params = None
                if len(events) >= binding.max_replies_per_root:
                    truncated = True
        if _remaining(command.deadline) <= 0 and next_path:
            raise TeamsProviderError("DEADLINE_EXCEEDED")
        if next_path and len(events) >= per_root_limit:
            truncated = True
        return events, total_bytes, truncated, latest

    async def _get(
        self,
        path: str,
        token: str,
        params: Mapping[str, str] | None,
        deadline: datetime,
    ) -> _GraphResponse:
        response = await self._graph.get(path, token, params, deadline)
        if not isinstance(response.body, dict):
            raise TeamsProviderError("MALFORMED_OUTPUT")
        return response

    async def fetch_resource(self, external_reference: str, context: AdapterContext) -> ResourceResult:
        raise ValueError("ADAPTER_CONTRACT_UNSUPPORTED")

    async def resolve_identity_hint(
        self, external_reference: str, context: AdapterContext
    ) -> IdentityHintResult:
        return IdentityHintResult(state="none")


def _scope(command: PullEventsCommand, binding: TeamsInstallationConfig):
    from projecta_api.configuration.ports import SecretScope

    return SecretScope(
        command.project_id,
        command.installation_id,
        "teams",
        binding.tenant_id,
        binding.credential_revision,
    )


def _messages_path(binding: TeamsInstallationConfig) -> str:
    return f"{_GRAPH_PREFIX}{quote(binding.team_id, safe='')}/channels/{quote(binding.channel_id, safe='')}/messages"


def _parse_messages(body: object) -> tuple[list[Mapping[str, object]], str | None]:
    if not isinstance(body, dict):
        raise TeamsProviderError("MALFORMED_OUTPUT")
    body_object = cast(dict[object, object], body)
    raw_messages = body_object.get("value")
    if not isinstance(raw_messages, list):
        raise TeamsProviderError("MALFORMED_OUTPUT")
    messages: list[Mapping[str, object]] = []
    for item in cast(list[object], raw_messages):
        if not isinstance(item, dict):
            raise TeamsProviderError("MALFORMED_OUTPUT")
        messages.append(cast(dict[str, object], item))
    next_link = body_object.get("@odata.nextLink")
    if next_link is not None and not isinstance(next_link, str):
        raise TeamsProviderError("MALFORMED_OUTPUT")
    return messages, next_link


def _candidate(
    command: PullEventsCommand,
    binding: TeamsInstallationConfig,
    message: Mapping[str, object],
    parent_id: str | None,
) -> RawEventCandidate:
    message_id = _required_text(message, "id")
    modified = _timestamp(message, "lastModifiedDateTime")
    created = _timestamp(message, "createdDateTime", default=modified)
    body = message.get("body")
    body_text = _safe_body_text(body)
    deleted = message.get("deletedDateTime") is not None
    if not body_text and not deleted:
        raise TeamsProviderError("MALFORMED_OUTPUT")
    actor = _actor_hint(message.get("from"))
    content_payload = {
        "bodyText": body_text or "Message deleted",
        "deleted": deleted,
        "messageKind": "reply" if parent_id else "root",
        "parentReference": _digest(parent_id) if parent_id else None,
    }
    content = json.dumps(content_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    if len(content) > binding.max_event_bytes:
        raise _TeamsContentLimit
    event_key = f"{command.project_id}|{command.installation_id}|{binding.tenant_id}|{binding.team_id}|{binding.channel_id}|{message_id}|{modified.isoformat()}"
    event_id = "evt-" + hashlib.sha256(event_key.encode()).hexdigest()[:32]
    external_reference = "teams://message/" + _digest(message_id)
    event_type: EventType = "source.updated" if modified > created or deleted else "source.created"
    return RawEventCandidate(
        eventId=event_id,
        eventType=event_type,
        externalReference=external_reference,
        actorHint=actor,
        occurredAt=modified,
        contentType=cast(ContentType, "application/json"),
        contentBytes=content,
    )


def _safe_body_text(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    raw = cast(dict[object, object], value).get("content")
    if not isinstance(raw, str):
        return ""
    parser = _TextExtractor()
    try:
        parser.feed(raw)
        parser.close()
    except Exception:
        return ""
    text = html.unescape(" ".join(parser.parts))
    return " ".join(text.split())


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _actor_hint(value: object) -> ActorHint | None:
    if not isinstance(value, dict):
        return None
    user = cast(dict[object, object], value).get("user")
    if not isinstance(user, dict):
        return None
    user_object = cast(dict[object, object], user)
    raw_id = user_object.get("id")
    display = user_object.get("displayName")
    return ActorHint(
        sourceSystem="microsoft-teams",
        externalId=_digest(raw_id) if isinstance(raw_id, str) else None,
        displayLabel=display[:256] if isinstance(display, str) else None,
    )


def _required_text(message: Mapping[str, object], key: str) -> str:
    value = message.get(key)
    if not isinstance(value, str) or not value or len(value) > 512:
        raise TeamsProviderError("MALFORMED_OUTPUT")
    return value


def _timestamp(message: Mapping[str, object], key: str, *, default: datetime | None = None) -> datetime:
    value = message.get(key)
    if not isinstance(value, str):
        if default is not None:
            return default
        raise TeamsProviderError("MALFORMED_OUTPUT")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError as error:
        raise TeamsProviderError("MALFORMED_OUTPUT") from error


def _validate_next_link(
    value: str, binding: TeamsInstallationConfig, expected_prefix: str
) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.netloc != _GRAPH_HOST or parsed.fragment:
        raise TeamsProviderError("MALFORMED_OUTPUT")
    expected_path_prefix = _messages_path(binding)
    if not parsed.path.startswith(expected_path_prefix) or parsed.path != expected_prefix or len(value) > 2048:
        raise TeamsProviderError("MALFORMED_OUTPUT")
    query = parse_qs(parsed.query, keep_blank_values=True)
    if any(len(key) > 128 or any(len(item) > 512 for item in values) for key, values in query.items()):
        raise TeamsProviderError("MALFORMED_OUTPUT")
    return parsed.path + (f"?{parsed.query}" if parsed.query else "")


def _is_graph_path(path: str) -> bool:
    parsed = urlsplit(path)
    return parsed.scheme == "" and parsed.netloc == "" and path.startswith(_GRAPH_PREFIX) and ".." not in path


def _digest(value: str | None) -> str:
    return hashlib.sha256((value or "").encode()).hexdigest()[:32]


def _remaining(deadline: datetime) -> float:
    return (deadline - datetime.now(UTC)).total_seconds()


def _cursor_watermark(cursor: OpaqueCursor | None) -> datetime | None:
    if cursor is None:
        return None
    parts = cursor.value.split("|", 2)
    if len(parts) != 3 or parts[0] != "teams.v1":
        raise TeamsProviderError("MALFORMED_OUTPUT")
    try:
        return datetime.fromisoformat(parts[1]).astimezone(UTC)
    except ValueError as error:
        raise TeamsProviderError("MALFORMED_OUTPUT") from error


def _failure(outcome: SyncOutcome, code: str) -> PullEventsResult:
    return PullEventsResult(events=(), nextCursor=None, sourceBytes=0, outcome=outcome, failureCode=cast(Any, code))


def _credential_failure(code: str) -> PullEventsResult:
    mapping = {
        "CREDENTIAL_INVALID": "ADAPTER_CREDENTIAL_INVALID",
        "CREDENTIAL_UNAUTHORIZED": "ADAPTER_CREDENTIAL_INVALID",
        "CREDENTIAL_MISSING": "ADAPTER_CREDENTIAL_INVALID",
        "CREDENTIAL_EXPIRED": "ADAPTER_CREDENTIAL_INVALID",
    }
    return _failure("unavailable", mapping.get(code, "ADAPTER_UNAVAILABLE"))


def _provider_failure(code: str) -> PullEventsResult:
    outcome = cast(
        SyncOutcome,
        {
            "PERMISSION_DENIED": "unavailable",
            "PROVIDER_NOT_FOUND": "unavailable",
            "RATE_LIMITED": "rate-limited",
            "DEADLINE_EXCEEDED": "deadline-exceeded",
            "MALFORMED_OUTPUT": "malformed-output",
        }.get(code, "unavailable"),
    )
    return _failure(
        outcome,
        {
            "PERMISSION_DENIED": "ADAPTER_PERMISSION_DENIED",
            "PROVIDER_NOT_FOUND": "ADAPTER_PROVIDER_NOT_FOUND",
            "RATE_LIMITED": "ADAPTER_RATE_LIMITED",
            "DEADLINE_EXCEEDED": "ADAPTER_DEADLINE_EXCEEDED",
            "MALFORMED_OUTPUT": "ADAPTER_OUTPUT_INVALID",
        }.get(code, "ADAPTER_UNAVAILABLE"),
    )
