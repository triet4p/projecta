from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "evaluation" / "sprint-12"
OPT = EVAL / "optimization"


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


OWNER = OPT / "s12-f-12-rm31-owner-review.v1.json"
TRANSITION = OPT / "s12-f-12-rm31-approval-transition.v1.json"
CURRENT = EVAL / "current-state.v1.json"
G5 = OPT / "g5-packet.v23.rm35-authorization.json"
REPORT = OPT / "s12-f-12-stage-a-report.v6.json"


def test_rm31_owner_transition_binds_immutable_inputs() -> None:
    owner = _json(OWNER)
    transition = _json(TRANSITION)
    assert transition["ownerReview"]["digest"] == _digest(OWNER)
    assert transition["ownerReview"]["status"] == owner["status"]
    for evidence in (
        owner["reviewedEvidence"]["rm30Package"],
        owner["reviewedEvidence"]["diagnosticReport"],
        owner["reviewedEvidence"]["diagnosticReportSchema"],
    ):
        assert evidence["digest"] == _digest(ROOT / evidence["path"])
    assert owner["reviewedEvidence"]["immutableReport"]["digest"] == _digest(REPORT)
    assert owner["reviewedEvidence"]["immutableReport"]["providerCalls"] == 144
    assert owner["reviewedEvidence"]["immutableReport"]["retryCount"] == 0


def test_rm31_current_state_and_g5_open_preparation_only() -> None:
    current = _json(CURRENT)
    g5 = _json(G5)
    assert current["status"] == g5["status"]
    assert current["currentEvidence"]["g5Packet"]["path"] == G5.relative_to(ROOT).as_posix()
    assert current["currentEvidence"]["remediationImplementationOwnerReview"]["path"] == OWNER.relative_to(ROOT).as_posix()
    assert current["currentEvidence"]["remediationImplementationApprovalTransition"]["path"] == TRANSITION.relative_to(ROOT).as_posix()
    historical = current["experimentState"]["historicalLineage"]
    assert historical["lineageVersion"] == "v7"
    assert historical["preregistrationIssued"] is True
    assert historical["technicalFreezeIssued"] is True
    assert historical["providerCallsPerformed"] == 144
    governance = g5["authorizationBoundary"]
    for key in (
        "supersedingLineagePreparationAuthorized",
        "preregistrationPreparationAuthorized",
        "technicalFreezePreparationAuthorized",
        "executionPackagePreparationAuthorized",
    ):
        assert governance[key] is True
    for key in (
        "validationAuthorized",
        "validationAccessAuthorized",
        "heldOutAccessAuthorized",
        "stageBAuthorized",
        "candidateSelectionAuthorized",
        "promotionAuthorized",
    ):
        assert governance[key] is False
    assert governance["providerExecutionAuthorized"] is True
    assert governance["newAuthorizationIssued"] is True
    assert governance["authorizedExecutions"] == 1
    assert governance["authorizedProviderCalls"] == 144
    assert governance["providerCallsPerformed"] == 0
    assert governance["preregistrationIssued"] is True
    assert governance["technicalFreezeIssued"] is True
    assert current["nextTasks"] == [
        "S12-RM-36_EXECUTE_EXACT_V8_STAGE_A_ONCE",
        "S12-RM-37_OWNER_POST_RUN_DECISION",
    ]
