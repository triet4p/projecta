"""Server-owned canonical-event validation and deterministic hashing."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from typing import cast

from projecta_api.connectors.contracts import (
    CanonicalEvent,
    EvidenceMetadata,
    RawEventCandidate,
    sha256_digest,
)

_EVIDENCE_REF = re.compile(r"^ev_[A-Za-z0-9_-]{22}$")
_MAX_ENVELOPE_BYTES = 64 * 1024
_MAX_STRING = 16 * 1024
_MAX_FIELDS = 128
_MAX_DEPTH = 16


class CanonicalEventValidationError(ValueError):
    """Finite validation problem with no raw payload in its message."""

    def __init__(self, code: str, field: str | None = None) -> None:
        self.code = code
        self.field = field
        super().__init__(code)


def validate_and_canonicalize(
    candidate: RawEventCandidate,
    *,
    project_id: str,
    installation_id: str,
    connector_type: str,
    evidence_reference: str,
    now: datetime | None = None,
    max_age: timedelta = timedelta(days=365),
    max_future_skew: timedelta = timedelta(minutes=15),
) -> CanonicalEvent:
    """Bind adapter output to server scope and recompute both contract hashes."""
    if connector_type != "json-mock" or candidate.event_id == "":
        raise CanonicalEventValidationError("EVENT_FIELD_INVALID", "connectorType")
    if candidate.external_reference.startswith(("/", "\\")) or ".." in candidate.external_reference:
        raise CanonicalEventValidationError("EVENT_REFERENCE_INVALID", "externalReference")
    if any(ord(character) < 32 for character in candidate.external_reference):
        raise CanonicalEventValidationError("EVENT_FIELD_INVALID", "externalReference")
    if not _EVIDENCE_REF.fullmatch(evidence_reference):
        raise CanonicalEventValidationError("EVENT_REFERENCE_INVALID", "contentRef")
    observed = now.astimezone(UTC) if now is not None else datetime.now(UTC)
    occurred_at = candidate.occurred_at.astimezone(UTC)
    if occurred_at < observed - max_age or occurred_at > observed + max_future_skew:
        raise CanonicalEventValidationError("EVENT_TIMESTAMP_INVALID", "occurredAt")
    if len(candidate.content_bytes) > 1024 * 1024:
        raise CanonicalEventValidationError("EVENT_LIMIT_EXCEEDED", "contentBytes")
    _validate_content(candidate.content_bytes, candidate.content_type)
    metadata = EvidenceMetadata(
        contentRef=evidence_reference,
        contentHash=sha256_digest(candidate.content_bytes),
        contentType=candidate.content_type,
        byteLength=len(candidate.content_bytes),
    )
    canonical_fields: dict[str, object] = {
        "schemaVersion": "canonical-event.v1",
        "eventId": candidate.event_id,
        "connectorType": connector_type,
        "eventType": candidate.event_type,
        "projectScope": project_id,
        "installationScope": installation_id,
        "externalReference": candidate.external_reference,
        "actorHint": candidate.actor_hint.model_dump(by_alias=True, exclude_none=True)
        if candidate.actor_hint
        else None,
        "occurredAt": occurred_at.isoformat().replace("+00:00", "Z"),
        "content": {
            "contentHash": metadata.content_hash,
            "contentType": metadata.content_type,
            "byteLength": metadata.byte_length,
        },
    }
    canonical_bytes = json.dumps(
        canonical_fields,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    if len(canonical_bytes) > _MAX_ENVELOPE_BYTES:
        raise CanonicalEventValidationError("EVENT_LIMIT_EXCEEDED", "envelope")
    return CanonicalEvent(
        schemaVersion="canonical-event.v1",
        eventId=candidate.event_id,
        connectorType=connector_type,
        eventType=candidate.event_type,
        projectScope=project_id,
        installationScope=installation_id,
        externalReference=candidate.external_reference,
        actorHint=candidate.actor_hint,
        occurredAt=occurred_at,
        content=metadata,
        canonicalBodyHash=f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}",
    )


def canonical_body_bytes(event: CanonicalEvent) -> bytes:
    """Serialize exactly the identity fields used for replay/conflict detection."""
    body: dict[str, object] = {
        "schemaVersion": event.schema_version,
        "eventId": event.event_id,
        "connectorType": event.connector_type,
        "eventType": event.event_type,
        "projectScope": event.project_scope,
        "installationScope": event.installation_scope,
        "externalReference": event.external_reference,
        "actorHint": event.actor_hint.model_dump(by_alias=True, exclude_none=True)
        if event.actor_hint
        else None,
        "occurredAt": event.occurred_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "content": {
            "contentHash": event.content.content_hash,
            "contentType": event.content.content_type,
            "byteLength": event.content.byte_length,
        },
    }
    return json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _validate_content(content: bytes, content_type: str) -> None:
    if content_type == "text/plain":
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise CanonicalEventValidationError("EVENT_CONTENT_INVALID", "content") from error
        if len(text) > _MAX_STRING:
            raise CanonicalEventValidationError("EVENT_LIMIT_EXCEEDED", "content")
        return
    try:
        value = json.loads(
            content.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite_number,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise CanonicalEventValidationError("EVENT_CONTENT_INVALID", "content") from error
    _walk_bounded(value, 0)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate object key")
        result[key] = value
    return result


def _reject_non_finite_number(value: str) -> object:
    raise ValueError(f"non-finite number is not valid JSON: {value}")


def _walk_bounded(value: object, depth: int) -> None:
    if depth > _MAX_DEPTH:
        raise CanonicalEventValidationError("EVENT_LIMIT_EXCEEDED", "content")
    if isinstance(value, dict):
        typed_value = cast(dict[str, object], value)
        if len(typed_value) > _MAX_FIELDS:
            raise CanonicalEventValidationError("EVENT_LIMIT_EXCEEDED", "content")
        for key, child in typed_value.items():
            if len(key) > _MAX_STRING:
                raise CanonicalEventValidationError("EVENT_LIMIT_EXCEEDED", "content")
            _walk_bounded(child, depth + 1)
    elif isinstance(value, list):
        typed_value = cast(list[object], value)
        if len(typed_value) > _MAX_FIELDS:
            raise CanonicalEventValidationError("EVENT_LIMIT_EXCEEDED", "content")
        for child in typed_value:
            _walk_bounded(child, depth + 1)
    elif isinstance(value, str) and len(value) > _MAX_STRING:
        raise CanonicalEventValidationError("EVENT_LIMIT_EXCEEDED", "content")
