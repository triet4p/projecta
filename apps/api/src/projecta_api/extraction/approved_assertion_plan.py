"""Test-only bridge from an approved manual receipt to an RM-63 assertion plan.

S13-02 records a durable RM-61 confirm receipt for a validated manual Note
capture but deliberately leaves RM-63 production materialization owner-locked.
This module is the sanctioned test-only path from that receipt to a versioned
``ApprovedAssertionPlan`` payload: it accepts only a ``confirm`` receipt bound
to the server-resolved :class:`VerifiedManualCapture`, and it fails closed for
reject/abstain decisions, stale revisions, cross-project scope, tampered
evidence, unvalidated captures, and malformed IRIs/keys.

The payload mirrors the Semantic Core ``ApprovedAssertionPlan`` record field
for field, including its ``bodyDigest`` and ``metadataComment`` algorithms, so
a focused Java test can assert byte-identical digests before the Core
test-only binding service promotes the candidate. The sanctioned test-only
orchestration is :func:`plan_and_fixture_for_test_materialization`: it builds
the approved plan from the *actual persisted receipt* (never a hand-seeded
digest) and returns a minimal in-memory candidate fixture carrying the exact
safe review binding the Core boundary rechecks transactionally. Nothing here
enables production materialization: the Core boundary stays disabled by
default, the API runtime approval route never calls this module, and the
legacy API confirmation routes keep returning
``MATERIALIZATION_NOT_AUTHORIZED`` for manual captures.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from typing import Final
from urllib.parse import urlparse

from projecta_api.extraction.manual_capture import VerifiedManualCapture
from projecta_api.extraction.review_receipts import (
    ReviewActorContext,
    ReviewDecisionReceiptRecord,
    ReviewDecisionReceiptService,
)

APPROVED_ASSERTION_PLAN_VERSION: Final = "approved-assertion-plan.v1"
MANUAL_ONTOLOGY_VERSION: Final = "0.3.0"
MANUAL_CONSTRAINED_CONTRACT_VERSION: Final = "manual-entity-capture.v1"
MANUAL_EVIDENCE_SELECTION_VERSION: Final = "text-anchor.v1"
MANUAL_SOURCE_VERSION_REVISION: Final = 1
DATA_BASE: Final = "https://w3id.org/projecta/data/project/"

_PROJECT_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")
_SOURCE_ID_PATTERN = re.compile(r"sv_[0-9a-f]{64}")
_DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
_VERSION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


class ManualApprovedPlanError(ValueError):
    """Raised when a receipt/capture pair cannot back an assertion plan."""


@dataclass(frozen=True, slots=True)
class ManualApprovedPlan:
    """Versioned, review-bound plan payload for one manual candidate."""

    project: str
    candidate_iri: str
    candidate_revision: int
    source_version_id: str
    source_version_revision: int
    review_receipt_digest: str
    evidence_digest: str
    ontology_version: str
    constrained_relation_contract_version: str
    evidence_selection_version: str
    asserted_iri: str
    reviewer_iri: str
    label: str
    valid_from: date
    expected_asserted_graph_revision: str
    provenance_activity_iri: str
    idempotency_key: str

    def body_digest(self) -> str:
        """Replicate the Core plan digest byte for byte (UTF-8, ``|`` joins)."""

        canonical = "|".join(
            [
                self.project,
                self.candidate_iri,
                str(self.candidate_revision),
                self.source_version_id,
                str(self.source_version_revision),
                self.review_receipt_digest,
                self.evidence_digest,
                self.ontology_version,
                self.constrained_relation_contract_version,
                self.evidence_selection_version,
                self.asserted_iri,
                self.reviewer_iri,
                self.label,
                self.valid_from.isoformat(),
            ]
        )
        body = "|".join(
            [
                APPROVED_ASSERTION_PLAN_VERSION,
                self.project,
                self.source_version_id,
                str(self.source_version_revision),
                self.ontology_version,
                self.constrained_relation_contract_version,
                self.evidence_selection_version,
                self.expected_asserted_graph_revision,
                self.provenance_activity_iri,
                self.idempotency_key,
                canonical,
            ]
        )
        return _digest(body.encode("utf-8", "strict"))

    def metadata_comment(self) -> str:
        """Replicate the Core candidate review-binding comment exactly."""

        return (
            "projecta-approved-candidate/v1"
            f"|candidateRevision={self.candidate_revision}"
            f"|sourceVersionId={self.source_version_id}"
            f"|sourceVersionRevision={self.source_version_revision}"
            f"|reviewReceiptDigest={self.review_receipt_digest}"
            f"|evidenceDigest={self.evidence_digest}"
            f"|constrainedRelationContractVersion={self.constrained_relation_contract_version}"
            f"|evidenceSelectionVersion={self.evidence_selection_version}"
        )

    def safe_dict(self) -> dict[str, object]:
        """Return JSON-safe plan data without raw source text or quotes."""

        return {
            "contractVersion": APPROVED_ASSERTION_PLAN_VERSION,
            "project": self.project,
            "candidateIri": self.candidate_iri,
            "candidateRevision": self.candidate_revision,
            "sourceVersionId": self.source_version_id,
            "sourceVersionRevision": self.source_version_revision,
            "reviewReceiptDigest": self.review_receipt_digest,
            "evidenceDigest": self.evidence_digest,
            "ontologyVersion": self.ontology_version,
            "constrainedRelationContractVersion": self.constrained_relation_contract_version,
            "evidenceSelectionVersion": self.evidence_selection_version,
            "assertedIri": self.asserted_iri,
            "reviewerIri": self.reviewer_iri,
            "label": self.label,
            "validFrom": self.valid_from.isoformat(),
            "expectedAssertedGraphRevision": self.expected_asserted_graph_revision,
            "provenanceActivityIri": self.provenance_activity_iri,
            "idempotencyKey": self.idempotency_key,
            "bodyDigest": self.body_digest(),
        }


def plan_from_wire_format(payload: object) -> ManualApprovedPlan:
    """Rebuild a plan from its wire format, revalidating every invariant.

    This is the receiving half of the test-only API&rarr;Core delivery: the
    Java Core boundary parses the same payload the API serves. Unknown fields
    and any invariant violation fail closed with
    :class:`ManualApprovedPlanError`.
    """

    if not isinstance(payload, dict):
        raise ManualApprovedPlanError("approved plan payload is invalid")
    known = {
        "contractVersion",
        "project",
        "candidateIri",
        "candidateRevision",
        "sourceVersionId",
        "sourceVersionRevision",
        "reviewReceiptDigest",
        "evidenceDigest",
        "ontologyVersion",
        "constrainedRelationContractVersion",
        "evidenceSelectionVersion",
        "assertedIri",
        "reviewerIri",
        "label",
        "validFrom",
        "expectedAssertedGraphRevision",
        "provenanceActivityIri",
        "idempotencyKey",
        "bodyDigest",
    }
    unknown = set(payload) - known
    if unknown:
        raise ManualApprovedPlanError("approved plan payload carries unknown fields")
    try:
        plan = ManualApprovedPlan(
            project=str(payload["project"]),
            candidate_iri=str(payload["candidateIri"]),
            candidate_revision=int(payload["candidateRevision"]),  # type: ignore[arg-type]
            source_version_id=str(payload["sourceVersionId"]),
            source_version_revision=int(payload["sourceVersionRevision"]),  # type: ignore[arg-type]
            review_receipt_digest=str(payload["reviewReceiptDigest"]),
            evidence_digest=str(payload["evidenceDigest"]),
            ontology_version=str(payload["ontologyVersion"]),
            constrained_relation_contract_version=str(
                payload["constrainedRelationContractVersion"]
            ),
            evidence_selection_version=str(payload["evidenceSelectionVersion"]),
            asserted_iri=str(payload["assertedIri"]),
            reviewer_iri=str(payload["reviewerIri"]),
            label=str(payload["label"]),
            valid_from=date.fromisoformat(str(payload["validFrom"])),
            expected_asserted_graph_revision=str(payload["expectedAssertedGraphRevision"]),
            provenance_activity_iri=str(payload["provenanceActivityIri"]),
            idempotency_key=str(payload["idempotencyKey"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ManualApprovedPlanError("approved plan payload is invalid") from error
    _validate_plan(plan)
    if str(payload.get("bodyDigest", plan.body_digest())) != plan.body_digest():
        raise ManualApprovedPlanError("approved plan body digest does not match")
    contract = str(payload.get("contractVersion", APPROVED_ASSERTION_PLAN_VERSION))
    if contract != APPROVED_ASSERTION_PLAN_VERSION:
        raise ManualApprovedPlanError("approved plan contract is not supported")
    return plan


def build_manual_approved_plan(
    *,
    project_id: str,
    candidate_iri: str,
    capture: VerifiedManualCapture,
    receipt: ReviewDecisionReceiptRecord,
    expected_asserted_graph_revision: str,
    provenance_activity_iri: str,
    idempotency_key: str,
    asserted_iri: str,
    reviewer_iri: str,
    valid_from: date,
    label: str | None = None,
) -> ManualApprovedPlan:
    """Bind a confirm receipt and verified capture into an assertion plan.

    Every invariant is rechecked here even though the approval route already
    enforced it: only ``confirm`` receipts for a ``validated`` capture in the
    same project, with matching candidate/source revisions and evidence
    digest, can produce a plan. Anything else raises
    :class:`ManualApprovedPlanError` and materializes nothing.
    """

    if receipt.decision != "confirm":
        raise ManualApprovedPlanError("only a confirm receipt can back an assertion plan")
    if capture.candidate_status != "validated":
        raise ManualApprovedPlanError("manual capture is not validated")
    if receipt.project_digest != _digest(project_id.encode("utf-8", "strict")):
        raise ManualApprovedPlanError("receipt project does not match the plan project")
    if receipt.candidate_revision != capture.candidate_revision:
        raise ManualApprovedPlanError("receipt candidate revision does not match the capture")
    if receipt.source_version_digest != _digest(
        capture.source_version.source_version_id.encode("utf-8", "strict")
    ):
        raise ManualApprovedPlanError("receipt source version does not match the capture")
    if receipt.source_version_revision != MANUAL_SOURCE_VERSION_REVISION:
        raise ManualApprovedPlanError("receipt source version revision is stale")
    if receipt.evidence_digest != capture.anchor.quote_digest:
        raise ManualApprovedPlanError("receipt evidence does not match the verified anchor")
    if receipt.constrained_contract_version != MANUAL_CONSTRAINED_CONTRACT_VERSION:
        raise ManualApprovedPlanError("receipt contract is not the manual capture contract")

    resolved_label = capture.evidence_text if label is None else label
    plan = ManualApprovedPlan(
        project=project_id,
        candidate_iri=candidate_iri,
        candidate_revision=capture.candidate_revision,
        source_version_id=capture.source_version.source_version_id,
        source_version_revision=MANUAL_SOURCE_VERSION_REVISION,
        review_receipt_digest=receipt.receipt_digest,
        evidence_digest=capture.anchor.quote_digest,
        ontology_version=MANUAL_ONTOLOGY_VERSION,
        constrained_relation_contract_version=MANUAL_CONSTRAINED_CONTRACT_VERSION,
        evidence_selection_version=MANUAL_EVIDENCE_SELECTION_VERSION,
        asserted_iri=asserted_iri,
        reviewer_iri=reviewer_iri,
        label=resolved_label,
        valid_from=valid_from,
        expected_asserted_graph_revision=expected_asserted_graph_revision,
        provenance_activity_iri=provenance_activity_iri,
        idempotency_key=idempotency_key,
    )
    _validate_plan(plan)
    return plan


@dataclass(frozen=True, slots=True)
class TestMaterializationFixture:
    """Test-only lifecycle transition the Core boundary applies itself.

    The fixture carries only the human-approval identity Core rechecks
    transactionally: the plan's exact ``projecta-approved-candidate/v1`` safe
    review binding and the released manual ontology version. Java applies the
    confirmed transition to the real ``QuickNoteCaptureService`` candidate row
    (the same row Core persisted at capture) via
    ``ManualApprovedReviewBinding`` before submitting the paired plan under
    ``MaterializationAuthorization.enabledForTest()``. Python never writes a
    cross-language fixture file. Production code must never consume this
    fixture.
    """

    project: str
    candidate_iri: str
    lifecycle_status: str
    ontology_version: str
    safe_binding_comment: str


def plan_and_fixture_for_test_materialization(
    *,
    project_id: str,
    candidate_iri: str,
    capture: VerifiedManualCapture,
    receipts: ReviewDecisionReceiptService,
    actor: ReviewActorContext,
    item_kind: str,
    item_handle: str,
    expected_asserted_graph_revision: str,
    provenance_activity_iri: str,
    idempotency_key: str,
    asserted_iri: str,
    reviewer_iri: str,
    valid_from: date,
    label: str | None = None,
) -> tuple[ManualApprovedPlan, TestMaterializationFixture]:
    """Build the approved plan from the actual persisted confirm receipt.

    This is the sanctioned test-only orchestration of the production approval
    logic: it reads the durable RM-61 receipt history persisted by the real
    ``manual-approvals`` route (via ``ReviewDecisionReceiptService.history``),
    selects the latest receipt for the server-owned entity handle, and binds
    it to the server-resolved ``VerifiedManualCapture`` through
    :func:`build_manual_approved_plan`. The returned fixture records the Core
    lifecycle transition the human approval authorizes (``confirmed`` plus the
    plan's exact safe binding comment) so the Core test-side transition can
    apply it to the real captured candidate row before the Core boundary
    rechecks the revision/source/review binding inside its transaction. It
    raises :class:`ManualApprovedPlanError` when no persisted confirm receipt
    backs the capture (no-approval, reject, abstain, stale, cross-project, or
    tampered inputs all fail closed here and materialize nothing).
    """

    history = list(receipts.history(actor, item_kind, item_handle))  # type: ignore[arg-type]
    if not history:
        raise ManualApprovedPlanError("no persisted review receipt backs this capture")
    receipt = max(history, key=lambda item: item.sequence)
    plan = build_manual_approved_plan(
        project_id=project_id,
        candidate_iri=candidate_iri,
        capture=capture,
        receipt=receipt,
        expected_asserted_graph_revision=expected_asserted_graph_revision,
        provenance_activity_iri=provenance_activity_iri,
        idempotency_key=idempotency_key,
        asserted_iri=asserted_iri,
        reviewer_iri=reviewer_iri,
        valid_from=valid_from,
        label=label,
    )
    fixture = TestMaterializationFixture(
        project=plan.project,
        candidate_iri=plan.candidate_iri,
        lifecycle_status="confirmed",
        ontology_version=plan.ontology_version,
        safe_binding_comment=plan.metadata_comment(),
    )
    return plan, fixture


def _validate_plan(plan: ManualApprovedPlan) -> None:
    if _PROJECT_PATTERN.fullmatch(plan.project) is None:
        raise ManualApprovedPlanError("plan project is invalid")
    if _SOURCE_ID_PATTERN.fullmatch(plan.source_version_id) is None:
        raise ManualApprovedPlanError("plan source version ID is invalid")
    for field, value in (
        ("review receipt digest", plan.review_receipt_digest),
        ("evidence digest", plan.evidence_digest),
        ("expected asserted graph revision", plan.expected_asserted_graph_revision),
    ):
        if _DIGEST_PATTERN.fullmatch(value) is None:
            raise ManualApprovedPlanError(f"plan {field} is invalid")
    for field, value in (
        ("ontology version", plan.ontology_version),
        ("constrained relation contract version", plan.constrained_relation_contract_version),
        ("evidence selection version", plan.evidence_selection_version),
    ):
        if _VERSION_PATTERN.fullmatch(value) is None:
            raise ManualApprovedPlanError(f"plan {field} is invalid")
    if plan.candidate_revision < 1 or plan.source_version_revision < 1:
        raise ManualApprovedPlanError("plan candidate/source revisions must be positive")
    scope = DATA_BASE + plan.project + "/"
    if not plan.candidate_iri.startswith(scope + "candidate/") or not _absolute_iri(
        plan.candidate_iri
    ):
        raise ManualApprovedPlanError("plan candidate IRI is outside the project scope")
    if not plan.asserted_iri.startswith(scope) or not _absolute_iri(plan.asserted_iri):
        raise ManualApprovedPlanError("plan asserted IRI is outside the project scope")
    if not plan.reviewer_iri.startswith(scope + "person/") or not _absolute_iri(plan.reviewer_iri):
        raise ManualApprovedPlanError("plan reviewer IRI is outside the project scope")
    if not plan.provenance_activity_iri.startswith(scope) or not _absolute_iri(
        plan.provenance_activity_iri
    ):
        raise ManualApprovedPlanError("plan provenance activity IRI is outside the project scope")
    if not plan.idempotency_key or len(plan.idempotency_key) > 128 or "|" in plan.idempotency_key:
        raise ManualApprovedPlanError("plan idempotency key is invalid")
    if not plan.label or not plan.label.strip() or "|" in plan.label:
        raise ManualApprovedPlanError("plan assertion label is required")


def _absolute_iri(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()
