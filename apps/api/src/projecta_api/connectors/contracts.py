"""Finite provider-neutral contracts for the connector kernel."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ConnectorType = Literal["json-mock", "teams", "github-public-issues"]
ContentType = Literal["application/json", "text/plain"]
ConnectorCapability = Literal[
    "inbound-import",
    "resource-fetch",
    "identity-hint",
    "cancellation",
]
EventType = Literal["source.created", "source.updated"]
SyncOutcome = Literal[
    "succeeded",
    "empty",
    "replayed",
    "cancelled",
    "deadline-exceeded",
    "invalid-installation",
    "unsupported-capability",
    "malformed-output",
    "unavailable",
    "rate-limited",
    "truncated",
    "failed",
]
TerminalEventOutcome = Literal["accepted", "replayed", "failed", "cancelled"]
ErrorCode = Literal[
    "ADAPTER_UNKNOWN_TYPE",
    "ADAPTER_DUPLICATE_REGISTRATION",
    "ADAPTER_CONTRACT_UNSUPPORTED",
    "ADAPTER_INSTALLATION_INVALID",
    "ADAPTER_CAPABILITY_UNSUPPORTED",
    "ADAPTER_SCOPE_INVALID",
    "ADAPTER_REFERENCE_INVALID",
    "ADAPTER_OUTPUT_INVALID",
    "ADAPTER_LIMIT_EXCEEDED",
    "ADAPTER_CANCELLED",
    "ADAPTER_DEADLINE_EXCEEDED",
    "ADAPTER_UNAVAILABLE",
    "ADAPTER_RATE_LIMITED",
    "ADAPTER_CREDENTIAL_INVALID",
    "ADAPTER_PERMISSION_DENIED",
    "ADAPTER_PROVIDER_NOT_FOUND",
    "ADAPTER_FAILED",
    "EVENT_BODY_CONFLICT",
    "EVENT_IDEMPOTENCY_CONFLICT",
    "EVENT_OUTPUT_INVALID",
    "EVENT_LIMIT_EXCEEDED",
    "CURSOR_COMMIT_CONFLICT",
    "EVIDENCE_WRITE_FAILED",
    "SOURCE_COMMIT_FAILED",
    "SYNC_RETRY_INVALID",
]

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


def _safe_id(value: str) -> str:
    if not _SAFE_ID.fullmatch(value):
        raise ValueError("identifier must be URL-safe and at most 128 characters")
    return value


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return value.astimezone(UTC)


class ConnectorLimits(BaseModel):
    """Server-enforced upper bounds exposed as safe adapter metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    max_events: int = Field(default=100, ge=1, le=100)
    max_run_bytes: int = Field(default=10 * 1024 * 1024, ge=1, le=10 * 1024 * 1024)
    max_event_bytes: int = Field(default=1024 * 1024, ge=1, le=1024 * 1024)
    max_cursor_bytes: int = Field(default=512, ge=1, le=4096)
    deadline_seconds: int = Field(default=30, ge=1, le=300)


class ConnectorDescriptor(BaseModel):
    """Finite catalog entry; it deliberately contains no provider details."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    connector_type: ConnectorType = Field(alias="connectorType")
    contract_version: Literal["connector-contract.v1"] = Field(
        default="connector-contract.v1", alias="contractVersion"
    )
    display_name: str = Field(alias="displayName", min_length=1, max_length=128)
    capabilities: tuple[ConnectorCapability, ...] = Field(min_length=1, max_length=4)
    limits: ConnectorLimits = Field(default_factory=ConnectorLimits)

    @model_validator(mode="after")
    def validate_capabilities(self) -> ConnectorDescriptor:
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ValueError("capabilities must be unique")
        if "inbound-import" not in self.capabilities:
            raise ValueError("descriptor must declare inbound-import")
        return self


class InstallationConfig(BaseModel):
    """Allowlisted installation configuration passed to an adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    fixture_reference: str = Field(alias="fixtureReference", min_length=1, max_length=512)
    declared_capabilities: tuple[ConnectorCapability, ...] = Field(
        alias="declaredCapabilities", min_length=1, max_length=4
    )
    provider_config: dict[str, object] | None = Field(default=None, alias="providerConfig")

    @field_validator("fixture_reference")
    @classmethod
    def validate_reference(cls, value: str) -> str:
        if any(ord(char) < 32 for char in value) or ".." in value:
            raise ValueError("fixture reference is invalid")
        if not value.startswith("fixture://"):
            raise ValueError("fixture reference must use the fixture scheme")
        return value


class InstallationSnapshot(BaseModel):
    """Revision-bound, project-scoped installation state."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    installation_id: str = Field(alias="installationId")
    project_id: str = Field(alias="projectId")
    connector_type: ConnectorType = Field(alias="connectorType")
    capabilities: tuple[ConnectorCapability, ...]
    enabled: bool
    revision: int = Field(ge=1)
    fixture_reference: str = Field(alias="fixtureReference", min_length=1, max_length=512)
    secret_configured: bool = Field(alias="secretConfigured", default=False)

    _validate_installation_id = field_validator("installation_id", "project_id")(_safe_id)


class OpaqueCursor(BaseModel):
    """Opaque source position; the kernel never parses or rewrites it."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    value: str = Field(min_length=1, max_length=512)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        if any(ord(char) < 32 for char in value):
            raise ValueError("cursor contains a control character")
        return value


class ActorHint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source_system: str = Field(alias="sourceSystem", min_length=1, max_length=128)
    external_id: str | None = Field(default=None, alias="externalId", max_length=512)
    display_label: str | None = Field(default=None, alias="displayLabel", max_length=512)

    @field_validator("source_system", "external_id", "display_label")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        if value is not None and any(ord(char) < 32 for char in value):
            raise ValueError("actor hint contains a control character")
        return value


class EvidenceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    content_ref: str = Field(alias="contentRef", min_length=1, max_length=256)
    content_hash: str = Field(alias="contentHash")
    content_type: ContentType = Field(alias="contentType")
    byte_length: int = Field(alias="byteLength", ge=0, le=1024 * 1024)

    @field_validator("content_hash")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("content hash must be a lowercase sha256 digest")
        return value


class CanonicalEvent(BaseModel):
    """Validated event envelope; it contains no domain assertion or raw body."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["canonical-event.v1"] = Field(
        default="canonical-event.v1", alias="schemaVersion"
    )
    event_id: str = Field(alias="eventId")
    connector_type: ConnectorType = Field(alias="connectorType")
    event_type: EventType = Field(alias="eventType")
    project_scope: str = Field(alias="projectScope")
    installation_scope: str = Field(alias="installationScope")
    external_reference: str = Field(alias="externalReference", min_length=1, max_length=512)
    actor_hint: ActorHint | None = Field(default=None, alias="actorHint")
    occurred_at: datetime = Field(alias="occurredAt")
    content: EvidenceMetadata
    canonical_body_hash: str = Field(alias="canonicalBodyHash")

    _validate_event_id = field_validator("event_id", "project_scope", "installation_scope")(
        _safe_id
    )

    @field_validator("external_reference")
    @classmethod
    def validate_external_reference(cls, value: str) -> str:
        if any(ord(char) < 32 for char in value) or ".." in value:
            raise ValueError("external reference is invalid")
        return value

    @field_validator("occurred_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return _utc(value)

    @field_validator("canonical_body_hash")
    @classmethod
    def validate_body_hash(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("canonical body hash must be a lowercase sha256 digest")
        return value


class RawEventCandidate(BaseModel):
    """Adapter output before server-owned scope, evidence, and hashing."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    event_id: str = Field(alias="eventId")
    event_type: EventType = Field(alias="eventType")
    external_reference: str = Field(alias="externalReference", min_length=1, max_length=512)
    actor_hint: ActorHint | None = Field(default=None, alias="actorHint")
    occurred_at: datetime = Field(alias="occurredAt")
    content_type: ContentType = Field(alias="contentType")
    content_bytes: bytes = Field(alias="contentBytes", min_length=1, max_length=1024 * 1024)

    _validate_event_id = field_validator("event_id")(_safe_id)


class PullEventsCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    installation_id: str = Field(alias="installationId")
    project_id: str = Field(alias="projectId")
    fixture_reference: str = Field(alias="fixtureReference", min_length=1, max_length=512)
    cursor: OpaqueCursor | None = None
    max_events: int = Field(default=100, ge=1, le=100)
    max_bytes: int = Field(default=10 * 1024 * 1024, ge=1, le=10 * 1024 * 1024)
    deadline: datetime
    correlation_id: str = Field(alias="correlationId", min_length=1, max_length=128)
    operation_id: str = Field(alias="operationId", min_length=1, max_length=128)
    capability: Literal["inbound-import"]
    installation_revision: int = Field(default=1, alias="installationRevision", ge=1)
    provider_config: dict[str, object] | None = Field(default=None, alias="providerConfig")

    _validate_scope = field_validator("installation_id", "project_id")(_safe_id)

    @field_validator("fixture_reference")
    @classmethod
    def validate_fixture_reference(cls, value: str) -> str:
        if (
            not value.startswith("fixture://")
            or ".." in value
            or any(ord(char) < 32 for char in value)
        ):
            raise ValueError("fixture reference is invalid")
        return value

    @field_validator("deadline")
    @classmethod
    def require_deadline_timezone(cls, value: datetime) -> datetime:
        return _utc(value)


class PullEventsResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    events: tuple[RawEventCandidate, ...] = Field(max_length=100)
    next_cursor: OpaqueCursor | None = Field(default=None, alias="nextCursor")
    source_bytes: int = Field(alias="sourceBytes", ge=0, le=10 * 1024 * 1024)
    outcome: SyncOutcome
    failure_code: ErrorCode | None = Field(default=None, alias="failureCode")


class RetryLineage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    parent_run_id: str = Field(alias="parentRunId")
    parent_revision: int = Field(alias="parentRevision", ge=1)
    attempt_number: int = Field(alias="attemptNumber", ge=2, le=2)

    _validate_parent = field_validator("parent_run_id")(_safe_id)


class SyncCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    project_id: str = Field(alias="projectId")
    installation_id: str = Field(alias="installationId")
    expected_installation_revision: int = Field(alias="expectedInstallationRevision", ge=1)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=16, max_length=128)
    run_id: str = Field(alias="runId")
    deadline: datetime
    capability: Literal["inbound-import"] = "inbound-import"
    retry: RetryLineage | None = None

    _validate_scope = field_validator("project_id", "installation_id", "run_id")(_safe_id)

    @field_validator("deadline")
    @classmethod
    def normalize_deadline(cls, value: datetime) -> datetime:
        return _utc(value)


class SanitizedConnectorError(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    code: ErrorCode
    detail: str = Field(min_length=1, max_length=2000)
    retryable: bool
    correlation_id: str = Field(alias="correlationId", min_length=1, max_length=128)
    occurred_at: datetime = Field(alias="occurredAt")

    @field_validator("detail")
    @classmethod
    def no_sensitive_detail(cls, value: str) -> str:
        lowered = value.lower()
        forbidden = ("traceback", "secret_", "password", "authorization:", "rdf:", "file://")
        if any(token in lowered for token in forbidden):
            raise ValueError("error detail contains forbidden material")
        return value

    @field_validator("occurred_at")
    @classmethod
    def normalize_error_time(cls, value: datetime) -> datetime:
        return _utc(value)


def sha256_digest(content: bytes) -> str:
    """Return the contract's lower-case evidence digest."""
    return f"sha256:{hashlib.sha256(content).hexdigest()}"
