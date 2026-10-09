"""RM-61 durable review decision receipt contract tests."""

from __future__ import annotations

import json
from typing import Literal, cast

import pytest

from projecta_api.extraction.review_receipts import (
    InMemoryReviewDecisionReceiptRepository,
    ReviewActorContext,
    ReviewAuthorizationError,
    ReviewDecisionReceiptService,
    ReviewDecisionRequest,
    ReviewReceiptConflict,
    ReviewReceiptStaleError,
)
from projecta_api.operational.errors import IdempotencyConflict


def _request(
    *,
    item_kind: str = "entity",
    item_handle: str = "eh1_" + "a" * 64,
    source_version_id: str = "sv_" + "b" * 64,
    candidate_revision: int = 1,
    expected_candidate_revision: int = 0,
    idempotency_key: str = "review-1",
    decision: str = "confirm",
    previous_decision_digest: str | None = None,
) -> ReviewDecisionRequest:
    return ReviewDecisionRequest.model_validate(
        {
            "projectId": "project-alpha",
            "itemKind": item_kind,
            "itemHandle": item_handle,
            "candidateRevision": candidate_revision,
            "expectedCandidateRevision": expected_candidate_revision,
            "sourceVersionId": source_version_id,
            "sourceVersionRevision": 1,
            "constrainedContractVersion": "entity-handle.v1",
            "evidenceDigest": None,
            "previousDecisionDigest": previous_decision_digest,
            "idempotencyKey": idempotency_key,
            "decision": decision,
            "decisionPayloadDigest": "sha256:" + "c" * 64 if decision == "edit" else None,
        }
    )


def _service() -> tuple[ReviewDecisionReceiptService, InMemoryReviewDecisionReceiptRepository]:
    repository = InMemoryReviewDecisionReceiptRepository()
    return ReviewDecisionReceiptService(repository), repository


def _actor(
    project_id: str = "project-alpha",
    capability: Literal["candidate.review"] = "candidate.review",
) -> ReviewActorContext:
    return ReviewActorContext(
        project_id=project_id,
        actor_id="reviewer-private",
        capability=capability,
        authorization_revision="membership-rev-7",
    )


def test_receipts_append_confirm_edit_reject_and_abstain_with_digest_chain() -> None:
    service, repository = _service()
    actor = _actor()
    first = service.record(actor, _request())
    assert first.outcome == "accepted" and first.sequence == 1
    second = service.record(
        actor,
        _request(
            candidate_revision=1,
            expected_candidate_revision=1,
            idempotency_key="review-edit",
            decision="edit",
            previous_decision_digest=first.receipt_digest,
        ),
    )
    third = service.record(
        actor,
        _request(
            candidate_revision=1,
            expected_candidate_revision=1,
            idempotency_key="review-reject",
            decision="reject",
            previous_decision_digest=second.receipt_digest,
        ),
    )
    fourth = service.record(
        actor,
        _request(
            candidate_revision=1,
            expected_candidate_revision=1,
            idempotency_key="review-abstain",
            decision="abstain",
            previous_decision_digest=third.receipt_digest,
        ),
    )
    assert [row.decision for row in repository.history("project-alpha", "entity", "sha256:" + "0" * 64)] == []
    assert [row.sequence for row in service.history(actor, "entity", "eh1_" + "a" * 64)] == [1, 2, 3, 4]
    assert fourth.previous_decision_digest == third.receipt_digest


def test_exact_idempotent_replay_returns_same_receipt_without_mutation() -> None:
    service, _ = _service()
    actor = _actor()
    first = service.record(actor, _request())
    replay = service.record(actor, _request())
    assert replay.outcome == "replayed"
    assert replay.receipt_digest == first.receipt_digest
    assert replay.sequence == first.sequence


def test_same_idempotency_key_with_different_body_conflicts() -> None:
    service, _ = _service()
    actor = _actor()
    service.record(actor, _request())
    with pytest.raises(IdempotencyConflict):
        service.record(actor, _request(decision="reject"))


def test_stale_source_candidate_and_previous_digest_fail_closed() -> None:
    service, _ = _service()
    actor = _actor()
    first = service.record(actor, _request())
    with pytest.raises(ReviewReceiptStaleError):
        service.record(
            actor,
            _request(
                source_version_id="sv_" + "d" * 64,
                candidate_revision=1,
                expected_candidate_revision=1,
                idempotency_key="stale-source",
                previous_decision_digest=first.receipt_digest,
            ),
        )
    with pytest.raises(ReviewReceiptStaleError):
        service.record(
            actor,
            _request(
                candidate_revision=1,
                expected_candidate_revision=0,
                idempotency_key="stale-candidate",
            ),
        )
    with pytest.raises(ReviewReceiptConflict):
        service.record(
            actor,
            _request(
                candidate_revision=1,
                expected_candidate_revision=1,
                idempotency_key="bad-chain",
                previous_decision_digest="sha256:" + "e" * 64,
            ),
        )


def test_project_scope_and_unauthorized_actor_fail_closed() -> None:
    service, _ = _service()
    with pytest.raises(ReviewAuthorizationError):
        service.record(_actor(project_id="project-other"), _request())
    with pytest.raises(ReviewAuthorizationError):
        service.record(
            ReviewActorContext.model_construct(
                project_id="project-alpha",
                actor_id="reviewer-private",
                capability=cast(Literal["candidate.review"], "project-reader"),
                authorization_revision="membership-rev-7",
            ),
            _request(),
        )


def test_safe_serialization_excludes_raw_identifiers_and_payload() -> None:
    service, _ = _service()
    receipt = service.record(_actor(), _request())
    serialized = json.dumps(receipt.safe_dict(), sort_keys=True)
    assert "reviewer-private" not in serialized
    assert "eh1_" not in serialized
    assert "sv_" not in serialized
    assert "review-1" not in serialized


