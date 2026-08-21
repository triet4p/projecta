"""Contract checks for the completed, bounded S12-f-09 Stage A evidence."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPT = ROOT / "evaluation/sprint-12/optimization"


def _read(name: str) -> dict:
    return json.loads((OPT / name).read_text(encoding="utf-8"))


def test_f09_authorization_is_stage_a_only_and_heldout_closed() -> None:
    authorization = _read("s12-f-09-authorization.v1.json")
    assert authorization["status"] == "APPROVED_FOR_DEVELOPMENT_STAGE_A"
    assert authorization["providerExecutionAuthorized"] is True
    assert authorization["heldOutInspected"] is False
    assert authorization["stageBAuthorized"] is False
    assert authorization["retryAuthorized"] is False
    assert authorization["scope"]["caseCount"] == 48
    assert authorization["scope"]["caseRunsPerArm"] == 144


def test_f09_execution_preserves_288_runs_and_rejects_stage_b() -> None:
    report = _read("s12-f-09-relation-evidence-stage-a.v2.json")
    assert report["status"] == "STAGE_A_COMPLETED_OFFLINE_REPAIRED"
    assert report["decision"] == "STAGE_A_NOT_ELIGIBLE_FOR_STAGE_B"
    assert report["executionCount"] == 288
    assert report["stageBAuthorized"] is False
    assert report["heldOutInspected"] is False
    assert report["retryCount"] == 0
    assert report["candidate"]["primaryMetrics"]["relationSemanticMicroF1"] < 0.8
    assert report["candidate"]["primaryMetrics"]["relationEvidenceSupport"] == 1.0
    assert report["candidate"]["primaryMetrics"]["relationEvidenceExact"] == 1.0
    assert report["gates"]["candidateHardGate"] is False
    assert report["measurement"]["evidenceZeroDenominatorPolicy"] == "not-applicable"


def test_f09_has_six_immutable_run_reports() -> None:
    run_dir = OPT / "s12-f-09-relation-evidence-stage-a"
    reports = sorted(run_dir.glob("*.report.v1.json"))
    assert len(reports) == 6
    assert all(path.stat().st_size > 0 for path in reports)
