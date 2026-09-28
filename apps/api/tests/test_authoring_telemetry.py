from __future__ import annotations

import json
import sqlite3
from datetime import timedelta
from typing import cast

import pytest

from projecta_api.configuration.storage import OperationalDatabase
from projecta_api.context import TrustedRequestContext
from projecta_api.extraction.authoring_telemetry import (
    AuthoringTelemetryRepository,
    AuthoringTelemetryService,
)
from projecta_api.extraction.correction_burden import (
    CorrectionBurdenRequest,
    CorrectionBurdenTelemetryService,
    InMemoryCorrectionBurdenRepository,
)
from projecta_api.extraction.local_suggestion_store import LocalSuggestionKey
from projecta_api.extraction.review_receipts import (
    InMemoryReviewDecisionReceiptRepository,
    ReviewActorContext,
    ReviewDecisionReceiptService,
    ReviewDecisionRequest,
)
from projecta_api.extraction.service import ExtractionOrchestrator, ExtractionPersistence

_PROJECT = "private-project-alpha"
_ACTOR = "private-reviewer-alpha"
_SOURCE_VERSION = "sv_" + "b" * 64
_ITEM_HANDLE = "eh1_" + "a" * 64
_DIGEST = "sha256:" + "c" * 64


def _confirm_receipt():
    actor = ReviewActorContext(
        project_id=_PROJECT,
        actor_id=_ACTOR,
        capability="candidate.review",
        authorization_revision="private-membership-revision",
    )
    request = ReviewDecisionRequest.model_validate(
        {
            "projectId": _PROJECT,
            "itemKind": "entity",
            "itemHandle": _ITEM_HANDLE,
            "candidateRevision": 1,
            "expectedCandidateRevision": 0,
            "sourceVersionId": _SOURCE_VERSION,
            "sourceVersionRevision": 1,
            "constrainedContractVersion": "entity-handle.v1",
            "evidenceDigest": None,
            "previousDecisionDigest": None,
            "idempotencyKey": "private-review-idempotency",
            "decision": "confirm",
            "decisionPayloadDigest": None,
        }
    )
    receipt = ReviewDecisionReceiptService(
        InMemoryReviewDecisionReceiptRepository()
    ).record(actor, request)
    key = LocalSuggestionKey(
        project_id=_PROJECT,
        source_version_id=_SOURCE_VERSION,
        source_version_revision=1,
        item_handle=_ITEM_HANDLE,
        item_revision=1,
        evidence_digest=_DIGEST,
    )
    return receipt, key


def test_workflow_metrics_are_scoped_idempotent_and_raw_content_free() -> None:
    database = OperationalDatabase(":memory:")
    repository = AuthoringTelemetryRepository(database)
    receipt, key = _confirm_receipt()
    now = receipt.occurred_at

    repository.record_manual_review(_PROJECT, _ACTOR, key.workflow_id, "entity", receipt, now=now)
    repository.record_local_attempt(
        _PROJECT, _ACTOR, key.workflow_id, "entity", "private-attempt-id", now=now
    )
    repository.record_manual_edit(
        _PROJECT,
        _ACTOR,
        key.workflow_id,
        "entity",
        "private-edit-id",
        ("label", "type"),
        semantic_edit_count=2,
        unclassified=False,
        now=now,
    )
    with database.transaction() as connection:
        repository.append_local_request(
            connection,
            _PROJECT,
            _ACTOR,
            key.workflow_id,
            "entity",
            "private-idempotency-digest",
            "private-request-digest",
            now=now,
        )
        repository.append_local_request(
            connection,
            _PROJECT,
            _ACTOR,
            key.workflow_id,
            "entity",
            "private-idempotency-digest",
            "private-request-digest",
            now=now + timedelta(seconds=1),
        )

    summary = repository.summary(_PROJECT, _ACTOR)
    assert summary.workflow_count == 1
    assert summary.manual_workflow_count == 1
    assert summary.local_request_count == 1
    assert summary.local_inference_attempt_count == 1
    assert summary.zero_model_workflow_count == 0
    assert summary.review_receipt_count == 1
    assert summary.correction_event_count == 2
    assert summary.semantic_edit_count == 2
    assert summary.correction_categories.major == 1
    assert summary.correction_categories.minor == 0
    assert summary.correction_categories.unchanged == 1
    assert summary.accepted_assertion_count == 0
    assert summary.mean_local_inference_attempts_per_accepted_assertion is None
    assert repository.summary(_PROJECT, "another-private-reviewer").workflow_count == 0
    assert repository.summary("another-private-project", _ACTOR).workflow_count == 0

    with database.transaction() as connection:
        rows = connection.execute("SELECT * FROM authoring_cost_events").fetchall()
    safe_rows = json.dumps([dict(row) for row in rows], sort_keys=True)
    for private_value in (
        _PROJECT,
        _ACTOR,
        _SOURCE_VERSION,
        _ITEM_HANDLE,
        "private-attempt-id",
        "private-edit-id",
        "private-request-digest",
    ):
        assert private_value not in safe_rows
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        database.execute("UPDATE authoring_cost_events SET local_inference_units = 0")
    database.close()


def test_only_accepted_materialization_events_create_assertion_cost_records() -> None:
    database = OperationalDatabase(":memory:")
    authoring_repository = AuthoringTelemetryRepository(database)
    authoring_service = AuthoringTelemetryService(authoring_repository)
    receipt, key = _confirm_receipt()
    authoring_repository.record_manual_review(
        _PROJECT, _ACTOR, key.workflow_id, "entity", receipt, now=receipt.occurred_at
    )
    authoring_repository.record_local_attempt(
        _PROJECT, _ACTOR, key.workflow_id, "entity", "private-attempt-id", now=receipt.occurred_at
    )

    assert authoring_repository.summary(_PROJECT, _ACTOR).accepted_assertion_count == 0
    correction_service = CorrectionBurdenTelemetryService(
        InMemoryCorrectionBurdenRepository()
    )
    orchestrator = ExtractionOrchestrator(
        None,
        cast(ExtractionPersistence, object()),
        None,
        correction_burden_service=correction_service,
        authoring_telemetry_service=authoring_service,
    )
    context = TrustedRequestContext(
        project_id=_PROJECT, actor_id=_ACTOR, request_id="private-request-id"
    )
    accepted_request = CorrectionBurdenRequest.model_validate(
        {
            "projectId": _PROJECT,
            "itemKind": "entity",
            "itemId": _ITEM_HANDLE,
            "assertionId": "private-assertion-id",
            "sourceVersionId": _SOURCE_VERSION,
            "sourceVersionRevision": 1,
            "reviewReceiptDigest": receipt.receipt_digest,
            "materializationRevision": _DIGEST,
            "inferenceRevision": None,
            "correctionCategory": "unchanged",
            "correctionDimensions": [],
            "reviewOutcome": "confirmed",
            "semanticEditCount": 0,
            "reviewLatencyMs": 25,
            "materializationState": "accepted",
            "inferenceState": "not-materialized",
            "idempotencyKey": "private-materialization-idempotency",
        }
    )

    event = orchestrator.record_correction_burden(context, accepted_request)
    replay = orchestrator.record_correction_burden(context, accepted_request)
    summary = authoring_repository.summary(_PROJECT, _ACTOR)
    assert event.materialization_state == "accepted"
    assert replay.outcome == "replayed"
    assert summary.accepted_assertion_count == 1
    assert summary.cost_known_accepted_assertion_count == 1
    assert summary.mean_local_inference_attempts_per_accepted_assertion == 1.0
    assert summary.accepted_assertions[0].cost_known is True
    assert summary.accepted_assertions[0].local_inference_attempts == 1
    assert summary.accepted_assertions[0].review_receipt_digest == receipt.receipt_digest
    assert authoring_repository.summary(_PROJECT, "another-private-reviewer").accepted_assertion_count == 0

    with database.transaction() as connection:
        rows = connection.execute("SELECT * FROM authoring_cost_events").fetchall()
    safe_rows = json.dumps([dict(row) for row in rows], sort_keys=True)
    for private_value in (
        _PROJECT,
        _ACTOR,
        _ITEM_HANDLE,
        _SOURCE_VERSION,
        "private-assertion-id",
        "private-request-id",
    ):
        assert private_value not in safe_rows
    database.close()
