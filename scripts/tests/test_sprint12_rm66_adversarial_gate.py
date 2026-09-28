"""Machine-state and immutable-custody checks for S12-RM-66."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "evaluation/sprint-12"
SUMMARY = ROOT / "docs/sprint-plans/sprint-12/artifacts/task_S12-RM-66_summary.md"
STATUS = "F_RF_POC_BASELINE_ACCEPTED_DENSE_HARD_V4_FAILED_STRATEGY_REDESIGN_REQUIRED"
NEXT = "DENSE_HARD_V4_STRATEGY_REDESIGN_REQUIRES_NEW_AUTHORITY"


def test_rm66_accepts_adversarial_gate_and_preserves_internal_poc_boundary() -> None:
    current = json.loads((EVAL / "current-state.v1.json").read_text(encoding="utf-8"))
    assert current["status"] == STATUS
    evidence = current["currentEvidence"]["rm66OfflineAdversarialGate"]
    assert evidence["contractVersion"] == "rm66-offline-adversarial-gate.v1"
    assert evidence["providerCalls"] == 0
    assert evidence["productionAuthorization"] is False
    assert evidence["humanEvidence"] is False
    assert current["experimentState"]["currentGovernance"]["offlineAdversarialTestingAccepted"] is True
    assert current["experimentState"]["currentGovernance"]["nextPermittedAction"] == NEXT
    assert current["nextTasks"] == [NEXT]


def test_rm66_binds_immutable_reports_and_absent_v8() -> None:
    expected = {
        "s12-f-12-stage-a-report.v6.json": "419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233",
        "s12-f-12-stage-a-report.v9.json": "84cb0667b8ee3469be5bdd4c3545a41012ba46bb07071508c41dca76fbf3761e",
    }
    paths = [EVAL / "optimization" / name for name in expected]
    assert {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths} == expected
    assert not (EVAL / "optimization/s12-f-12-stage-a-report.v8.json").exists()


def test_rm66_summary_records_environment_skip_and_non_claims() -> None:
    summary = SUMMARY.read_text(encoding="utf-8")
    for phrase in (
        "offline test evidence only",
        "no connector PostgreSQL configuration",
        "not a pass",
        "zero provider calls",
        "RM-67 is the sole",
        "no test path writes evaluation artifacts",
    ):
        assert phrase in summary
