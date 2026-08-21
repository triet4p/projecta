from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "evaluation/sprint-12"
OPT = EVAL / "optimization"


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


REPORT = OPT / "s12-f-12-stage-a-report.v6.json"
CONTRACT = OPT / "s12-f-12-rm28-diagnostic-contract.v1.json"
PACKAGE = OPT / "s12-f-12-rm28-offline-remediation.v1.json"
ANALYZER = ROOT / "scripts/s12_f12_rm28_offline_diagnostics.py"
NEXT_STATE = EVAL / "current-state-next.v1.json"
V16 = OPT / "g5-packet.v16.offline-remediation-preparation.json"
REVIEW = OPT / "s12-f-12-rm29-owner-review.v1.json"
TRANSITION = OPT / "s12-f-12-rm29-approval-transition.v1.json"
G5 = OPT / "g5-packet.v17.json"
CURRENT_G5 = OPT / "g5-packet.v29.rm43-issuance.json"
CURRENT = EVAL / "current-state.v1.json"


def test_rm29_review_binds_rm28_chain_and_preserves_unknowns() -> None:
    review = _json(REVIEW)
    evidence = review["reviewedEvidence"]
    assert evidence["immutableReport"]["digest"] == _digest(REPORT)
    assert evidence["diagnosticContract"]["digest"] == _digest(CONTRACT)
    assert evidence["remediationPackage"]["digest"] == _digest(PACKAGE)
    assert evidence["diagnosticImplementation"]["digest"] == _digest(ANALYZER)
    assert evidence["nonAuthoritativeNextState"]["digest"] == _digest(NEXT_STATE)
    assert evidence["nonAuthoritativeG5Preparation"]["digest"] == _digest(V16)
    assert review["verifiedEvidence"]["schemaInvalidTotal"] == 6
    assert review["verifiedEvidence"]["invalidEvidenceTotal"] == 17
    assert review["verifiedEvidence"]["goldRelationsControlFailures"] == 0
    assert review["ownerAssessment"]["unknownsPreservedWithoutGuessing"] is True


def test_rm29_decision_opens_only_offline_implementation() -> None:
    review = _json(REVIEW)
    decision = review["decision"]
    assert decision["offlineDiagnosticImplementationAuthorized"] is True
    assert decision["offlineSchemaEvidenceRemediationAuthorized"] is True
    for key in (
        "supersedingLineagePreparationAuthorized",
        "preregistrationIssued",
        "technicalFreezeIssued",
        "providerExecutionAuthorized",
        "newAuthorizationIssued",
        "validationAccessAuthorized",
        "heldOutAccessAuthorized",
        "stageBAuthorized",
        "candidateSelectionAuthorized",
        "promotionAuthorized",
    ):
        assert decision[key] is False, key
    assert decision["nextPermittedAction"] == (
        "IMPLEMENT_OFFLINE_F12_DIAGNOSTIC_REMEDIATION_AND_MOCK_TESTS"
    )


def test_rm29_transition_and_g5_v17_have_exact_pointers_and_locks() -> None:
    transition = _json(TRANSITION)
    g5 = _json(G5)
    assert transition["ownerReview"]["digest"] == _digest(REVIEW)
    assert transition["approvedPreparation"]["remediationPackage"]["digest"] == _digest(PACKAGE)
    assert transition["approvedPreparation"]["diagnosticContract"]["digest"] == _digest(CONTRACT)
    assert transition["currentDecisionState"]["providerExecutionAuthorized"] is False
    assert transition["currentDecisionState"]["supersedingLineagePreparationAuthorized"] is False
    assert g5["ownerDecision"]["digest"] == _digest(REVIEW)
    assert g5["approvalTransition"]["digest"] == _digest(TRANSITION)
    assert g5["status"] == "G5_F12_OFFLINE_REMEDIATION_APPROVED_IMPLEMENTATION_ONLY"
    assert g5["approvedRemediation"]["package"] == PACKAGE.relative_to(ROOT).as_posix()
    locks = g5["authorizationBoundary"]
    for key in (
        "supersedingLineagePreparationAuthorized",
        "providerExecutionAuthorized",
        "preregistrationIssued",
        "technicalFreezeIssued",
        "newAuthorizationIssued",
        "validationAuthorized",
        "heldOutAccessAuthorized",
        "stageBAuthorized",
        "candidateSelectionAuthorized",
        "promotionAuthorized",
    ):
        assert locks[key] is False, key
    assert locks["offlineDiagnosticImplementationAuthorized"] is True
    assert locks["offlineSchemaEvidenceRemediationAuthorized"] is True


def test_rm29_current_state_and_plan_advances_to_rm31_after_rm30() -> None:
    current = _json(CURRENT)
    g5 = _json(CURRENT_G5)
    plan = (ROOT / "docs/sprint-plans/sprint-12.md").read_text(encoding="utf-8")
    assert current["status"] == "G5_F12_CORRECTED_V9_LINEAGE_ISSUED_PROVIDER_AUTHORIZATION_PENDING"
    assert current["status"] == g5["status"]
    assert current["currentEvidence"]["remediationOwnerReview"]["path"] == REVIEW.relative_to(ROOT).as_posix()
    assert current["currentEvidence"]["remediationApprovalTransition"]["path"] == TRANSITION.relative_to(ROOT).as_posix()
    assert current["currentEvidence"]["g5Packet"]["path"] == CURRENT_G5.relative_to(ROOT).as_posix()
    assert current["experimentState"]["historicalLineage"]["providerCallsPerformed"] == 144
    assert current["experimentState"]["historicalLineage"]["retryCount"] == 0
    assert current["nextTasks"] == [
        "S12-RM-44_PREPARE_EXACT_V9_STAGE_A_AUTHORIZATION",
        "S12-RM-45_OWNER_REVIEW_EXACT_V9_STAGE_A_AUTHORIZATION",
    ]
    assert "[x] **S12-RM-29" in plan
    assert "[x] **S12-RM-30" in plan
    assert "[x] **S12-RM-31" in plan
    assert "[x] **S12-RM-32" in plan
    assert "[x] **S12-RM-33" in plan
    assert "[x] **S12-RM-34" in plan
    assert "[x] **S12-RM-35" in plan
    assert "[x] **S12-RM-43" in plan
    assert "[ ] **S12-RM-44" in plan
    assert "[ ] **S12-RM-45" in plan
    assert "sprint-12/g5-optimization.v29.rm43-issuance.md" in plan
