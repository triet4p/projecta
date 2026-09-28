"""Focused state and custody checks for S12-RM-64."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "evaluation/sprint-12"
SUMMARY = ROOT / "docs/sprint-plans/sprint-12/artifacts/task_S12-RM-64_summary.md"


def test_rm64_transitions_to_correction_burden_without_runtime_enablement() -> None:
    current = json.loads((EVAL / "current-state.v1.json").read_text(encoding="utf-8"))
    assert current["status"] == "F_RF_POC_BASELINE_ACCEPTED_DENSE_HARD_V4_FAILED_STRATEGY_REDESIGN_REQUIRED"
    evidence = current["currentEvidence"]["rm64InferenceInvalidationRebuild"]
    assert evidence["contractVersion"] == "inference-rebuild-plan.v1"
    assert evidence["rebuildEnabledByDefault"] is False
    assert evidence["productionAuthorization"] is False
    governance = current["experimentState"]["currentGovernance"]
    assert governance["inferenceInvalidationRebuildContractAccepted"] is True
    assert governance["inferenceRebuildEnabledByDefault"] is False
    assert current["nextTasks"] == ["DENSE_HARD_V4_STRATEGY_REDESIGN_REQUIRES_NEW_AUTHORITY"]


def test_rm64_summary_binds_stale_historical_and_atomic_guards() -> None:
    summary = SUMMARY.read_text(encoding="utf-8")
    for phrase in (
        "finite allowlist",
        "stale before rebuild",
        "historical",
        "one Jena",
        "Exact replays",
        "RM-65 remains the sole",
    ):
        assert phrase in summary
