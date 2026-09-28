"""Append-only, raw-content-free authoring cost and correction telemetry."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from projecta_api.configuration.storage import OperationalDatabase
from projecta_api.extraction.correction_burden import CorrectionBurdenEventRecord
from projecta_api.extraction.review_receipts import ReviewDecisionReceiptRecord

AUTHORING_COST_CONTRACT_VERSION = "authoring-cost.v1"
WorkflowKind = Literal["entity", "relation"]
ModelUsage = Literal["none", "local-attempted"]
CorrectionCategory = Literal["unchanged", "minor", "major"]
CorrectionDimension = Literal[
    "span", "type", "label", "predicate", "endpoint", "evidence"
]
MAX_REVIEW_LATENCY_MS = 31_536_000_000


class CorrectionCategoryCounts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    unchanged: int = Field(ge=0)
    minor: int = Field(ge=0)
    major: int = Field(ge=0)


class WorkflowCostRecord(BaseModel):
    """User-scoped cost and correction counters for one opaque workflow digest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    workflow_digest: str = Field(alias="workflowDigest", pattern=r"^sha256:[0-9a-f]{64}$")
    workflow_kind: WorkflowKind = Field(alias="workflowKind")
    workflow_mode: Literal["manual", "local", "mixed"] = Field(alias="workflowMode")
    model_usage: ModelUsage = Field(alias="modelUsage")
    local_request_count: int = Field(alias="localRequestCount", ge=0)
    local_inference_attempts: int = Field(alias="localInferenceAttempts", ge=0)
    zero_model: bool = Field(alias="zeroModel")
    review_receipt_count: int = Field(alias="reviewReceiptCount", ge=0)
    correction_event_count: int = Field(alias="correctionEventCount", ge=0)
    semantic_edit_count: int = Field(alias="semanticEditCount", ge=0)
    review_latency_ms: int | None = Field(alias="reviewLatencyMs", ge=0)
    review_latency_sample_count: int = Field(alias="reviewLatencySampleCount", ge=0)
    correction_categories: CorrectionCategoryCounts = Field(alias="correctionCategories")


class AcceptedAssertionCostRecord(BaseModel):
    """Cost attribution for one receipt-backed accepted materialization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    assertion_digest: str = Field(alias="assertionDigest", pattern=r"^sha256:[0-9a-f]{64}$")
    review_receipt_digest: str = Field(alias="reviewReceiptDigest", pattern=r"^sha256:[0-9a-f]{64}$")
    workflow_digest: str | None = Field(
        default=None, alias="workflowDigest", pattern=r"^sha256:[0-9a-f]{64}$"
    )
    cost_known: bool = Field(alias="costKnown")
    local_inference_attempts: int | None = Field(
        default=None, alias="localInferenceAttempts", ge=0
    )
    semantic_edit_count: int | None = Field(default=None, alias="semanticEditCount", ge=0)
    review_latency_ms: int | None = Field(default=None, alias="reviewLatencyMs", ge=0)


class AuthoringCostMetrics(BaseModel):
    """Derived metrics for the trusted user's workflows in one project."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["authoring-cost.v1"] = Field(alias="contractVersion")
    cost_basis: Literal["local-inference-attempt"] = Field(alias="costBasis")
    project_digest: str = Field(alias="projectDigest", pattern=r"^sha256:[0-9a-f]{64}$")
    actor_digest: str = Field(alias="actorDigest", pattern=r"^sha256:[0-9a-f]{64}$")
    workflow_count: int = Field(alias="workflowCount", ge=0)
    manual_workflow_count: int = Field(alias="manualWorkflowCount", ge=0)
    local_request_count: int = Field(alias="localRequestCount", ge=0)
    local_attempted_workflow_count: int = Field(alias="localAttemptedWorkflowCount", ge=0)
    zero_model_workflow_count: int = Field(alias="zeroModelWorkflowCount", ge=0)
    local_inference_attempt_count: int = Field(alias="localInferenceAttemptCount", ge=0)
    review_receipt_count: int = Field(alias="reviewReceiptCount", ge=0)
    correction_event_count: int = Field(alias="correctionEventCount", ge=0)
    semantic_edit_count: int = Field(alias="semanticEditCount", ge=0)
    review_latency_ms_total: int = Field(alias="reviewLatencyMsTotal", ge=0)
    review_latency_sample_count: int = Field(alias="reviewLatencySampleCount", ge=0)
    correction_categories: CorrectionCategoryCounts = Field(alias="correctionCategories")
    accepted_assertion_count: int = Field(alias="acceptedAssertionCount", ge=0)
    cost_known_accepted_assertion_count: int = Field(
        alias="costKnownAcceptedAssertionCount", ge=0
    )
    mean_local_inference_attempts_per_accepted_assertion: float | None = Field(
        default=None, alias="meanLocalInferenceAttemptsPerAcceptedAssertion", ge=0
    )
    workflows: tuple[WorkflowCostRecord, ...] = Field(default=(), max_length=10_000)
    accepted_assertions: tuple[AcceptedAssertionCostRecord, ...] = Field(
        default=(), alias="acceptedAssertions", max_length=10_000
    )


class AuthoringTelemetryRepository:
    """Append and reduce only digests, finite values, counts, and bounded timing."""

    def __init__(self, database: OperationalDatabase) -> None:
        self._database = database

    def record_manual_workflow(
        self,
        project_id: str,
        actor_id: str,
        workflow_id: str,
        workflow_kind: WorkflowKind,
        *,
        now: datetime,
    ) -> None:
        with self._database.transaction() as connection:
            self.append_manual_workflow(
                connection, project_id, actor_id, workflow_id, workflow_kind, now=now
            )

    def append_manual_workflow(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        actor_id: str,
        workflow_id: str,
        workflow_kind: WorkflowKind,
        *,
        now: datetime,
    ) -> None:
        project_digest, actor_digest, workflow_digest = _scope_digests(
            project_id, actor_id, workflow_id
        )
        _append_event(
            connection,
            event_type="manual_workflow",
            project_digest=project_digest,
            actor_digest=actor_digest,
            workflow_digest=workflow_digest,
            workflow_kind=workflow_kind,
            event_key=workflow_digest,
            occurred_at=now,
        )

    def append_local_request(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        actor_id: str,
        workflow_id: str,
        workflow_kind: WorkflowKind,
        idempotency_digest: str,
        request_digest: str,
        *,
        now: datetime,
    ) -> None:
        project_digest, actor_digest, workflow_digest = _scope_digests(
            project_id, actor_id, workflow_id
        )
        _append_event(
            connection,
            event_type="local_request",
            project_digest=project_digest,
            actor_digest=actor_digest,
            workflow_digest=workflow_digest,
            workflow_kind=workflow_kind,
            event_key=_digest(f"{idempotency_digest}\0{request_digest}"),
            occurred_at=now,
        )

    def record_local_attempt(
        self,
        project_id: str,
        actor_id: str,
        workflow_id: str,
        workflow_kind: WorkflowKind,
        attempt_digest: str,
        *,
        now: datetime,
    ) -> None:
        project_digest, actor_digest, workflow_digest = _scope_digests(
            project_id, actor_id, workflow_id
        )
        with self._database.transaction() as connection:
            _append_event(
                connection,
                event_type="local_attempt",
                project_digest=project_digest,
                actor_digest=actor_digest,
                workflow_digest=workflow_digest,
                workflow_kind=workflow_kind,
                attempt_digest=_digest(attempt_digest),
                local_inference_units=1,
                event_key=_digest(attempt_digest),
                occurred_at=now,
            )

    def append_review(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        actor_id: str,
        workflow_id: str,
        workflow_kind: WorkflowKind,
        receipt: ReviewDecisionReceiptRecord,
        *,
        correction_dimensions: Sequence[CorrectionDimension] = (),
        semantic_edit_count: int = 0,
        review_latency_ms: int | None = None,
        now: datetime | None = None,
    ) -> None:
        project_digest, actor_digest, workflow_digest = _scope_digests(
            project_id, actor_id, workflow_id
        )
        if receipt.project_digest != project_digest or receipt.actor_digest != actor_digest:
            raise ValueError("review receipt scope does not match authoring workflow")
        if review_latency_ms is not None and review_latency_ms < 0:
            raise ValueError("review latency cannot be negative")
        if semantic_edit_count < 0:
            raise ValueError("semantic edit count cannot be negative")
        _append_dimensions(correction_dimensions)
        category = _correction_category(correction_dimensions, receipt.decision)
        _append_event(
            connection,
            event_type="review",
            project_digest=project_digest,
            actor_digest=actor_digest,
            workflow_digest=workflow_digest,
            workflow_kind=workflow_kind,
            receipt_digest=receipt.receipt_digest,
            decision=receipt.decision,
            correction_category=category,
            correction_dimensions=tuple(correction_dimensions),
            semantic_edit_count=semantic_edit_count,
            review_latency_ms=review_latency_ms,
            event_key=receipt.receipt_digest,
            occurred_at=receipt.occurred_at if now is None else now,
        )

    def record_review(
        self,
        project_id: str,
        actor_id: str,
        workflow_id: str,
        workflow_kind: WorkflowKind,
        receipt: ReviewDecisionReceiptRecord,
        *,
        correction_dimensions: Sequence[CorrectionDimension] = (),
        semantic_edit_count: int = 0,
        review_latency_ms: int | None = None,
        now: datetime | None = None,
    ) -> None:
        with self._database.transaction() as connection:
            self.append_review(
                connection,
                project_id,
                actor_id,
                workflow_id,
                workflow_kind,
                receipt,
                correction_dimensions=correction_dimensions,
                semantic_edit_count=semantic_edit_count,
                review_latency_ms=review_latency_ms,
                now=now,
            )

    def record_manual_review(
        self,
        project_id: str,
        actor_id: str,
        workflow_id: str,
        workflow_kind: WorkflowKind,
        receipt: ReviewDecisionReceiptRecord,
        *,
        now: datetime,
    ) -> None:
        with self._database.transaction() as connection:
            self.append_manual_workflow(
                connection, project_id, actor_id, workflow_id, workflow_kind, now=now
            )
            self.append_review(
                connection, project_id, actor_id, workflow_id, workflow_kind, receipt
            )


    def record_manual_edit(
        self,
        project_id: str,
        actor_id: str,
        workflow_id: str,
        workflow_kind: WorkflowKind,
        edit_id: str,
        dimensions: Sequence[CorrectionDimension],
        semantic_edit_count: int,
        unclassified: bool,
        *,
        now: datetime,
    ) -> None:
        project_digest, actor_digest, workflow_digest = _scope_digests(
            project_id, actor_id, workflow_id
        )
        _append_dimensions(dimensions)
        if semantic_edit_count < 0:
            raise ValueError("semantic edit count cannot be negative")
        with self._database.transaction() as connection:
            _append_event(
                connection,
                event_type="manual_edit",
                project_digest=project_digest,
                actor_digest=actor_digest,
                workflow_digest=workflow_digest,
                workflow_kind=workflow_kind,
                event_key=_digest(edit_id),
                correction_category=(
                    None if unclassified else _correction_category(dimensions, "edit")
                ),
                correction_dimensions=tuple(dimensions),
                semantic_edit_count=semantic_edit_count,
                occurred_at=now,
            )


    def record_accepted_assertion(
        self,
        project_id: str,
        actor_id: str,
        event: CorrectionBurdenEventRecord,
    ) -> None:
        if event.project_digest != _digest(project_id):
            raise ValueError("accepted assertion event does not match project")
        if event.materialization_state != "accepted":
            return
        project_digest = _digest(project_id)
        materializer_digest = _digest(actor_id)
        with self._database.transaction() as connection:
            receipt = connection.execute(
                """SELECT actor_digest, workflow_digest, workflow_kind, decision
                   FROM authoring_cost_events
                   WHERE project_digest = ? AND receipt_digest = ? AND event_type = 'review'
                   ORDER BY occurred_at, event_id LIMIT 1""",
                (project_digest, event.review_receipt_digest),
            ).fetchone()
            if receipt is not None and receipt["decision"] != "confirm":
                raise ValueError("accepted assertion is not bound to a confirm receipt")
            actor_digest = str(receipt["actor_digest"]) if receipt is not None else materializer_digest
            workflow_digest = str(receipt["workflow_digest"]) if receipt is not None else None
            workflow_kind = (
                cast(WorkflowKind, str(receipt["workflow_kind"]))
                if receipt is not None
                else event.item_kind
            )
            _append_event(
                connection,
                event_type="accepted_assertion",
                project_digest=project_digest,
                actor_digest=actor_digest,
                workflow_digest=workflow_digest,
                workflow_kind=workflow_kind,
                receipt_digest=event.review_receipt_digest,
                assertion_digest=event.assertion_digest,
                event_key=event.review_receipt_digest + "\0" + event.assertion_digest,
                occurred_at=event.occurred_at,
            )

    def summary(self, project_id: str, actor_id: str) -> AuthoringCostMetrics:
        project_digest = _digest(project_id)
        actor_digest = _digest(actor_id)
        with self._database.transaction() as connection:
            rows = connection.execute(
                """SELECT * FROM authoring_cost_events
                   WHERE project_digest = ? AND actor_digest = ?
                   ORDER BY occurred_at, event_id""",
                (project_digest, actor_digest),
            ).fetchall()
        return _summarize(project_digest, actor_digest, rows)


class AuthoringTelemetryService:
    def __init__(self, repository: AuthoringTelemetryRepository) -> None:
        self._repository = repository

    def record_local_attempt(
        self,
        project_id: str,
        actor_id: str,
        workflow_id: str,
        workflow_kind: WorkflowKind,
        attempt_digest: str,
        *,
        now: datetime,
    ) -> None:
        self._repository.record_local_attempt(
            project_id, actor_id, workflow_id, workflow_kind, attempt_digest, now=now
        )

    def summary(self, project_id: str, actor_id: str) -> AuthoringCostMetrics:
        return self._repository.summary(project_id, actor_id)

    def record_manual_review(
        self,
        project_id: str,
        actor_id: str,
        workflow_id: str,
        workflow_kind: WorkflowKind,
        receipt: ReviewDecisionReceiptRecord,
    ) -> None:
        self._repository.record_manual_review(
            project_id, actor_id, workflow_id, workflow_kind, receipt, now=receipt.occurred_at
        )

    def record_manual_edit(
        self,
        project_id: str,
        actor_id: str,
        workflow_id: str,
        workflow_kind: WorkflowKind,
        edit_id: str,
        dimensions: Sequence[CorrectionDimension],
        semantic_edit_count: int,
        unclassified: bool,
        *,
        now: datetime,
    ) -> None:
        self._repository.record_manual_edit(
            project_id,
            actor_id,
            workflow_id,
            workflow_kind,
            edit_id,
            dimensions,
            semantic_edit_count,
            unclassified,
            now=now,
        )

    def record_review(
        self,
        project_id: str,
        actor_id: str,
        workflow_id: str,
        workflow_kind: WorkflowKind,
        receipt: ReviewDecisionReceiptRecord,
        *,
        correction_dimensions: Sequence[CorrectionDimension] = (),
        semantic_edit_count: int = 0,
        review_latency_ms: int | None = None,
    ) -> None:
        self._repository.record_review(
            project_id,
            actor_id,
            workflow_id,
            workflow_kind,
            receipt,
            correction_dimensions=correction_dimensions,
            semantic_edit_count=semantic_edit_count,
            review_latency_ms=review_latency_ms,
        )

    def record_accepted_assertion(
        self, project_id: str, actor_id: str, event: CorrectionBurdenEventRecord
    ) -> None:
        self._repository.record_accepted_assertion(project_id, actor_id, event)


def _summarize(
    project_digest: str, actor_digest: str, rows: Sequence[sqlite3.Row]
) -> AuthoringCostMetrics:
    grouped: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        workflow_digest = row["workflow_digest"]
        if isinstance(workflow_digest, str):
            grouped[workflow_digest].append(row)

    workflow_records: list[WorkflowCostRecord] = []
    for workflow_digest, events in sorted(grouped.items()):
        kinds = {str(row["workflow_kind"]) for row in events}
        if len(kinds) != 1:
            raise ValueError("workflow kind changed within one telemetry scope")
        event_types = {str(row["event_type"]) for row in events}
        attempts = sum(
            int(row["local_inference_units"])
            for row in events
            if row["event_type"] == "local_attempt"
        )
        requests = sum(1 for row in events if row["event_type"] == "local_request")
        manual = "manual_workflow" in event_types
        local = requests > 0 or attempts > 0
        reviews = [row for row in events if row["event_type"] == "review"]
        correction_rows = [
            row
            for row in events
            if row["event_type"] == "manual_edit"
            or row["event_type"] == "review"
            and row["correction_category"] is not None
        ]
        categories = _category_counts(correction_rows)
        latencies = [
            int(row["review_latency_ms"])
            for row in reviews
            if row["review_latency_ms"] is not None
        ]
        workflow_records.append(
            WorkflowCostRecord(
                workflowDigest=workflow_digest,
                workflowKind=next(iter(kinds)),
                workflowMode="mixed" if manual and local else "local" if local else "manual",
                modelUsage="local-attempted" if attempts else "none",
                localRequestCount=requests,
                localInferenceAttempts=attempts,
                zeroModel=attempts == 0,
                reviewReceiptCount=len(reviews),
                correctionEventCount=len(correction_rows),
                semanticEditCount=sum(int(row["semantic_edit_count"]) for row in correction_rows),
                reviewLatencyMs=sum(latencies) if latencies else None,
                reviewLatencySampleCount=len(latencies),
                correctionCategories=categories,
            )
        )

    accepted_rows = [row for row in rows if row["event_type"] == "accepted_assertion"]
    workflow_by_digest = {record.workflow_digest: record for record in workflow_records}
    accepted_records: list[AcceptedAssertionCostRecord] = []
    for row in accepted_rows:
        workflow_digest = row["workflow_digest"]
        workflow = workflow_by_digest.get(str(workflow_digest)) if workflow_digest else None
        accepted_records.append(
            AcceptedAssertionCostRecord(
                assertionDigest=str(row["assertion_digest"]),
                reviewReceiptDigest=str(row["receipt_digest"]),
                workflowDigest=str(workflow_digest) if workflow_digest else None,
                costKnown=workflow is not None,
                localInferenceAttempts=(workflow.local_inference_attempts if workflow is not None else None),
                semanticEditCount=(workflow.semantic_edit_count if workflow is not None else None),
                reviewLatencyMs=(workflow.review_latency_ms if workflow is not None else None),
            )
        )
    accepted_records.sort(key=lambda item: (item.assertion_digest, item.review_receipt_digest))

    correction_rows = [
        row
        for row in rows
        if row["event_type"] == "manual_edit"
        or row["event_type"] == "review"
        and row["correction_category"] is not None
    ]
    categories = _category_counts(correction_rows)
    latency_rows = [
        int(row["review_latency_ms"])
        for row in rows
        if row["event_type"] == "review" and row["review_latency_ms"] is not None
    ]
    total_attempts = sum(record.local_inference_attempts for record in workflow_records)
    known_accepted = [record for record in accepted_records if record.cost_known]
    mean_cost = (
        sum(record.local_inference_attempts or 0 for record in known_accepted) / len(known_accepted)
        if known_accepted
        else None
    )
    return AuthoringCostMetrics(
        contractVersion=AUTHORING_COST_CONTRACT_VERSION,
        costBasis="local-inference-attempt",
        projectDigest=project_digest,
        actorDigest=actor_digest,
        workflowCount=len(workflow_records),
        manualWorkflowCount=sum(1 for events in grouped.values() if any(row["event_type"] == "manual_workflow" for row in events)),
        localRequestCount=sum(1 for row in rows if row["event_type"] == "local_request"),
        localAttemptedWorkflowCount=sum(1 for record in workflow_records if record.local_inference_attempts > 0),
        zeroModelWorkflowCount=sum(1 for record in workflow_records if record.zero_model),
        localInferenceAttemptCount=total_attempts,
        reviewReceiptCount=sum(1 for row in rows if row["event_type"] == "review"),
        correctionEventCount=len(correction_rows),
        semanticEditCount=sum(int(row["semantic_edit_count"]) for row in correction_rows),
        reviewLatencyMsTotal=sum(latency_rows),
        reviewLatencySampleCount=len(latency_rows),
        correctionCategories=categories,
        acceptedAssertionCount=len(accepted_records),
        costKnownAcceptedAssertionCount=len(known_accepted),
        meanLocalInferenceAttemptsPerAcceptedAssertion=mean_cost,
        workflows=tuple(workflow_records),
        acceptedAssertions=tuple(accepted_records),
    )


def _category_counts(rows: Sequence[sqlite3.Row]) -> CorrectionCategoryCounts:
    counts: Counter[str] = Counter(
        str(row["correction_category"])
        for row in rows
        if row["correction_category"] is not None
    )
    return CorrectionCategoryCounts(
        unchanged=counts["unchanged"], minor=counts["minor"], major=counts["major"]
    )


def _correction_category(
    dimensions: Sequence[CorrectionDimension],
    decision: Literal["confirm", "edit", "reject", "abstain"],
) -> CorrectionCategory | None:
    dimension_set = set(dimensions)
    if dimension_set & {"type", "predicate", "endpoint", "evidence"}:
        return "major"
    if dimension_set & {"span", "label"}:
        return "minor"
    if decision in {"confirm", "edit"}:
        return "unchanged"
    return None


def _append_dimensions(dimensions: Sequence[CorrectionDimension]) -> None:
    allowed = {"span", "type", "label", "predicate", "endpoint", "evidence"}
    if len(dimensions) != len(set(dimensions)) or not set(dimensions) <= allowed:
        raise ValueError("correction dimensions must be unique and allowlisted")


def _append_event(
    connection: sqlite3.Connection,
    *,
    event_type: Literal[
        "manual_workflow", "local_request", "local_attempt", "manual_edit",
        "review", "accepted_assertion"
    ],
    project_digest: str,
    actor_digest: str,
    workflow_digest: str | None,
    workflow_kind: WorkflowKind,
    event_key: str,
    occurred_at: datetime,
    attempt_digest: str | None = None,
    receipt_digest: str | None = None,
    assertion_digest: str | None = None,
    decision: Literal["confirm", "edit", "reject", "abstain"] | None = None,
    local_inference_units: int = 0,
    correction_category: CorrectionCategory | None = None,
    correction_dimensions: Sequence[CorrectionDimension] = (),
    semantic_edit_count: int = 0,
    review_latency_ms: int | None = None,
) -> None:
    _append_dimensions(correction_dimensions)
    if local_inference_units < 0 or semantic_edit_count < 0:
        raise ValueError("telemetry counts cannot be negative")
    if review_latency_ms is not None and not 0 <= review_latency_ms <= MAX_REVIEW_LATENCY_MS:
        raise ValueError("review latency must be within the one-year telemetry bound")
    event_id = _event_id(event_type, project_digest, actor_digest, workflow_digest, event_key)
    safe_values: tuple[object, ...] = (
        event_id,
        project_digest,
        actor_digest,
        workflow_digest,
        workflow_kind,
        event_type,
        attempt_digest,
        receipt_digest,
        assertion_digest,
        decision,
        local_inference_units,
        correction_category,
        json.dumps(list(correction_dimensions), separators=(",", ":")),
        semantic_edit_count,
        review_latency_ms,
        _timestamp(occurred_at),
    )
    connection.execute(
        """INSERT OR IGNORE INTO authoring_cost_events(
               event_id, project_digest, actor_digest, workflow_digest, workflow_kind,
               event_type, attempt_digest, receipt_digest, assertion_digest, decision,
               local_inference_units, correction_category, correction_dimensions,
               semantic_edit_count, review_latency_ms, occurred_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        safe_values,
    )
    stored = connection.execute(
        "SELECT * FROM authoring_cost_events WHERE event_id = ?", (event_id,)
    ).fetchone()
    if stored is None:
        raise RuntimeError("authoring telemetry event was not persisted")
    stored_values = tuple(stored[name] for name in (
        "event_id", "project_digest", "actor_digest", "workflow_digest", "workflow_kind",
        "event_type", "attempt_digest", "receipt_digest", "assertion_digest", "decision",
        "local_inference_units", "correction_category", "correction_dimensions",
        "semantic_edit_count", "review_latency_ms", "occurred_at",
    ))
    if stored_values != safe_values:
        if (
            event_type in {"manual_workflow", "local_request"}
            and stored_values[:-1] == safe_values[:-1]
        ):
            return
        raise ValueError("authoring telemetry event conflicts with its idempotency key")


def _scope_digests(project_id: str, actor_id: str, workflow_id: str) -> tuple[str, str, str]:
    return _digest(project_id), _digest(actor_id), _digest(workflow_id)


def _event_id(
    event_type: str,
    project_digest: str,
    actor_digest: str,
    workflow_digest: str | None,
    event_key: str,
) -> str:
    serialized = "\0".join(
        (event_type, project_digest, actor_digest, workflow_digest or "", event_key)
    )
    return "act1_" + sha256(serialized.encode("utf-8", "strict")).hexdigest()


def _digest(value: str) -> str:
    return "sha256:" + sha256(value.encode("utf-8", "strict")).hexdigest()


def _timestamp(value: datetime) -> str:
    current = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return current.astimezone(UTC).isoformat()
