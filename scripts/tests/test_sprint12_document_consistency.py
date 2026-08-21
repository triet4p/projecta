from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "evaluation" / "sprint-12"
OPT = EVAL / "optimization"
DOCS = ROOT / "docs" / "sprint-plans" / "sprint-12"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


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


def test_current_state_and_g5_packet_agree() -> None:
    current = _json(EVAL / "current-state.v1.json")
    g5 = _json(OPT / "g5-packet.v12.json")

    expected = "G5_F12_ISSUED_PROVIDER_AUTHORIZATION_PENDING"
    assert current["status"] == expected
    assert g5["status"] == expected
    assert current["experimentState"]["candidateSelection"] == "NO_SELECTION"
    assert g5["selection"]["status"] == "NO_SELECTION"
    assert current["experimentState"]["providerExecutionAuthorized"] is False
    assert g5["activeExperiment"]["providerExecutionAuthorized"] is False
    assert current["experimentState"]["heldOutInspected"] is False
    assert g5["authorizationBoundary"]["heldOutAccessAuthorized"] is False


def test_current_documents_do_not_repeat_superseded_statuses() -> None:
    sprint_plan = (DOCS.parent / "sprint-12.md").read_text(encoding="utf-8")
    global_plan = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    readme = (EVAL / "README.md").read_text(encoding="utf-8")
    handoffs = (DOCS / "agent-handoffs.md").read_text(encoding="utf-8")

    assert "sprint-12/current-state.md" in sprint_plan
    assert "sprint-12/g5-optimization.v12.md" in sprint_plan
    assert "G5_F12_ISSUED_PROVIDER_AUTHORIZATION_PENDING" in global_plan
    assert "CURRENT_RM24_RM25_AUTHORIZATION_AND_EXECUTION_HANDOFFS" in handoffs
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
        assert "current-state.md" in text or "g5-optimization.v12.md" in text
