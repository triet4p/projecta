"""Append-only, raw-content-free correction-burden telemetry (RM-65)."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import Final, Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from projecta_api.operational.database import ConnectorDatabase
from projecta_api.operational.errors import (
    IdempotencyConflict,
    RevisionConflict,
    TelemetryIntegrityError,
)
from projecta_api.operational.schema import CorrectionBurdenEvent

CORRECTION_BURDEN_CONTRACT_VERSION: Final = "correction-burden.v1"
CorrectionCategory = Literal["unchanged", "minor", "major"]
CorrectionDimension = Literal["span", "type", "label", "predicate", "endpoint", "evidence"]
LifecycleOutcome = Literal[
    "confirmed", "edited", "rejected", "abstained", "quarantined", "stale", "conflict", "replayed"
]
MaterializationState = Literal["accepted", "replayed", "stale", "quarantined", "abstained", "conflict", "not-materialized"]
InferenceState = Literal["current", "stale", "not-materialized"]


class CorrectionBurdenRequest(BaseModel):
    """Strict event input; IDs are hashed before safe serialization or telemetry storage."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["correction-burden.v1"] = Field(
        default=CORRECTION_BURDEN_CONTRACT_VERSION, alias="contractVersion"
    )
    project_id: str = Field(alias="projectId", min_length=1, max_length=128)
    item_kind: Literal["entity", "relation"] = Field(alias="itemKind")
    item_id: str = Field(alias="itemId", min_length=3, max_length=256)
    assertion_id: str = Field(alias="assertionId", min_length=3, max_length=512)
    source_version_id: str = Field(alias="sourceVersionId", pattern=r"^sv_[0-9a-f]{64}$")
    source_version_revision: int = Field(alias="sourceVersionRevision", ge=1)
    review_receipt_digest: str = Field(alias="reviewReceiptDigest", pattern=r"^sha256:[0-9a-f]{64}$")
    materialization_revision: str | None = Field(
        default=None, alias="materializationRevision", pattern=r"^sha256:[0-9a-f]{64}$"
    )
    inference_revision: str | None = Field(
        default=None, alias="inferenceRevision", pattern=r"^sha256:[0-9a-f]{64}$"
    )
    correction_category: CorrectionCategory = Field(alias="correctionCategory")
    correction_dimensions: tuple[CorrectionDimension, ...] = Field(
        default=(), alias="correctionDimensions", max_length=6
    )
    review_outcome: LifecycleOutcome = Field(alias="reviewOutcome")
    semantic_edit_count: int = Field(alias="semanticEditCount", ge=0, le=1_000_000)
    review_latency_ms: int = Field(alias="reviewLatencyMs", ge=0, le=31_536_000_000)
    materialization_state: MaterializationState = Field(alias="materializationState")
    inference_state: InferenceState = Field(alias="inferenceState")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=256)

    @model_validator(mode="after")
    def validate_dimensions(self) -> CorrectionBurdenRequest:
        if len(set(self.correction_dimensions)) != len(self.correction_dimensions):
            raise ValueError("correction dimensions must be unique")
        if self.correction_category == "unchanged" and self.correction_dimensions:
            raise ValueError("unchanged events cannot carry correction dimensions")
        if self.materialization_state == "accepted" and self.materialization_revision is None:
            raise ValueError("accepted materialization requires a revision")
        if self.inference_state == "current" and self.inference_revision is None:
            raise ValueError("current inference requires a revision")
        if "|" in self.idempotency_key:
            raise ValueError("idempotency key contains an unsupported delimiter")
        return self

    def safe_dict(self) -> dict[str, object]:
        return {
            "contractVersion": self.contract_version,
            "projectDigest": _digest(self.project_id),
            "itemKind": self.item_kind,
            "itemDigest": _digest(self.item_id),
            "assertionDigest": _digest(self.assertion_id),
            "sourceVersionDigest": _digest(self.source_version_id),
            "sourceVersionRevision": self.source_version_revision,
            "reviewReceiptDigest": self.review_receipt_digest,
            "materializationRevision": self.materialization_revision,
            "inferenceRevision": self.inference_revision,
            "correctionCategory": self.correction_category,
            "correctionDimensions": list(self.correction_dimensions),
            "reviewOutcome": self.review_outcome,
            "semanticEditCount": self.semantic_edit_count,
            "reviewLatencyMs": self.review_latency_ms,
            "materializationState": self.materialization_state,
            "inferenceState": self.inference_state,
            "idempotencyDigest": _digest(self.idempotency_key),
        }


class CorrectionBurdenEventRecord(BaseModel):
    """Safe event returned by the append boundary; no raw identifiers or payloads."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    contract_version: Literal["correction-burden.v1"] = Field(alias="contractVersion")
    outcome: Literal["accepted", "replayed"]
    event_id: str = Field(alias="eventId", pattern=r"^cbe1_[0-9a-f]{64}$")
    project_digest: str = Field(alias="projectDigest", pattern=r"^sha256:[0-9a-f]{64}$")
    item_kind: Literal["entity", "relation"] = Field(alias="itemKind")
    item_digest: str = Field(alias="itemDigest", pattern=r"^sha256:[0-9a-f]{64}$")
    assertion_digest: str = Field(alias="assertionDigest", pattern=r"^sha256:[0-9a-f]{64}$")
    source_version_digest: str = Field(alias="sourceVersionDigest", pattern=r"^sha256:[0-9a-f]{64}$")
    source_version_revision: int = Field(alias="sourceVersionRevision", ge=1)
    review_receipt_digest: str = Field(alias="reviewReceiptDigest", pattern=r"^sha256:[0-9a-f]{64}$")
    materialization_revision: str | None = Field(
        default=None, alias="materializationRevision", pattern=r"^sha256:[0-9a-f]{64}$"
    )
    inference_revision: str | None = Field(
        default=None, alias="inferenceRevision", pattern=r"^sha256:[0-9a-f]{64}$"
    )
    correction_category: CorrectionCategory = Field(alias="correctionCategory")
    correction_dimensions: tuple[CorrectionDimension, ...] = Field(
        alias="correctionDimensions", max_length=6
    )
    review_outcome: LifecycleOutcome = Field(alias="reviewOutcome")
    semantic_edit_count: int = Field(alias="semanticEditCount", ge=0)
    review_latency_ms: int = Field(alias="reviewLatencyMs", ge=0)
    materialization_state: MaterializationState = Field(alias="materializationState")
    inference_state: InferenceState = Field(alias="inferenceState")
    idempotency_digest: str = Field(alias="idempotencyDigest", pattern=r"^sha256:[0-9a-f]{64}$")
    occurred_at: datetime = Field(alias="occurredAt")
    event_digest: str = Field(alias="eventDigest", pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_lifecycle(self) -> CorrectionBurdenEventRecord:
        if len(set(self.correction_dimensions)) != len(self.correction_dimensions):
            raise ValueError("correction dimensions must be unique")
        if self.correction_category == "unchanged" and self.correction_dimensions:
            raise ValueError("unchanged events cannot carry correction dimensions")
        if self.materialization_state == "accepted" and self.materialization_revision is None:
            raise ValueError("accepted materialization requires a revision")
        if self.inference_state == "current" and self.inference_revision is None:
            raise ValueError("current inference requires a revision")
        return self

    def safe_dict(self) -> dict[str, object]:
        return cast(dict[str, object], self.model_dump(mode="json", by_alias=True))


class CorrectionBurdenSummary(BaseModel):
    """Reducer output derived solely from immutable event rows."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["correction-burden.v1"] = Field(alias="contractVersion")
    project_digest: str = Field(alias="projectDigest", pattern=r"^sha256:[0-9a-f]{64}$")
    event_count: int = Field(alias="eventCount", ge=0)
    accepted_assertion_count: int = Field(alias="acceptedAssertionCount", ge=0)
    semantic_edit_count: int = Field(alias="semanticEditCount", ge=0)
    review_latency_ms: int = Field(alias="reviewLatencyMs", ge=0)
    category_counts: dict[str, int] = Field(alias="categoryCounts")
    outcome_counts: dict[str, int] = Field(alias="outcomeCounts")


@dataclass(frozen=True, slots=True)
class _EventWrite:
    project_id: str
    item_kind: Literal["entity", "relation"]
    item_digest: str
    assertion_digest: str
    source_version_digest: str
    source_version_revision: int
    review_receipt_digest: str
    materialization_revision: str | None
    inference_revision: str | None
    correction_category: CorrectionCategory
    correction_dimensions: tuple[CorrectionDimension, ...]
    review_outcome: LifecycleOutcome
    semantic_edit_count: int
    review_latency_ms: int
    materialization_state: MaterializationState
    inference_state: InferenceState
    idempotency_digest: str
    request_digest: str
    event_id: str
    occurred_at: datetime
    event_digest: str


class CorrectionBurdenRepository(Protocol):
    def append(self, write: _EventWrite) -> CorrectionBurdenEventRecord: ...

    def events(self, project_id: str) -> Sequence[CorrectionBurdenEventRecord]: ...


class CorrectionBurdenTelemetryService:
    """Append telemetry events and reduce summaries without mutable totals."""

    def __init__(self, repository: CorrectionBurdenRepository) -> None:
        self._repository = repository

    def record(self, request: CorrectionBurdenRequest) -> CorrectionBurdenEventRecord:
        request_digest = _digest_bytes(_stable_json(request.safe_dict()).encode("utf-8"))
        occurred_at = datetime.now(UTC)
        event_digest = _event_digest(request_digest, occurred_at)
        write = _EventWrite(
            project_id=request.project_id,
            item_kind=request.item_kind,
            item_digest=_digest(request.item_id),
            assertion_digest=_digest(request.assertion_id),
            source_version_digest=_digest(request.source_version_id),
            source_version_revision=request.source_version_revision,
            review_receipt_digest=request.review_receipt_digest,
            materialization_revision=request.materialization_revision,
            inference_revision=request.inference_revision,
            correction_category=request.correction_category,
            correction_dimensions=request.correction_dimensions,
            review_outcome=request.review_outcome,
            semantic_edit_count=request.semantic_edit_count,
            review_latency_ms=request.review_latency_ms,
            materialization_state=request.materialization_state,
            inference_state=request.inference_state,
            idempotency_digest=_digest(request.idempotency_key),
            request_digest=request_digest,
            event_id="cbe1_" + request_digest.split(":", 1)[1],
            occurred_at=occurred_at,
            event_digest=event_digest,
        )
        return self._repository.append(write)

    def summary(self, project_id: str) -> CorrectionBurdenSummary:
        events = tuple(self._repository.events(project_id))
        return summarize_events(project_id, events)


class InMemoryCorrectionBurdenRepository:
    def __init__(self) -> None:
        self._lock = RLock()
        self._rows: dict[tuple[str, str], CorrectionBurdenEventRecord] = {}
        self._events: dict[str, list[CorrectionBurdenEventRecord]] = {}

    def append(self, write: _EventWrite) -> CorrectionBurdenEventRecord:
        with self._lock:
            key = (write.project_id, write.idempotency_digest)
            existing = self._rows.get(key)
            if existing is not None:
                if existing.event_digest != write.event_digest and existing.event_id != write.event_id:
                    raise IdempotencyConflict("telemetry idempotency key conflicts with event body")
                return existing.model_copy(update={"outcome": "replayed"})
            event = _event(write, "accepted")
            self._rows[key] = event
            self._events.setdefault(write.project_id, []).append(event)
            return event

    def events(self, project_id: str) -> Sequence[CorrectionBurdenEventRecord]:
        with self._lock:
            return tuple(self._events.get(project_id, ()))


class PostgresCorrectionBurdenRepository:
    """Existing PostgreSQL operational boundary for append-only telemetry."""

    def __init__(self, database: ConnectorDatabase) -> None:
        self._database = database

    def append(self, write: _EventWrite) -> CorrectionBurdenEventRecord:
        with self._database.connection(operation="append_correction_burden_event") as connection:
            with Session(bind=connection) as session:
                existing = session.execute(
                    select(CorrectionBurdenEvent).where(
                        CorrectionBurdenEvent.project_id == write.project_id,
                        CorrectionBurdenEvent.idempotency_digest == write.idempotency_digest,
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    existing_record = _event_from_row(existing, "replayed")
                    if existing.request_digest != write.request_digest:
                        raise IdempotencyConflict("telemetry idempotency key conflicts with event body")
                    return existing_record
            try:
                connection.execute(
                    insert(CorrectionBurdenEvent).values(
                        event_id=write.event_id,
                        project_id=write.project_id,
                        item_kind=write.item_kind,
                        item_digest=write.item_digest,
                        assertion_digest=write.assertion_digest,
                        source_version_digest=write.source_version_digest,
                        source_version_revision=write.source_version_revision,
                        review_receipt_digest=write.review_receipt_digest,
                        materialization_revision=write.materialization_revision,
                        inference_revision=write.inference_revision,
                        correction_category=write.correction_category,
                        correction_dimensions=list(write.correction_dimensions),
                        review_outcome=write.review_outcome,
                        semantic_edit_count=write.semantic_edit_count,
                        review_latency_ms=write.review_latency_ms,
                        materialization_state=write.materialization_state,
                        inference_state=write.inference_state,
                        idempotency_digest=write.idempotency_digest,
                        request_digest=write.request_digest,
                        occurred_at=write.occurred_at,
                        event_digest=write.event_digest,
                    )
                )
            except IntegrityError as exc:
                raise RevisionConflict("telemetry append raced with another event") from exc
            return _event(write, "accepted")

    def events(self, project_id: str) -> Sequence[CorrectionBurdenEventRecord]:
        with self._database.connection(operation="list_correction_burden_events") as connection:
            with Session(bind=connection) as session:
                rows = session.execute(
                    select(CorrectionBurdenEvent)
                    .where(CorrectionBurdenEvent.project_id == project_id)
                    .order_by(CorrectionBurdenEvent.occurred_at.asc(), CorrectionBurdenEvent.event_id.asc())
                ).scalars().all()
        return tuple(_event_from_row(row, "accepted") for row in rows)


def summarize_events(
    project_id: str, events: Sequence[CorrectionBurdenEventRecord]
) -> CorrectionBurdenSummary:
    categories: Counter[str] = Counter()
    outcomes: Counter[str] = Counter()
    accepted = 0
    edits = 0
    latency = 0
    for event in events:
        categories[event.correction_category] += 1
        outcomes[event.review_outcome] += 1
        edits += event.semantic_edit_count
        latency += event.review_latency_ms
        if event.materialization_state == "accepted" and event.inference_state in {"current", "stale"}:
            accepted += 1
    return CorrectionBurdenSummary(
        contractVersion=CORRECTION_BURDEN_CONTRACT_VERSION,
        projectDigest=_digest(project_id),
        eventCount=len(events),
        acceptedAssertionCount=accepted,
        semanticEditCount=edits,
        reviewLatencyMs=latency,
        categoryCounts=dict(categories),
        outcomeCounts=dict(outcomes),
    )


def _event(write: _EventWrite, outcome: Literal["accepted", "replayed"]) -> CorrectionBurdenEventRecord:
    return CorrectionBurdenEventRecord(
        contractVersion=CORRECTION_BURDEN_CONTRACT_VERSION,
        outcome=outcome,
        eventId=write.event_id,
        projectDigest=_digest(write.project_id),
        itemKind=write.item_kind,
        itemDigest=write.item_digest,
        assertionDigest=write.assertion_digest,
        sourceVersionDigest=write.source_version_digest,
        sourceVersionRevision=write.source_version_revision,
        reviewReceiptDigest=write.review_receipt_digest,
        materializationRevision=write.materialization_revision,
        inferenceRevision=write.inference_revision,
        correctionCategory=write.correction_category,
        correctionDimensions=write.correction_dimensions,
        reviewOutcome=write.review_outcome,
        semanticEditCount=write.semantic_edit_count,
        reviewLatencyMs=write.review_latency_ms,
        materializationState=write.materialization_state,
        inferenceState=write.inference_state,
        idempotencyDigest=write.idempotency_digest,
        occurredAt=write.occurred_at,
        eventDigest=write.event_digest,
    )


def _event_from_row(row: CorrectionBurdenEvent, outcome: Literal["accepted", "replayed"]) -> CorrectionBurdenEventRecord:
    try:
        project_id = _row_text(row.project_id, "project_id", max_length=128)
        dimensions = row.correction_dimensions
        record = CorrectionBurdenEventRecord.model_validate(
            {
                "contractVersion": CORRECTION_BURDEN_CONTRACT_VERSION,
                "outcome": outcome,
                "eventId": _row_text(row.event_id, "event_id"),
                "projectDigest": _digest(project_id),
                "itemKind": _row_text(row.item_kind, "item_kind"),
                "itemDigest": _row_text(row.item_digest, "item_digest"),
                "assertionDigest": _row_text(row.assertion_digest, "assertion_digest"),
                "sourceVersionDigest": _row_text(row.source_version_digest, "source_version_digest"),
                "sourceVersionRevision": _row_int(row.source_version_revision, "source_version_revision"),
                "reviewReceiptDigest": _row_text(row.review_receipt_digest, "review_receipt_digest"),
                "materializationRevision": _row_optional_text(row.materialization_revision, "materialization_revision"),
                "inferenceRevision": _row_optional_text(row.inference_revision, "inference_revision"),
                "correctionCategory": _row_text(row.correction_category, "correction_category"),
                "correctionDimensions": tuple(dimensions),
                "reviewOutcome": _row_text(row.review_outcome, "review_outcome"),
                "semanticEditCount": _row_int(row.semantic_edit_count, "semantic_edit_count"),
                "reviewLatencyMs": _row_int(row.review_latency_ms, "review_latency_ms"),
                "materializationState": _row_text(row.materialization_state, "materialization_state"),
                "inferenceState": _row_text(row.inference_state, "inference_state"),
                "idempotencyDigest": _row_text(row.idempotency_digest, "idempotency_digest"),
                "occurredAt": row.occurred_at,
                "eventDigest": _row_text(row.event_digest, "event_digest"),
            }
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise TelemetryIntegrityError("correction-burden row failed schema validation") from exc

    request_digest = _request_digest_from_event(project_id, record)
    if _row_text(row.request_digest, "request_digest") != request_digest:
        raise TelemetryIntegrityError("correction-burden request digest mismatch")
    if record.event_id != "cbe1_" + request_digest.split(":", 1)[1]:
        raise TelemetryIntegrityError("correction-burden event identity mismatch")
    if record.event_digest != _event_digest(request_digest, record.occurred_at):
        raise TelemetryIntegrityError("correction-burden event digest mismatch")
    return record


def _request_digest_from_event(project_id: str, event: CorrectionBurdenEventRecord) -> str:
    safe: dict[str, object] = {
        "contractVersion": event.contract_version,
        "projectDigest": _digest(project_id),
        "itemKind": event.item_kind,
        "itemDigest": event.item_digest,
        "assertionDigest": event.assertion_digest,
        "sourceVersionDigest": event.source_version_digest,
        "sourceVersionRevision": event.source_version_revision,
        "reviewReceiptDigest": event.review_receipt_digest,
        "materializationRevision": event.materialization_revision,
        "inferenceRevision": event.inference_revision,
        "correctionCategory": event.correction_category,
        "correctionDimensions": list(event.correction_dimensions),
        "reviewOutcome": event.review_outcome,
        "semanticEditCount": event.semantic_edit_count,
        "reviewLatencyMs": event.review_latency_ms,
        "materializationState": event.materialization_state,
        "inferenceState": event.inference_state,
        "idempotencyDigest": event.idempotency_digest,
    }
    return _digest_bytes(_stable_json(safe).encode("utf-8"))


def _event_digest(request_digest: str, occurred_at: datetime) -> str:
    if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
        raise ValueError("correction event timestamp must be timezone-aware")
    return _digest_bytes(
        _stable_json(
            {
                "requestDigest": request_digest,
                "occurredAt": occurred_at.astimezone(UTC).isoformat(),
            }
        ).encode("utf-8")
    )


def _row_text(value: object, name: str, *, max_length: int | None = None) -> str:
    if not isinstance(value, str) or not value or (max_length is not None and len(value) > max_length):
        raise TypeError(f"{name} must be a bounded non-empty string")
    return value


def _row_optional_text(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _row_text(value, name)


def _row_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    return value


def _stable_json(value: dict[str, object]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: str) -> str:
    return _digest_bytes(value.encode("utf-8"))


def _digest_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"
