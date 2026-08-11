"""Deterministic bounded JSON/Mock adapter used by the connector kernel."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from projecta_api.connectors.contracts import (
    ActorHint,
    ConnectorDescriptor,
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


class JsonMockResource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    external_reference: str = Field(alias="externalReference", min_length=1, max_length=512)
    occurred_at: datetime = Field(alias="occurredAt")
    event_type: str = Field(alias="eventType", pattern="^source\\.(created|updated)$")
    actor_hint: str | None = Field(default=None, alias="actorHint", max_length=512)
    content_type: str = Field(alias="contentType", pattern="^(application/json|text/plain)$")
    content: object


class JsonMockFixture(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    fixture_version: str = Field(alias="fixtureVersion", pattern="^json-mock\\.v1$")
    connector_type: str = Field(alias="connectorType", pattern="^json-mock$")
    resources: tuple[JsonMockResource, ...] = Field(min_length=0, max_length=100)

    @classmethod
    def from_bytes(cls, payload: bytes) -> JsonMockFixture:
        if len(payload) > 10 * 1024 * 1024:
            raise ValueError("fixture exceeds the run byte limit")

        def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate fixture field")
                result[key] = value
            return result

        def reject_non_finite_number(value: str) -> object:
            raise ValueError(f"non-finite number is not valid JSON: {value}")

        decoded = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_non_finite_number,
        )
        if not isinstance(decoded, Mapping):
            raise ValueError("fixture root must be an object")
        return cls.model_validate(decoded)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


class JsonMockAdapter(ConnectorAdapter):
    """An in-memory fixture adapter; it performs no network or semantic writes."""

    DESCRIPTOR = ConnectorDescriptor(
        connectorType="json-mock",
        displayName="JSON / Mock",
        capabilities=("inbound-import", "resource-fetch", "cancellation"),
    )

    def __init__(self, fixture: JsonMockFixture) -> None:
        self._fixture = fixture
        self.pull_call_count = 0

    def descriptor(self) -> ConnectorDescriptor:
        return self.DESCRIPTOR

    async def validate_installation(
        self, config: InstallationConfig, context: AdapterContext
    ) -> InstallationValidation:
        if context.connector_type != "json-mock":
            return InstallationValidation(outcome="invalid", code="ADAPTER_SCOPE_INVALID")
        if "inbound-import" not in config.declared_capabilities:
            return InstallationValidation(
                outcome="unsupported", code="ADAPTER_CAPABILITY_UNSUPPORTED"
            )
        if not any(
            _belongs_to_fixture(resource.external_reference, config.fixture_reference)
            for resource in self._fixture.resources
        ):
            return InstallationValidation(outcome="invalid", code="ADAPTER_INSTALLATION_INVALID")
        return InstallationValidation(outcome="valid")

    async def pull_events(self, command: PullEventsCommand) -> PullEventsResult:
        self.pull_call_count += 1
        if datetime.now(UTC) >= command.deadline:
            return PullEventsResult(events=(), sourceBytes=0, outcome="deadline-exceeded")
        if command.capability not in self.DESCRIPTOR.capabilities:
            return PullEventsResult(events=(), sourceBytes=0, outcome="unsupported-capability")
        scoped_resources = tuple(
            resource
            for resource in self._fixture.resources
            if _belongs_to_fixture(resource.external_reference, command.fixture_reference)
        )
        start = 0 if command.cursor is None else _cursor_index(command.cursor)
        selected = scoped_resources[start : start + command.max_events]
        events: list[RawEventCandidate] = []
        total = 0
        for index, resource in enumerate(selected, start=start):
            content = resource.content
            content_bytes = (
                content.encode("utf-8") if isinstance(content, str) else _canonical_json(content)
            )
            if total + len(content_bytes) > command.max_bytes:
                break
            actor_hint = (
                ActorHint(sourceSystem="json-mock", externalId=resource.actor_hint)
                if resource.actor_hint
                else None
            )
            events.append(
                RawEventCandidate(
                    eventId=f"evt-{index + 1:03d}",
                    eventType=cast(EventType, resource.event_type),
                    externalReference=resource.external_reference,
                    actorHint=actor_hint,
                    occurredAt=resource.occurred_at,
                    contentType=cast(ContentType, resource.content_type),
                    contentBytes=content_bytes,
                )
            )
            total += len(content_bytes)
        next_index = start + len(events)
        next_cursor = OpaqueCursor(value=str(next_index)) if events else None
        outcome: SyncOutcome = "empty" if not events else "succeeded"
        return PullEventsResult(
            events=tuple(events), nextCursor=next_cursor, sourceBytes=total, outcome=outcome
        )

    async def fetch_resource(
        self, external_reference: str, context: AdapterContext
    ) -> ResourceResult:
        for resource in self._fixture.resources:
            if resource.external_reference == external_reference:
                content_bytes = (
                    resource.content.encode("utf-8")
                    if isinstance(resource.content, str)
                    else _canonical_json(resource.content)
                )
                return ResourceResult(
                    contentType=resource.content_type,
                    contentBytes=content_bytes,
                    contentHash=sha256_digest(content_bytes),
                )
        raise ValueError("ADAPTER_REFERENCE_INVALID")

    async def resolve_identity_hint(
        self, external_reference: str, context: AdapterContext
    ) -> IdentityHintResult:
        for resource in self._fixture.resources:
            if resource.external_reference == external_reference and resource.actor_hint:
                return IdentityHintResult(
                    state="hint", sourceSystem="json-mock", externalId=resource.actor_hint
                )
        return IdentityHintResult(state="none")


def _cursor_index(cursor: OpaqueCursor) -> int:
    try:
        index = int(cursor.value)
    except ValueError as error:
        raise ValueError("ADAPTER_REFERENCE_INVALID") from error
    if index < 0 or index > 100:
        raise ValueError("ADAPTER_LIMIT_EXCEEDED")
    return index


def _belongs_to_fixture(external_reference: str, fixture_reference: str) -> bool:
    prefix = fixture_reference.rstrip("/")
    return external_reference == prefix or external_reference.startswith(prefix + "/")
