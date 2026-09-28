"""Focused state and custody checks for S12-RM-63."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "evaluation/sprint-12"
SUMMARY = ROOT / "docs/sprint-plans/sprint-12/artifacts/task_S12-RM-63_summary.md"


def _current() -> dict[str, object]:
    return json.loads((EVAL / "current-state.v1.json").read_text(encoding="utf-8"))


def test_rm63_transitions_to_inference_invalidation_without_enablement() -> None:
    current = _current()
    assert current["status"] == "F_RF_POC_BASELINE_ACCEPTED_DENSE_HARD_V4_FAILED_STRATEGY_REDESIGN_REQUIRED"
    evidence = current["currentEvidence"]["rm64InferenceInvalidationRebuild"]
    assert evidence["contractVersion"] == "inference-rebuild-plan.v1"
    assert evidence["rebuildEnabledByDefault"] is False
    assert evidence["productionAuthorization"] is False
    assert current["experimentState"]["currentGovernance"]["inferenceInvalidationRebuildContractAccepted"] is True
    assert current["experimentState"]["currentGovernance"]["inferenceRebuildEnabledByDefault"] is False
    assert current["nextTasks"] == ["DENSE_HARD_V4_STRATEGY_REDESIGN_REQUIRES_NEW_AUTHORITY"]


def test_rm63_summary_preserves_closed_authority_boundary() -> None:
    summary = SUMMARY.read_text(encoding="utf-8")
    for phrase in (
        "one Jena",
        "idempotent replay",
        "disabled by default",
        "no production enablement",
        "RM-64 remains",
    ):
        assert phrase in summary
