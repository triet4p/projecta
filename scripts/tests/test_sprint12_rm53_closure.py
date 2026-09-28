"""Focused custody and governance checks for S12-RM-53."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from jsonschema import validate

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "evaluation/sprint-12"
OPT = EVAL / "optimization"
HARNESS = EVAL / "harness"
DECISION = OPT / "s12-f-12-rm53-owner-decision.v1.json"
TRANSITION = OPT / "s12-f-12-rm53-decision-transition.v1.json"


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _git_blob_digest(path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"HEAD:{path}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return f"sha256:{hashlib.sha256(result.stdout).hexdigest()}"


def test_rm53_decision_and_transition_validate_closed_schemas() -> None:
    validate(_json(DECISION), _json(HARNESS / "s12-f-12-rm53-owner-decision.schema.v1.json"))
    validate(
        _json(TRANSITION),
        _json(HARNESS / "s12-f-12-rm53-decision-transition.schema.v1.json"),
    )


def test_rm53_binds_rm52_rm51_custody_and_absent_v8() -> None:
    decision = _json(DECISION)
    reviewed = decision["reviewedArtifacts"]
    assert isinstance(reviewed, dict)
    refs = (
        ("rm52Closure", "evaluation/sprint-12/optimization/s12-f-12-rm52-offline-closure.v1.json"),
        ("rm52Backlog", "evaluation/sprint-12/optimization/s12-f-12-rm52-error-backlog.v1.json"),
        ("rm51OwnerDecision", "evaluation/sprint-12/optimization/s12-f-12-rm51-owner-decision.v1.json"),
        ("rm51Transition", "evaluation/sprint-12/optimization/s12-f-12-rm51-decision-transition.v1.json"),
        ("v6Report", "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json"),
        ("v9Report", "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v9.json"),
        ("v8Execution", "evaluation/sprint-12/optimization/s12-f-12-rm36-execution-transition.v1.json"),
        ("rm51CurrentPacket", "evaluation/sprint-12/optimization/g5-packet.v36.rm51-closure-only.json"),
    )
    for key, relative_path in refs:
        reference = reviewed[key]
        assert reference["path"] == relative_path
        assert reference["digest"] == _digest(ROOT / relative_path)

    for key, schema_relative_path in (
        (
            "rm52Closure",
            "evaluation/sprint-12/harness/s12-f-12-rm52-offline-closure.schema.v1.json",
        ),
        (
            "rm52Backlog",
            "evaluation/sprint-12/harness/s12-f-12-rm52-error-backlog.schema.v1.json",
        ),
    ):
        assert reviewed[key]["schemaDigest"] == _digest(ROOT / schema_relative_path)
        assert reviewed[key]["schemaPath"] == schema_relative_path
        assert reviewed[key]["testPath"] == "scripts/tests/test_sprint12_rm52_closure.py"

    assert _json(ROOT / reviewed["rm52Closure"]["path"])["governance"]["providerCalls"] == 0
    assert _json(ROOT / reviewed["rm52Backlog"]["path"])["governance"]["providerCalls"] == 0
    rm51 = _json(ROOT / reviewed["rm51Transition"]["path"])
    for key in (
        "providerExecutionAuthorized",
        "runtimeRemediationImplementationAuthorized",
        "validationAccessAuthorized",
        "heldOutAccessAuthorized",
        "stageBAuthorized",
        "candidateSelectionAuthorized",
        "promotionAuthorized",
    ):
        assert rm51["currentDecisionState"][key] is False

    assert reviewed["v8Report"] == {
        "path": "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v8.json",
        "exists": False,
        "digest": None,
    }
    assert not (ROOT / reviewed["v8Report"]["path"]).exists()
    assert reviewed["currentStateBeforeTransition"]["digest"] == _git_blob_digest(
        "evaluation/sprint-12/current-state.v1.json"
    )


def test_rm53_keeps_all_execution_and_business_claims_closed() -> None:
    decision = _json(DECISION)
    transition = _json(TRANSITION)
    verification = decision["verification"]
    selected = decision["decision"]
    current = transition["currentDecisionState"]
    assert verification["providerCallsInRm52"] == 0
    assert verification["providerExperimentationStopped"] is True
    assert verification["humanBusinessEvidencePresent"] is False
    assert selected["humanBusinessQualityClaim"] is False
    for state in (selected, current):
        for key in (
            "runtimeImplementationAuthorized",
            "providerExecutionAuthorized",
            "validationAccessAuthorized",
            "heldOutAccessAuthorized",
            "stageBAuthorized",
            "candidateSelectionAuthorized",
            "promotionAuthorized",
        ):
            assert state[key] is False
    assert transition["nextPermittedAction"] == (
        "S12-RM-54_REVIEW_HUMAN_FIRST_EXTRACTION_FRAMEWORK_DESIGN"
    )


def test_rm53_current_state_remains_bound_after_rm54_transition() -> None:
    current = _json(EVAL / "current-state.v1.json")
    assert current["status"] == "F_RF_POC_BASELINE_ACCEPTED_DENSE_HARD_V4_FAILED_STRATEGY_REDESIGN_REQUIRED"
    assert current["nextTasks"] == [
        "DENSE_HARD_V4_STRATEGY_REDESIGN_REQUIRES_NEW_AUTHORITY",
    ]
    assert current["currentEvidence"]["rm53OwnerDecision"]["digest"] == _digest(DECISION)
    assert current["currentEvidence"]["rm53DecisionTransition"]["digest"] == _digest(TRANSITION)
    governance = current["experimentState"]["currentGovernance"]
    assert governance["offlineClosureDocumentationAuthorized"] is False
    assert governance["errorBacklogPreparationAuthorized"] is False
    assert governance["humanFirstDesignReviewAuthorized"] is False
    assert governance["nextPermittedAction"] == (
        "DENSE_HARD_V4_STRATEGY_REDESIGN_REQUIRES_NEW_AUTHORITY"
    )

    plan = (ROOT / "docs/sprint-plans/sprint-12.md").read_text(encoding="utf-8")
    assert "[x] **S12-RM-53" in plan
    assert "[x] **S12-RM-54" in plan
    assert "[x] **S12-RM-55" in plan
    assert "[x] **S12-RM-56" in plan
    assert "human-first-extraction-framework.v2.md" in plan

    for path in (
        ROOT / "docs/PLAN.md",
        ROOT / "docs/sprint-plans/sprint-12/current-state.md",
        ROOT / "evaluation/sprint-12/README.md",
        ROOT / "docs/sprint-plans/sprint-12/agent-handoffs.md",
    ):
        text = path.read_text(encoding="utf-8")
        assert "RM-53 owner review is pending" not in text
        assert "RM-53 must review the closure" not in text
