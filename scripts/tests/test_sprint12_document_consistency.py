from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "evaluation" / "sprint-12"
OPT = EVAL / "optimization"
DOCS = ROOT / "docs" / "sprint-plans" / "sprint-12"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _index_digest(path: Path) -> str:
    relative = path.relative_to(ROOT).as_posix()
    blob = subprocess.check_output(["git", "show", f":{relative}"], cwd=ROOT)
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def test_rm23f_transition_preserves_history_and_sets_current_state() -> None:
    transition = _json(OPT / "s12-f-12-rm23f-issuance-transition.v1.json")
    review_path = OPT / "s12-f-12-rm23f-owner-review.v1.json"
    prereg_path = OPT / "s12-f-12-rm22d-issuance-draft.v7.json"
    package_path = OPT / "s12-f-12-rm22d-execution-package.v7.json"
    freeze_path = OPT / "s12-f-12-rm22d-technical-freeze.v7.json"

    assert transition["ownerReview"]["digest"] == _digest(review_path)
    assert transition["issuedLineage"]["preregistration"]["digest"] == _digest(
        prereg_path
    )
    assert transition["issuedLineage"]["executionPackage"]["digest"] == _digest(
        package_path
    )
    assert transition["issuedLineage"]["technicalFreeze"]["digest"] == _digest(
        freeze_path
    )

    prereg = _json(prereg_path)
    freeze = _json(freeze_path)
    assert prereg["preregistrationIssued"] is False
    assert freeze["executionFreezeIssued"] is False
    assert transition["currentDecisionState"]["preregistrationIssued"] is True
    assert transition["currentDecisionState"]["executionFreezeIssued"] is True
    assert transition["currentDecisionState"]["providerExecutionAuthorized"] is False


def test_rm25_transition_remains_historical_and_current_state_agrees_after_rm33() -> None:
    current = _json(EVAL / "current-state.v1.json")
    g5 = _json(OPT / "g5-packet.v21.json")
    transition = _json(OPT / "s12-f-12-rm25-authorization-transition.v1.json")
    authorization_path = OPT / "s12-f-12-rm25-authorization.v1.json"
    review_path = OPT / "s12-f-12-rm25-owner-review.v1.json"

    expected = "G5_F12_V8_LINEAGE_ISSUED_PROVIDER_AUTHORIZATION_PENDING"
    assert current["status"] == expected
    assert g5["status"] == expected
    assert transition["authorization"]["digest"] == _digest(authorization_path)
    assert transition["ownerReview"]["digest"] == _digest(review_path)
    assert current["experimentState"]["candidateSelection"] == "NO_SELECTION"
    assert g5["selection"]["status"] == "NO_SELECTION"
    assert current["experimentState"]["currentGovernance"]["providerExecutionAuthorized"] is False
    assert g5["authorizationBoundary"]["providerExecutionAuthorized"] is False
    assert g5["authorizationBoundary"]["preregistrationIssued"] is True
    assert g5["authorizationBoundary"]["technicalFreezeIssued"] is True
    assert current["experimentState"]["historicalLineage"]["providerCallsPerformed"] == 144
    assert current["experimentState"]["stageAReportExists"] is True
    assert current["experimentState"]["stageAStatus"] == "COMPLETED_REJECTED_NO_STAGE_B"
    assert current["experimentState"]["heldOutInspected"] is False
    assert g5["authorizationBoundary"]["heldOutAccessAuthorized"] is False


def test_rm33_issuance_is_digest_bound_and_provider_locked() -> None:
    current = _json(EVAL / "current-state.v1.json")
    packet = _json(OPT / "g5-packet.v21.json")
    owner_path = OPT / "s12-f-12-rm33-owner-review.v1.json"
    transition_path = OPT / "s12-f-12-rm33-issuance-transition.v1.json"
    owner = _json(owner_path)
    transition = _json(transition_path)

    assert owner["status"] == "OWNER_ISSUANCE_REVIEW_APPROVED_ISSUANCE_ONLY"
    assert transition["ownerReview"]["digest"] == _digest(owner_path)
    assert packet["ownerDecision"]["digest"] == _digest(owner_path)
    assert packet["issuanceTransition"]["digest"] == _digest(transition_path)
    assert current["currentEvidence"]["rm33OwnerReview"]["digest"] == _digest(owner_path)
    assert current["currentEvidence"]["rm33IssuanceTransition"]["digest"] == _digest(transition_path)
    assert transition["currentDecisionState"]["preregistrationIssued"] is True
    assert transition["currentDecisionState"]["technicalFreezeIssued"] is True
    assert transition["currentDecisionState"]["providerExecutionAuthorized"] is False
    assert transition["currentDecisionState"]["newAuthorizationIssued"] is False
    assert packet["currentLineage"]["reportExists"] is False
    assert packet["currentLineage"]["providerCallsPerformed"] == 0
    for key in (
        "validationAccessAuthorized",
        "heldOutAccessAuthorized",
        "stageBAuthorized",
        "candidateSelectionAuthorized",
        "promotionAuthorized",
    ):
        assert packet["authorizationBoundary"][key] is False


def test_rm27_owner_decision_transition_and_current_state_bind_closed_lineage() -> None:
    current = _json(EVAL / "current-state.v1.json")
    decision_path = OPT / "s12-f-12-stage-a-decision.v1.json"
    transition_path = OPT / "s12-f-12-rm27-decision-transition.v1.json"
    g5_path = OPT / "g5-packet.v15.json"
    decision = _json(decision_path)
    transition = _json(transition_path)
    g5 = _json(g5_path)
    report_path = OPT / "s12-f-12-stage-a-report.v6.json"
    report = _json(report_path)

    assert decision["status"] == "COMPLETED_REJECTED_NO_STAGE_B"
    assert decision["decision"]["experimentClosedRejected"] is True
    assert decision["decision"]["preserveReport"] is True
    assert decision["decision"]["doNotRetryThisAuthorization"] is True
    assert decision["evidence"]["report"]["digest"] == _index_digest(report_path)
    assert transition["ownerDecision"]["digest"] == _digest(decision_path)
    assert transition["immutableReport"]["digest"] == _index_digest(report_path)
    assert g5["activeDecision"]["ownerDecision"]["digest"] == _digest(decision_path)
    assert g5["activeDecision"]["decisionTransition"]["digest"] == _digest(
        transition_path
    )
    assert current["currentEvidence"]["ownerDecision"]["expectedStatus"] == (
        "COMPLETED_REJECTED_NO_STAGE_B"
    )
    assert current["currentEvidence"]["decisionTransition"]["expectedStatus"] == (
        "F12_CLOSED_REJECTED_NO_STAGE_B_OFFLINE_REMEDIATION_PREPARATION_ONLY"
    )
    assert g5["status"] == "G5_F12_CLOSED_REJECTED_OFFLINE_REMEDIATION_PREPARATION_ONLY"
    assert current["status"] == "G5_F12_V8_LINEAGE_ISSUED_PROVIDER_AUTHORIZATION_PENDING"
    assert report["decision"]["status"] == "COMPLETED_REJECTED_HARD_GATE"
    assert report["accounting"]["providerCallsAttempted"] == 144
    assert report["accounting"]["retryCount"] == 0
    assert transition["currentDecisionState"]["authorizationSpent"] is True

    common_locks = (
        "providerExecutionAuthorized",
        "validationAccessAuthorized",
        "heldOutAccessAuthorized",
        "stageBAuthorized",
        "candidateSelectionAuthorized",
        "promotionAuthorized",
    )
    for artifact in (decision["decision"], transition["currentDecisionState"]):
        for name in common_locks:
            assert artifact[name] is False
        assert artifact["offlineRemediationPreparationAuthorized"] is True
    for name in (
        "providerExecutionAuthorized",
        "heldOutAccessAuthorized",
        "stageBAuthorized",
        "candidateSelectionAuthorized",
        "promotionAuthorized",
        "retryAuthorized",
        "outputOverwriteAuthorized",
        "validationAuthorized",
    ):
        assert g5["authorizationBoundary"][name] is False
    assert g5["authorizationBoundary"]["offlineRemediationPreparationAuthorized"] is True

    assert g5["selection"] == {
        "status": "NO_SELECTION",
        "candidateAvailable": False,
        "candidateFreezeAuthorized": False,
        "reason": "S12-f-12 is closed rejected by RM-27 after hard, threshold and slice gate failures.",
    }
    assert current["experimentState"]["candidateSelection"] == "NO_SELECTION"
    assert current["nextTasks"] == [
        "S12-RM-34_PREPARE_EXACT_V8_STAGE_A_AUTHORIZATION_OFFLINE",
        "S12-RM-35_OWNER_AUTHORIZATION_REVIEW",
    ]


def test_f12_stage_a_execution_transition_and_report_are_immutable_evidence() -> None:
    transition = _json(OPT / "s12-f-12-stage-a-execution-transition.v1.json")
    report_path = OPT / "s12-f-12-stage-a-report.v6.json"
    report = _json(report_path)
    assert transition["report"]["digest"] == _index_digest(report_path)
    assert transition["report"]["status"] == report["decision"]["status"]
    assert report["accounting"]["providerCallsAttempted"] == 144
    assert report["accounting"]["responsesReceived"] == 144
    assert report["accounting"]["retryCount"] == 0
    assert report["custody"]["rawProviderPayloadStored"] is False
    assert report["custody"]["rawSourceTextStored"] is False
    assert transition["governance"]["stageBAuthorized"] is False
    assert transition["governance"]["candidateSelectionAuthorized"] is False
    assert transition["governance"]["heldOutAccessAuthorized"] is False


def test_current_documents_do_not_repeat_superseded_statuses() -> None:
    sprint_plan = (DOCS.parent / "sprint-12.md").read_text(encoding="utf-8")
    global_plan = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    readme = (EVAL / "README.md").read_text(encoding="utf-8")
    handoffs = (DOCS / "agent-handoffs.md").read_text(encoding="utf-8")

    assert "sprint-12/current-state.md" in sprint_plan
    assert "sprint-12/g5-optimization.v21.md" in sprint_plan
    assert "G5_F12_V8_LINEAGE_ISSUED_PROVIDER_AUTHORIZATION_PENDING" in global_plan
    assert "CURRENT_F12_V8_ISSUED_PROVIDER_AUTHORIZATION_HANDOFF" in handoffs
    assert "Handoff A — Runtime-backed" not in handoffs

    stale_phrases = (
        "pending R12–R13",
        "R13 approval remains pending",
        "pending R15 freeze",
        "pending the separate G3.1-C",
        "G4 is approved only as a truthful no-run",
    )
    for phrase in stale_phrases:
        assert phrase not in readme


def test_historical_gate_packets_are_labeled_as_snapshots() -> None:
    historical = (
        "g2-annotation-pilot.md",
        "g3-dataset-freeze.md",
        "g4-baseline.md",
        "g5-optimization.md",
        "g5-optimization.v6.md",
        "g5-optimization.v7.md",
    )
    for name in historical:
        text = (DOCS / name).read_text(encoding="utf-8")
        assert "Historical gate snapshot" in text
        assert "current-state.md" in text or "g5-optimization.v17.md" in text
