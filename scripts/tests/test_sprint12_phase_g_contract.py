"""Contract and adversarial self-tests for the Sprint 12 Phase G harness."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sprint12_heldout", ROOT / "scripts/sprint12_heldout.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def custody() -> dict:
    return json.loads(
        (
            ROOT / "evaluation/sprint-12/corpus/manifests/test-custody.manifest.v1.json"
        ).read_text(encoding="utf-8")
    )


def protocol() -> dict:
    return {
        "reviewerCount": 3,
        "scenarioCount": 12,
        "targetRoles": ["BrSE", "project-manager", "semantic-reviewer"],
        "independentAnnotation": True,
        "blindedOrder": True,
        "manualBaseline": {"counterbalanced": True, "sameReviewers": True},
    }


def test_custody_verification_fails_closed_for_repository_manifest() -> None:
    result = MODULE.verify_test_custody(custody())
    assert result["status"] == "CUSTODY_NOT_ESTABLISHED"
    assert result["payloadPresent"] is False
    assert "custody status is not established" in result["failures"]


def test_reviewer_protocol_requires_three_reviewers_and_twelve_scenarios() -> None:
    MODULE.validate_reviewer_protocol(protocol())
    broken = protocol()
    broken["reviewerCount"] = 2
    with pytest.raises(MODULE.HeldoutError, match="three qualified reviewers"):
        MODULE.validate_reviewer_protocol(broken)


def test_preregistration_is_blocked_without_frozen_candidate_or_custody() -> None:
    result = MODULE.preregister_run(
        candidate=None,
        evaluator_digest="sha256:" + "a" * 64,
        metrics=["trust"],
        thresholds={},
        reviewer_protocol=protocol(),
        abort_conditions=["mismatch"],
        custody={"status": "CUSTODY_NOT_ESTABLISHED"},
    )
    assert result["status"] == "PREREGISTRATION_BLOCKED"
    assert result["heldOutInspected"] is False
    assert set(result["blockers"]) == {
        "no frozen candidate",
        "test custody is not verified",
    }


def test_blinded_run_and_review_records_fail_explicitly_when_blocked() -> None:
    run = MODULE.execute_blinded_run({"status": "PREREGISTRATION_BLOCKED"})
    assert run["status"] == "BLINDED_RUN_BLOCKED"
    review = MODULE.capture_review_records([], scenario_count=12)
    manual = MODULE.capture_manual_baseline([], scenario_count=12)
    assert review["status"] == "REVIEW_INCOMPLETE"
    assert manual["status"] == "MANUAL_BASELINE_INCOMPLETE"


def test_review_and_manual_baseline_reject_raw_sensitive_fields() -> None:
    with pytest.raises(MODULE.HeldoutError, match="raw sensitive data"):
        MODULE.capture_review_records([{"comment": "secret"}], scenario_count=1)
    with pytest.raises(MODULE.HeldoutError, match="raw sensitive data"):
        MODULE.capture_manual_baseline([{"sourceText": "secret"}], scenario_count=1)


def test_gap_taxonomy_and_integrity_are_finite_and_digest_bound() -> None:
    assert (
        MODULE.classify_ontology_gap({"category": "ontology-change-candidate"})
        == "ontology-change-candidate"
    )
    with pytest.raises(MODULE.HeldoutError, match="unknown ontology-gap category"):
        MODULE.classify_ontology_gap({"category": "unknown"})
    integrity = MODULE.verify_evidence_integrity(
        custody={}, preregistration={}, run={}, reviewer={}, manual={}
    )
    assert integrity["status"] == "EVIDENCE_BLOCKED"
    assert len(integrity["componentDigests"]) == 5


def test_g6_packet_makes_no_business_quality_claim() -> None:
    blocked = {"status": "BLOCKED"}
    packet = MODULE.build_g6_packet(
        blocked,
        blocked,
        blocked,
        blocked,
        blocked,
        {"status": "UTILITY_NOT_AVAILABLE"},
        [],
        blocked,
    )
    assert packet["status"] == "G6_PREPARATION_BLOCKED_CUSTODY_OR_CANDIDATE"
    assert packet["heldOutEvidence"] is False
    assert packet["boundedClaim"] is None
    assert packet["businessApproval"] == "PENDING_HUMAN_APPROVAL"


def test_phase_g_plan_stops_at_g6_approval_gate() -> None:
    plan = (ROOT / "docs/sprint-plans/sprint-12.md").read_text(encoding="utf-8")
    assert "Status: `G6_PREPARATION_BLOCKED_CUSTODY_OR_CANDIDATE`" in plan
    assert "[x] **S12-84" in plan
    assert "[x] **S12-92" in plan
    assert "[ ] **S12-93" in plan
    for number in range(84, 94):
        summary = (
            ROOT
            / f"docs/sprint-plans/sprint-12/artifacts/task_S12-{number:02d}_summary.md"
        )
        assert summary.exists(), summary
        assert "## Testing" in summary.read_text(encoding="utf-8")
