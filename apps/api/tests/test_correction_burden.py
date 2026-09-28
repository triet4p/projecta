from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from pydantic import ValidationError

from projecta_api.context import TrustedRequestContext
from projecta_api.extraction.correction_burden import (
    CorrectionBurdenRequest,
    CorrectionBurdenTelemetryService,
    InMemoryCorrectionBurdenRepository,
    _event_from_row,
    _request_digest_from_event,
)
from projecta_api.extraction.review_receipts import (
    InMemoryReviewDecisionReceiptRepository,
    ReviewActorContext,
    ReviewDecisionReceiptService,
    ReviewDecisionRequest,
)
from projecta_api.extraction.service import ExtractionOrchestrator, ExtractionPersistence
from projecta_api.operational.errors import IdempotencyConflict, TelemetryIntegrityError

SOURCE = "sv_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
DIGEST = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
MIGRATION = Path(__file__).parents[1] / "alembic/versions/0010_correction_burden_events.py"


def request(**overrides: object) -> CorrectionBurdenRequest:
    body: dict[str, object] = {
        "projectId": "project-alpha",
        "itemKind": "entity",
        "itemId": "eh1_opaque-candidate",
        "assertionId": "assertion_opaque-1",
        "sourceVersionId": SOURCE,
        "sourceVersionRevision": 3,
        "reviewReceiptDigest": DIGEST,
        "materializationRevision": DIGEST,
        "inferenceRevision": DIGEST,
        "correctionCategory": "minor",
        "correctionDimensions": ["label"],
        "reviewOutcome": "edited",
        "semanticEditCount": 2,
        "reviewLatencyMs": 1200,
        "materializationState": "accepted",
        "inferenceState": "current",
        "idempotencyKey": "telemetry-1",
    }
    body.update(overrides)
    return CorrectionBurdenRequest.model_validate(body)


def test_safe_append_replay_conflict_and_reducer() -> None:
    repository = InMemoryCorrectionBurdenRepository()
    service = CorrectionBurdenTelemetryService(repository)
    accepted = service.record(request())
    replayed = service.record(request())

    assert accepted.outcome == "accepted"
    assert replayed.outcome == "replayed"
    assert accepted.event_id == replayed.event_id
    assert accepted.project_digest != "project-alpha"
    assert "eh1_opaque-candidate" not in str(accepted.safe_dict())
    assert "assertion_opaque-1" not in str(accepted.safe_dict())
    assert service.summary("project-alpha").event_count == 1
    assert service.summary("project-alpha").semantic_edit_count == 2

    with pytest.raises(IdempotencyConflict):
        service.record(request(semanticEditCount=3))


def test_returned_event_is_immutable_and_cannot_change_reducer_output() -> None:
    repository = InMemoryCorrectionBurdenRepository()
    service = CorrectionBurdenTelemetryService(repository)
    accepted = service.record(request())
    before = service.summary("project-alpha")

    with pytest.raises(ValidationError):
        accepted.semantic_edit_count = 999

    assert service.summary("project-alpha") == before


def test_persisted_row_body_tampering_fails_before_summary() -> None:
    repository = InMemoryCorrectionBurdenRepository()
    service = CorrectionBurdenTelemetryService(repository)
    accepted = service.record(request())
    request_digest = _request_digest_from_event("project-alpha", accepted)
    row = SimpleNamespace(
        project_id="project-alpha",
        event_id=accepted.event_id,
        item_kind=accepted.item_kind,
        item_digest=accepted.item_digest,
        assertion_digest=accepted.assertion_digest,
        source_version_digest=accepted.source_version_digest,
        source_version_revision=accepted.source_version_revision,
        review_receipt_digest=accepted.review_receipt_digest,
        materialization_revision=accepted.materialization_revision,
        inference_revision=accepted.inference_revision,
        correction_category=accepted.correction_category,
        correction_dimensions=list(accepted.correction_dimensions),
        review_outcome=accepted.review_outcome,
        semantic_edit_count=999,
        review_latency_ms=accepted.review_latency_ms,
        materialization_state=accepted.materialization_state,
        inference_state=accepted.inference_state,
        idempotency_digest=accepted.idempotency_digest,
        request_digest=request_digest,
        occurred_at=accepted.occurred_at,
        event_digest=accepted.event_digest,
    )

    with pytest.raises(TelemetryIntegrityError):
        _event_from_row(row, "accepted")


def test_migration_enforces_append_only_rows() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "correction_burden_events is append-only" in migration


@pytest.mark.parametrize(
    ("category", "dimensions"),
    [("unchanged", []), ("minor", ["span", "type", "label"]), ("major", ["predicate", "endpoint", "evidence"])],
)
def test_allowlisted_correction_matrix(category: str, dimensions: list[str]) -> None:
    parsed = request(correctionCategory=category, correctionDimensions=dimensions)
    assert parsed.correction_category == category
    assert list(parsed.correction_dimensions) == dimensions


def test_unknown_negative_and_coordinated_reconciliation_inputs_fail_closed() -> None:
    with pytest.raises(ValidationError):
        request(correctionCategory="business-critical")
    with pytest.raises(ValidationError):
        request(semanticEditCount=-1)
    with pytest.raises(ValidationError):
        request(reviewLatencyMs=-1)
    with pytest.raises(ValidationError):
        request(reconciled=True)
    with pytest.raises(ValidationError):
        request(correctionCategory="unchanged", correctionDimensions=["label"])


def test_project_isolation_and_summary_are_event_derived() -> None:
    repository = InMemoryCorrectionBurdenRepository()
    service = CorrectionBurdenTelemetryService(repository)
    service.record(request())
    service.record(request(projectId="project-beta", idempotencyKey="telemetry-beta"))

    alpha = service.summary("project-alpha")
    beta = service.summary("project-beta")
    assert alpha.event_count == 1
    assert beta.event_count == 1
    assert alpha.project_digest != beta.project_digest
    assert alpha.accepted_assertion_count == 1
    assert "reconciled" not in alpha.model_dump()


def test_review_boundary_has_explicit_non_provider_telemetry_hook() -> None:
    telemetry = CorrectionBurdenTelemetryService(InMemoryCorrectionBurdenRepository())
    receipts = ReviewDecisionReceiptService(InMemoryReviewDecisionReceiptRepository())
    orchestrator = ExtractionOrchestrator(
        None,
        cast(ExtractionPersistence, object()),
        None,
        review_receipt_service=receipts,
        correction_burden_service=telemetry,
    )
    actor = ReviewActorContext(
        project_id="project-alpha",
        actor_id="reviewer-private",
        capability="candidate.review",
        authorization_revision="trusted.v1",
    )
    review = ReviewDecisionRequest.model_validate(
        {
            "projectId": "project-alpha",
            "itemKind": "entity",
            "itemHandle": "eh1_" + "a" * 64,
            "candidateRevision": 1,
            "expectedCandidateRevision": 0,
            "sourceVersionId": SOURCE,
            "sourceVersionRevision": 1,
            "constrainedContractVersion": "entity-handle.v1",
            "idempotencyKey": "review-hook-1",
            "decision": "confirm",
        }
    )
    orchestrator.record_review_decision(
        TrustedRequestContext("project-alpha", "reviewer-private", "request-1"), actor, review
    )
    assert telemetry.summary("project-alpha").event_count == 1
