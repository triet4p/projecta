"""S13-02 sanctioned RM-63 bridge: approved-only manual plan, cross-language digest, safe binding.

Only a ``confirm`` RM-61 receipt bound to a server-verified manual capture can
produce a versioned ``ApprovedAssertionPlan`` payload. Reject/abstain, stale or
cross-project scope, tampered evidence, unvalidated captures, and malformed
IRIs/keys fail closed and materialize nothing. The payload mirrors the Semantic
Core plan record field for field so the focused Java parity test can assert
byte-identical ``bodyDigest`` and ``projecta-approved-candidate/v1`` review
binding before the Core test-only opt-in promotes the candidate. Production
materialization stays disabled; this module opens no runtime path.
"""

from __future__ import annotations

from datetime import date
from hashlib import sha256

import pytest

from projecta_api.extraction.approved_assertion_plan import (
    APPROVED_ASSERTION_PLAN_VERSION,
    MANUAL_CONSTRAINED_CONTRACT_VERSION,
    MANUAL_EVIDENCE_SELECTION_VERSION,
    MANUAL_ONTOLOGY_VERSION,
    ManualApprovedPlan,
    ManualApprovedPlanError,
    build_manual_approved_plan,
)
from projecta_api.extraction.manual_capture import resolve_manual_capture
from projecta_api.extraction.review_receipts import (
    InMemoryReviewDecisionReceiptRepository,
    ReviewActorContext,
    ReviewDecisionReceiptService,
    ReviewDecisionRequest,
)

_PROJECT_ID = "project-alpha"
_SOURCE_TEXT = "Plan \U0001f680 rollout"
_CANDIDATE_IRI = "https://w3id.org/projecta/data/project/project-alpha/candidate/note-1-1"
_ASSERTED_IRI = "https://w3id.org/projecta/data/project/project-alpha/requirement/req-manual-1"
_REVIEWER_IRI = "https://w3id.org/projecta/data/project/project-alpha/person/reviewer-1"
_PROVENANCE_IRI = (
    "https://w3id.org/projecta/data/project/project-alpha/activity/materialize/manual-1"
)
_EXPECTED_GRAPH_REVISION = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
_PARITY_BODY_DIGEST = "sha256:529948d4c8a5d7efb4df2416d2a7b9b15e9e918a367443871cb9593851a223d9"
_PARITY_COMMENT = (
    "projecta-approved-candidate/v1|candidateRevision=1"
    "|sourceVersionId=sv_abababababababababababababababababababababababababababababababab"
    "|sourceVersionRevision=1|reviewReceiptDigest=sha256:"
    + "1" * 64
    + "|evidenceDigest=sha256:"
    + "2" * 64
    + "|constrainedRelationContractVersion=manual-entity-capture.v1"
    "|evidenceSelectionVersion=text-anchor.v1"
)


def _capture():
    return resolve_manual_capture(
        _PROJECT_ID,
        {
            "candidateId": "note-1-1",
            "candidateRevision": 1,
            "candidateStatus": "validated",
            "sourceArtifactId": "note-1",
            "title": "Planning",
            "rawText": _SOURCE_TEXT,
            "evidenceText": _SOURCE_TEXT,
            "entityType": "Task",
            "startOffset": 0,
            "endOffset": len(_SOURCE_TEXT),
        },
    )


def _receipts() -> ReviewDecisionReceiptService:
    return ReviewDecisionReceiptService(InMemoryReviewDecisionReceiptRepository())


def _actor(project_id: str = _PROJECT_ID) -> ReviewActorContext:
    return ReviewActorContext(
        project_id=project_id,
        actor_id="reviewer-1",
        capability="candidate.review",
        authorization_revision="trusted-context.v1",
    )


def _handle() -> str:
    digest = sha256(f"{_PROJECT_ID}:review-entity:candidate-h-1".encode()).hexdigest()
    return f"eh1_{digest}"


def _confirm_receipt(service: ReviewDecisionReceiptService, capture, *, key: str = "manual-plan-1"):
    return service.record(
        _actor(),
        ReviewDecisionRequest(
            projectId=_PROJECT_ID,
            itemKind="entity",
            itemHandle=_handle(),
            candidateRevision=capture.candidate_revision,
            expectedCandidateRevision=0,
            sourceVersionId=capture.source_version.source_version_id,
            sourceVersionRevision=1,
            constrainedContractVersion=MANUAL_CONSTRAINED_CONTRACT_VERSION,
            evidenceDigest=capture.anchor.quote_digest,
            previousDecisionDigest=None,
            idempotencyKey=key,
            decision="confirm",
            decisionPayloadDigest="sha256:" + "c" * 64,
        ),
    )


def _plan(capture, receipt, **overrides):
    params = {
        "project_id": _PROJECT_ID,
        "candidate_iri": _CANDIDATE_IRI,
        "capture": capture,
        "receipt": receipt,
        "expected_asserted_graph_revision": _EXPECTED_GRAPH_REVISION,
        "provenance_activity_iri": _PROVENANCE_IRI,
        "idempotency_key": "manual-plan-1",
        "asserted_iri": _ASSERTED_IRI,
        "reviewer_iri": _REVIEWER_IRI,
        "valid_from": date(2026, 9, 27),
    }
    params.update(overrides)
    return build_manual_approved_plan(**params)


def test_confirm_receipt_builds_versioned_plan_with_zero_model_calls() -> None:
    capture = _capture()
    service = _receipts()
    receipt = _confirm_receipt(service, capture)

    plan = _plan(capture, receipt)

    assert plan.safe_dict()["contractVersion"] == APPROVED_ASSERTION_PLAN_VERSION
    assert plan.ontology_version == MANUAL_ONTOLOGY_VERSION
    assert plan.constrained_relation_contract_version == MANUAL_CONSTRAINED_CONTRACT_VERSION
    assert plan.evidence_selection_version == MANUAL_EVIDENCE_SELECTION_VERSION
    assert plan.review_receipt_digest == receipt.receipt_digest
    assert plan.evidence_digest == capture.anchor.quote_digest
    assert plan.body_digest().startswith("sha256:")
    assert plan.metadata_comment().startswith("projecta-approved-candidate/v1|")
    assert "rawText" not in str(plan.safe_dict())


def test_plan_digest_and_binding_match_semantic_core_algorithms() -> None:
    parity = ManualApprovedPlan(
        project=_PROJECT_ID,
        candidate_iri=_CANDIDATE_IRI,
        candidate_revision=1,
        source_version_id="sv_" + "ab" * 32,
        source_version_revision=1,
        review_receipt_digest="sha256:" + "1" * 64,
        evidence_digest="sha256:" + "2" * 64,
        ontology_version="0.3.0",
        constrained_relation_contract_version="manual-entity-capture.v1",
        evidence_selection_version="text-anchor.v1",
        asserted_iri=_ASSERTED_IRI,
        reviewer_iri=_REVIEWER_IRI,
        label="Parity assertion label",
        valid_from=date(2026, 9, 27),
        expected_asserted_graph_revision="sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        provenance_activity_iri=_PROVENANCE_IRI,
        idempotency_key="parity-key-1",
    )

    assert parity.body_digest() == _PARITY_BODY_DIGEST
    assert parity.metadata_comment() == _PARITY_COMMENT


@pytest.mark.parametrize("decision", ["reject", "abstain"])
def test_reject_and_abstain_receipts_cannot_back_a_plan(decision: str) -> None:
    capture = _capture()
    service = _receipts()
    confirm = _confirm_receipt(service, capture)
    closing = service.record(
        _actor(),
        ReviewDecisionRequest(
            projectId=_PROJECT_ID,
            itemKind="entity",
            itemHandle=_handle(),
            candidateRevision=1,
            expectedCandidateRevision=1,
            sourceVersionId=capture.source_version.source_version_id,
            sourceVersionRevision=1,
            constrainedContractVersion=MANUAL_CONSTRAINED_CONTRACT_VERSION,
            evidenceDigest=capture.anchor.quote_digest,
            previousDecisionDigest=confirm.receipt_digest,
            idempotencyKey=f"manual-plan-{decision}",
            decision=decision,  # type: ignore[arg-type]
        ),
    )

    with pytest.raises(ManualApprovedPlanError):
        _plan(capture, closing, idempotency_key=f"manual-plan-{decision}")


def test_stale_cross_project_tampered_and_unvalidated_pairs_fail_closed() -> None:
    capture = _capture()
    service = _receipts()
    confirm = _confirm_receipt(service, capture)

    with pytest.raises(ManualApprovedPlanError):
        _plan(capture, confirm, project_id="project-beta")

    tampered = confirm.model_copy(update={"source_version_digest": "sha256:" + "f" * 64})
    with pytest.raises(ManualApprovedPlanError):
        _plan(capture, tampered)

    stale_receipt = service.record(
        _actor(),
        ReviewDecisionRequest(
            projectId=_PROJECT_ID,
            itemKind="entity",
            itemHandle=_handle(),
            candidateRevision=2,
            expectedCandidateRevision=1,
            sourceVersionId=capture.source_version.source_version_id,
            sourceVersionRevision=1,
            constrainedContractVersion=MANUAL_CONSTRAINED_CONTRACT_VERSION,
            evidenceDigest=capture.anchor.quote_digest,
            previousDecisionDigest=confirm.receipt_digest,
            idempotencyKey="manual-plan-stale",
            decision="confirm",
            decisionPayloadDigest="sha256:" + "c" * 64,
        ),
    )
    with pytest.raises(ManualApprovedPlanError):
        _plan(capture, stale_receipt, idempotency_key="manual-plan-stale")

    tampered_evidence = confirm.model_copy(update={"evidence_digest": "sha256:" + "e" * 64})
    with pytest.raises(ManualApprovedPlanError):
        _plan(capture, tampered_evidence)

    extracted = resolve_manual_capture(
        _PROJECT_ID,
        {
            "candidateId": "note-1-1",
            "candidateRevision": 1,
            "candidateStatus": "extracted",
            "sourceArtifactId": "note-1",
            "title": "Planning",
            "rawText": _SOURCE_TEXT,
            "evidenceText": _SOURCE_TEXT,
            "entityType": "Task",
            "startOffset": 0,
            "endOffset": len(_SOURCE_TEXT),
        },
    )
    with pytest.raises(ManualApprovedPlanError):
        _plan(extracted, confirm)

    with pytest.raises(ManualApprovedPlanError):
        _plan(
            capture,
            confirm,
            candidate_iri="https://w3id.org/projecta/data/project/other/candidate/note-1-1",
        )
    with pytest.raises(ManualApprovedPlanError):
        _plan(capture, confirm, idempotency_key="bad|key")
