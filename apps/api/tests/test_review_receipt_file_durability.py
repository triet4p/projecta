"""S13-02 receipt restart durability: file-backed RM-61 store survives reopen.

Uses ``FileReviewDecisionReceiptRepository`` (same append/validate rules as the
in-memory and PostgreSQL adapters, one fsync'd JSON line per accepted row) in
a ``tmp_path`` directory, records a confirm receipt, drops the service
instance (simulated process restart), reopens from the same directory, and
proves the receipt history replays exactly with idempotent replay intact.
"""

from __future__ import annotations

from projecta_api.extraction.review_receipts import (
    FileReviewDecisionReceiptRepository,
    ReviewActorContext,
    ReviewDecisionReceiptService,
    ReviewDecisionRequest,
)


def _actor() -> ReviewActorContext:
    return ReviewActorContext(
        project_id="project-alpha",
        actor_id="reviewer-1",
        capability="candidate.review",
        authorization_revision="trusted-context.v1",
    )


def _request(
    *,
    item_handle: str = "eh1_" + "a" * 64,
    idempotency_key: str = "manual-approval-1",
) -> ReviewDecisionRequest:
    return ReviewDecisionRequest(
        projectId="project-alpha",
        itemKind="entity",
        itemHandle=item_handle,
        candidateRevision=1,
        expectedCandidateRevision=0,
        sourceVersionId="sv_" + "b" * 64,
        sourceVersionRevision=1,
        constrainedContractVersion="manual-entity-capture.v1",
        evidenceDigest="sha256:" + "c" * 64,
        previousDecisionDigest=None,
        idempotencyKey=idempotency_key,
        decision="confirm",
        decisionPayloadDigest="sha256:" + "d" * 64,
    )


def test_file_receipt_store_survives_reopen_with_idempotent_replay(tmp_path) -> None:
    actor = _actor()

    first_service = ReviewDecisionReceiptService(
        FileReviewDecisionReceiptRepository(tmp_path / "receipts")
    )
    accepted = first_service.record(actor, _request())
    assert accepted.outcome == "accepted"
    assert accepted.sequence == 1
    del first_service

    # Simulated process restart: a fresh service over the same directory.
    reopened = ReviewDecisionReceiptService(
        FileReviewDecisionReceiptRepository(tmp_path / "receipts")
    )
    history = list(reopened.history(actor, "entity", "eh1_" + "a" * 64))
    assert len(history) == 1
    assert history[0].receipt_digest == accepted.receipt_digest
    assert history[0].decision == "confirm"

    replay = reopened.record(actor, _request())
    assert replay.outcome == "replayed"
    assert replay.receipt_digest == accepted.receipt_digest
    assert len(list(reopened.history(actor, "entity", "eh1_" + "a" * 64))) == 1
