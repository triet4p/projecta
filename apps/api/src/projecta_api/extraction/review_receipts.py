"""Durable, append-only review decision receipts (RM-61)."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Final, Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from projecta_api.operational.database import ConnectorDatabase
from projecta_api.operational.errors import IdempotencyConflict, RevisionConflict
from projecta_api.operational.schema import ReviewDecisionReceipt

REVIEW_RECEIPT_CONTRACT_VERSION: Final = "review-receipt.v1"

ReviewDecision = Literal["confirm", "edit", "reject", "abstain"]
ReviewItemKind = Literal["entity", "relation"]


class ReviewReceiptError(ValueError):
    """Base class for fail-closed review receipt errors."""


class ReviewAuthorizationError(ReviewReceiptError):
    """Raised when the trusted actor context cannot review the project item."""


class ReviewReceiptStaleError(ReviewReceiptError):
    """Raised when source/candidate optimistic concurrency is stale."""


class ReviewReceiptConflict(ReviewReceiptError):
    """Raised when a receipt conflicts with the append-only history."""


class ReviewActorContext(BaseModel):
    """Trusted authorization context; caller-supplied role claims are rejected."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=128)
    actor_id: str = Field(min_length=1, max_length=256)
    capability: Literal["candidate.review"]
    authorization_revision: str = Field(min_length=1, max_length=256)


class ReviewDecisionRequest(BaseModel):
    """Raw request accepted only at the trusted review boundary."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["review-receipt.v1"] = Field(
        default=REVIEW_RECEIPT_CONTRACT_VERSION, alias="contractVersion"
    )
    project_id: str = Field(alias="projectId", min_length=1, max_length=128)
    item_kind: ReviewItemKind = Field(alias="itemKind")
    item_handle: str = Field(alias="itemHandle", min_length=3, max_length=256)
    candidate_revision: int = Field(alias="candidateRevision", ge=1)
    expected_candidate_revision: int = Field(alias="expectedCandidateRevision", ge=0)
    source_version_id: str = Field(alias="sourceVersionId", pattern=r"^sv_[0-9a-f]{64}$")
    source_version_revision: int = Field(alias="sourceVersionRevision", ge=1)
    constrained_contract_version: str = Field(
        alias="constrainedContractVersion", min_length=1, max_length=64
    )
    evidence_digest: str | None = Field(
        default=None, alias="evidenceDigest", pattern=r"^sha256:[0-9a-f]{64}$"
    )
    previous_decision_digest: str | None = Field(
        default=None, alias="previousDecisionDigest", pattern=r"^sha256:[0-9a-f]{64}$"
    )
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=256)
    decision: ReviewDecision
    decision_payload_digest: str | None = Field(
        default=None, alias="decisionPayloadDigest", pattern=r"^sha256:[0-9a-f]{64}$"
    )

    @model_validator(mode="after")
    def validate_item_handle(self) -> ReviewDecisionRequest:
        if not (self.item_handle.startswith("eh1_") or self.item_handle.startswith("rel_")):
            raise ValueError("itemHandle must be a server-owned opaque handle")
        if self.item_kind == "entity" and not self.item_handle.startswith("eh1_"):
            raise ValueError("entity receipt requires an entity handle")
        if self.item_kind == "relation" and not self.item_handle.startswith("rel_"):
            raise ValueError("relation receipt requires a relation handle")
        if self.candidate_revision not in {
            self.expected_candidate_revision,
            self.expected_candidate_revision + 1,
        }:
            raise ValueError("candidate revision must be current or the next revision")
        if self.decision == "edit" and self.decision_payload_digest is None:
            raise ValueError("edit decisions require a payload digest")
        return self

    def safe_dict(self) -> dict[str, object]:
        """Return deterministic safe data with no raw IDs or idempotency key."""

        return {
            "contractVersion": self.contract_version,
            "projectDigest": _digest(self.project_id),
            "itemKind": self.item_kind,
            "itemHandleDigest": _digest(self.item_handle),
            "candidateRevision": self.candidate_revision,
            "expectedCandidateRevision": self.expected_candidate_revision,
            "sourceVersionDigest": _digest(self.source_version_id),
            "sourceVersionRevision": self.source_version_revision,
            "constrainedContractVersion": self.constrained_contract_version,
            "evidenceDigest": self.evidence_digest,
            "previousDecisionDigest": self.previous_decision_digest,
            "idempotencyDigest": _digest(self.idempotency_key),
            "decision": self.decision,
            "decisionPayloadDigest": self.decision_payload_digest,
        }


class ReviewDecisionReceiptRecord(BaseModel):
    """Raw-content-free receipt returned to callers and telemetry."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["review-receipt.v1"] = Field(alias="contractVersion")
    outcome: Literal["accepted", "replayed"]
    receipt_id: str = Field(alias="receiptId", pattern=r"^rr1_[0-9a-f]{64}$")
    project_digest: str = Field(alias="projectDigest", pattern=r"^sha256:[0-9a-f]{64}$")
    actor_digest: str = Field(alias="actorDigest", pattern=r"^sha256:[0-9a-f]{64}$")
    authorization_digest: str = Field(alias="authorizationDigest", pattern=r"^sha256:[0-9a-f]{64}$")
    item_kind: ReviewItemKind = Field(alias="itemKind")
    item_handle_digest: str = Field(alias="itemHandleDigest", pattern=r"^sha256:[0-9a-f]{64}$")
    decision: ReviewDecision
    candidate_revision: int = Field(alias="candidateRevision", ge=1)
    source_version_digest: str = Field(
        alias="sourceVersionDigest", pattern=r"^sha256:[0-9a-f]{64}$"
    )
    source_version_revision: int = Field(alias="sourceVersionRevision", ge=1)
    constrained_contract_version: str = Field(alias="constrainedContractVersion")
    evidence_digest: str | None = Field(default=None, alias="evidenceDigest")
    previous_decision_digest: str | None = Field(default=None, alias="previousDecisionDigest")
    idempotency_digest: str = Field(alias="idempotencyDigest", pattern=r"^sha256:[0-9a-f]{64}$")
    sequence: int = Field(ge=1)
    occurred_at: datetime = Field(alias="occurredAt")
    receipt_digest: str = Field(alias="receiptDigest", pattern=r"^sha256:[0-9a-f]{64}$")

    def safe_dict(self) -> dict[str, object]:
        return cast(dict[str, object], self.model_dump(mode="json", by_alias=True))


@dataclass(frozen=True, slots=True)
class _ReceiptWrite:
    project_id: str
    actor_digest: str
    authorization_digest: str
    item_kind: ReviewItemKind
    item_handle_digest: str
    decision: ReviewDecision
    candidate_revision: int
    expected_candidate_revision: int
    source_version_digest: str
    source_version_revision: int
    constrained_contract_version: str
    evidence_digest: str | None
    previous_decision_digest: str | None
    idempotency_digest: str
    request_digest: str
    receipt_id: str
    occurred_at: datetime
    receipt_digest: str


@dataclass(frozen=True, slots=True)
class _AppendResult:
    receipt: ReviewDecisionReceiptRecord
    replayed: bool


class ReviewDecisionReceiptRepository(Protocol):
    """Operational persistence port for append-only receipt history."""

    def append(self, write: _ReceiptWrite) -> _AppendResult: ...

    def history(
        self, project_id: str, item_kind: ReviewItemKind, item_handle_digest: str
    ) -> Sequence[ReviewDecisionReceiptRecord]: ...


class ReviewDecisionReceiptService:
    """Authorize and persist explicit reviewer actions without materialization."""

    def __init__(self, repository: ReviewDecisionReceiptRepository) -> None:
        self._repository = repository

    def record(
        self, actor: ReviewActorContext, request: ReviewDecisionRequest
    ) -> ReviewDecisionReceiptRecord:
        if actor.capability != "candidate.review":
            raise ReviewAuthorizationError("review capability is required")
        if actor.project_id != request.project_id or not actor.actor_id.strip():
            raise ReviewAuthorizationError("actor is not authorized for this project")
        request_digest = _digest_bytes(
            _stable_json(
                {
                    "request": request.safe_dict(),
                    "actorDigest": _digest(actor.actor_id),
                    "authorizationDigest": _authorization_digest(actor),
                }
            )
        )
        occurred_at = datetime.now(UTC)
        receipt_digest = _digest_bytes(
            _stable_json(
                {
                    "requestDigest": request_digest,
                    "occurredAt": occurred_at.isoformat(),
                }
            )
        )
        write = _ReceiptWrite(
            project_id=request.project_id,
            actor_digest=_digest(actor.actor_id),
            authorization_digest=_authorization_digest(actor),
            item_kind=request.item_kind,
            item_handle_digest=_digest(request.item_handle),
            decision=request.decision,
            candidate_revision=request.candidate_revision,
            expected_candidate_revision=request.expected_candidate_revision,
            source_version_digest=_digest(request.source_version_id),
            source_version_revision=request.source_version_revision,
            constrained_contract_version=request.constrained_contract_version,
            evidence_digest=request.evidence_digest,
            previous_decision_digest=request.previous_decision_digest,
            idempotency_digest=_digest(request.idempotency_key),
            request_digest=request_digest,
            receipt_id="rr1_" + request_digest.split(":", 1)[1],
            occurred_at=occurred_at,
            receipt_digest=receipt_digest,
        )
        result = self._repository.append(write)
        if result.replayed:
            return result.receipt.model_copy(update={"outcome": "replayed"})
        return result.receipt

    def history(
        self, actor: ReviewActorContext, item_kind: ReviewItemKind, item_handle: str
    ) -> Sequence[ReviewDecisionReceiptRecord]:
        if actor.capability != "candidate.review":
            raise ReviewAuthorizationError("review capability is required")
        return self._repository.history(actor.project_id, item_kind, _digest(item_handle))


class InMemoryReviewDecisionReceiptRepository:
    """Deterministic test adapter mirroring the PostgreSQL append rules."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._rows: dict[str, ReviewDecisionReceiptRecord] = {}
        self._history: dict[tuple[str, ReviewItemKind, str], list[ReviewDecisionReceiptRecord]] = {}

    def append(self, write: _ReceiptWrite) -> _AppendResult:
        with self._lock:
            existing = self._rows.get(f"{write.project_id}:{write.idempotency_digest}")
            if existing is not None:
                if (
                    existing.receipt_digest != write.receipt_digest
                    and existing.outcome != "accepted"
                ):
                    raise IdempotencyConflict("idempotency key belongs to a different request")
                if existing.receipt_digest != write.receipt_digest:
                    # Timestamp differs on an exact retry; compare immutable request identity.
                    if existing.receipt_id != write.receipt_id:
                        raise IdempotencyConflict("idempotency key belongs to a different request")
                return _AppendResult(existing, True)
            key = (write.project_id, write.item_kind, write.item_handle_digest)
            rows = self._history.setdefault(key, [])
            _validate_append(cast(Sequence[ReviewDecisionReceiptRecord], rows), write)
            receipt = _receipt(write, len(rows) + 1, "accepted")
            rows.append(receipt)
            self._rows[f"{write.project_id}:{write.idempotency_digest}"] = receipt
            return _AppendResult(receipt, False)

    def history(
        self, project_id: str, item_kind: ReviewItemKind, item_handle_digest: str
    ) -> Sequence[ReviewDecisionReceiptRecord]:
        with self._lock:
            return tuple(self._history.get((project_id, item_kind, item_handle_digest), ()))


class FileReviewDecisionReceiptRepository:
    """Durable file-backed receipt store for focused restart-durability tests.

    Each accepted receipt is appended as one JSON line (``*.jsonl``) under a
    per-item directory, then fsync'd, so receipts survive process restart
    without a live PostgreSQL instance. The append rules (idempotency replay,
    stale/conflict validation) mirror
    :class:`InMemoryReviewDecisionReceiptRepository` exactly; production
    composition keeps using
    :class:`PostgresReviewDecisionReceiptRepository`.
    """

    def __init__(self, directory: str | Path) -> None:
        self._directory = Path(directory)
        self._lock = RLock()

    def append(self, write: _ReceiptWrite) -> _AppendResult:
        with self._lock:
            rows = list(self.history(write.project_id, write.item_kind, write.item_handle_digest))
            existing = next(
                (
                    row
                    for row in self._all_rows(write.project_id)
                    if row.idempotency_digest == write.idempotency_digest
                ),
                None,
            )
            if existing is not None:
                if existing.receipt_digest != write.receipt_digest:
                    # Timestamp differs on an exact retry; compare immutable request identity.
                    if existing.receipt_id != write.receipt_id:
                        raise IdempotencyConflict("idempotency key belongs to a different request")
                return _AppendResult(existing, True)
            _validate_append(rows, write)
            receipt = _receipt(write, len(rows) + 1, "accepted")
            path = self._item_path(write.project_id, write.item_kind, write.item_handle_digest)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(receipt.model_dump_json(by_alias=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            return _AppendResult(receipt, False)

    def history(
        self, project_id: str, item_kind: ReviewItemKind, item_handle_digest: str
    ) -> Sequence[ReviewDecisionReceiptRecord]:
        with self._lock:
            path = self._item_path(project_id, item_kind, item_handle_digest)
            if not path.is_file():
                return ()
            rows: list[ReviewDecisionReceiptRecord] = []
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rows.append(ReviewDecisionReceiptRecord.model_validate_json(line))
            return tuple(rows)

    def _all_rows(self, project_id: str) -> list[ReviewDecisionReceiptRecord]:
        rows: list[ReviewDecisionReceiptRecord] = []
        project_dir = self._directory / project_id
        if not project_dir.is_dir():
            return rows
        for path in sorted(project_dir.rglob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rows.append(ReviewDecisionReceiptRecord.model_validate_json(line))
        return rows

    def _item_path(
        self, project_id: str, item_kind: ReviewItemKind, item_handle_digest: str
    ) -> Path:
        safe_digest = item_handle_digest.removeprefix("sha256:")
        return self._directory / project_id / item_kind / f"{safe_digest}.jsonl"


class PostgresReviewDecisionReceiptRepository:
    """Persist receipts in the existing connector PostgreSQL operational database."""

    def __init__(self, database: ConnectorDatabase) -> None:
        self._database = database

    def append(self, write: _ReceiptWrite) -> _AppendResult:
        with self._database.connection(operation="append_review_decision_receipt") as connection:
            with Session(bind=connection) as session:
                existing = session.execute(
                    select(ReviewDecisionReceipt).where(
                        ReviewDecisionReceipt.project_id == write.project_id,
                        ReviewDecisionReceipt.idempotency_digest == write.idempotency_digest,
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    if existing.request_digest != write.request_digest:
                        raise IdempotencyConflict("idempotency key belongs to a different request")
                    return _AppendResult(_receipt_from_row(existing, "replayed"), True)
                rows = (
                    session.execute(
                        select(ReviewDecisionReceipt)
                        .where(
                            ReviewDecisionReceipt.project_id == write.project_id,
                            ReviewDecisionReceipt.item_kind == write.item_kind,
                            ReviewDecisionReceipt.item_handle_digest == write.item_handle_digest,
                        )
                        .order_by(ReviewDecisionReceipt.sequence.desc())
                        .with_for_update()
                    )
                    .scalars()
                    .all()
                )
                _validate_append(cast(Sequence[ReviewDecisionReceiptRecord], rows), write)
                sequence = len(rows) + 1
            try:
                connection.execute(
                    insert(ReviewDecisionReceipt).values(
                        receipt_id=write.receipt_id,
                        project_id=write.project_id,
                        actor_digest=write.actor_digest,
                        authorization_digest=write.authorization_digest,
                        item_kind=write.item_kind,
                        item_handle_digest=write.item_handle_digest,
                        decision=write.decision,
                        candidate_revision=write.candidate_revision,
                        source_version_digest=write.source_version_digest,
                        source_version_revision=write.source_version_revision,
                        constrained_contract_version=write.constrained_contract_version,
                        evidence_digest=write.evidence_digest,
                        previous_decision_digest=write.previous_decision_digest,
                        idempotency_digest=write.idempotency_digest,
                        request_digest=write.request_digest,
                        sequence=sequence,
                        occurred_at=write.occurred_at,
                        receipt_digest=write.receipt_digest,
                    )
                )
            except IntegrityError as exc:
                raise RevisionConflict("review receipt append raced with another revision") from exc
            return _AppendResult(_receipt(write, sequence, "accepted"), False)

    def history(
        self, project_id: str, item_kind: ReviewItemKind, item_handle_digest: str
    ) -> Sequence[ReviewDecisionReceiptRecord]:
        with self._database.connection(operation="list_review_decision_receipts") as connection:
            with Session(bind=connection) as session:
                rows = (
                    session.execute(
                        select(ReviewDecisionReceipt)
                        .where(
                            ReviewDecisionReceipt.project_id == project_id,
                            ReviewDecisionReceipt.item_kind == item_kind,
                            ReviewDecisionReceipt.item_handle_digest == item_handle_digest,
                        )
                        .order_by(ReviewDecisionReceipt.sequence.asc())
                    )
                    .scalars()
                    .all()
                )
        return tuple(_receipt_from_row(row, "accepted") for row in rows)


def _validate_append(rows: Sequence[ReviewDecisionReceiptRecord], write: _ReceiptWrite) -> None:
    if not rows:
        if write.expected_candidate_revision != 0 or write.previous_decision_digest is not None:
            raise ReviewReceiptStaleError("initial review receipt has stale predecessor")
        return
    latest = rows[0] if len(rows) == 1 else max(rows, key=lambda row: int(row.sequence))
    if latest.source_version_digest != write.source_version_digest:
        raise ReviewReceiptStaleError("source version is stale")
    if latest.source_version_revision != write.source_version_revision:
        raise ReviewReceiptStaleError("source version revision is stale")
    if latest.candidate_revision != write.expected_candidate_revision:
        raise ReviewReceiptStaleError("candidate revision is stale")
    if latest.receipt_digest != write.previous_decision_digest:
        raise ReviewReceiptConflict("previous decision digest does not continue history")


def _receipt(
    write: _ReceiptWrite, sequence: int, outcome: Literal["accepted", "replayed"]
) -> ReviewDecisionReceiptRecord:
    return ReviewDecisionReceiptRecord(
        contractVersion=REVIEW_RECEIPT_CONTRACT_VERSION,
        outcome=outcome,
        receiptId=write.receipt_id,
        projectDigest=_digest(write.project_id),
        actorDigest=write.actor_digest,
        authorizationDigest=write.authorization_digest,
        itemKind=write.item_kind,
        itemHandleDigest=write.item_handle_digest,
        decision=write.decision,
        candidateRevision=write.candidate_revision,
        sourceVersionDigest=write.source_version_digest,
        sourceVersionRevision=write.source_version_revision,
        constrainedContractVersion=write.constrained_contract_version,
        evidenceDigest=write.evidence_digest,
        previousDecisionDigest=write.previous_decision_digest,
        idempotencyDigest=write.idempotency_digest,
        sequence=sequence,
        occurredAt=write.occurred_at,
        receiptDigest=write.receipt_digest,
    )


def _receipt_from_row(
    row: ReviewDecisionReceipt, outcome: Literal["accepted", "replayed"]
) -> ReviewDecisionReceiptRecord:
    return ReviewDecisionReceiptRecord(
        contractVersion=REVIEW_RECEIPT_CONTRACT_VERSION,
        outcome=outcome,
        receiptId=str(row.receipt_id),
        projectDigest=_digest(str(row.project_id)),
        actorDigest=str(row.actor_digest),
        authorizationDigest=str(row.authorization_digest),
        itemKind=cast(ReviewItemKind, str(row.item_kind)),
        itemHandleDigest=str(row.item_handle_digest),
        decision=cast(ReviewDecision, str(row.decision)),
        candidateRevision=int(row.candidate_revision),
        sourceVersionDigest=str(row.source_version_digest),
        sourceVersionRevision=int(row.source_version_revision),
        constrainedContractVersion=str(row.constrained_contract_version),
        evidenceDigest=row.evidence_digest,
        previousDecisionDigest=row.previous_decision_digest,
        idempotencyDigest=str(row.idempotency_digest),
        sequence=int(row.sequence),
        occurredAt=row.occurred_at,
        receiptDigest=str(row.receipt_digest),
    )


def _authorization_digest(actor: ReviewActorContext) -> str:
    return _digest_bytes(
        _stable_json(
            {
                "actorDigest": _digest(actor.actor_id),
                "capability": actor.capability,
                "authorizationRevision": _digest(actor.authorization_revision),
            }
        )
    )


def _digest(value: str) -> str:
    return _digest_bytes(value.encode("utf-8", "strict"))


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _stable_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8", "strict"
    )
