"""Focused state and custody checks for S12-RM-65."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "evaluation/sprint-12"
SUMMARY = ROOT / "docs/sprint-plans/sprint-12/artifacts/task_S12-RM-65_summary.md"


def test_rm65_accepts_offline_telemetry_and_opens_rm66() -> None:
    current = json.loads((EVAL / "current-state.v1.json").read_text(encoding="utf-8"))
    assert current["status"] == "F_RF_POC_BASELINE_ACCEPTED_DENSE_HARD_V4_FAILED_STRATEGY_REDESIGN_REQUIRED"
    evidence = current["currentEvidence"]["rm65CorrectionBurdenTelemetry"]
    assert evidence["contractVersion"] == "correction-burden.v1"
    assert evidence["rawContentStored"] is False
    assert evidence["mutableTotalsAccepted"] is False
    assert evidence["productionAuthorization"] is False
    governance = current["experimentState"]["currentGovernance"]
    assert governance["correctionBurdenTelemetryContractAccepted"] is True
    assert governance["correctionBurdenTelemetryEnabledByDefault"] is False
    assert governance["correctionBurdenTelemetryProductionAuthorization"] is False
    assert current["nextTasks"] == [
        "DENSE_HARD_V4_STRATEGY_REDESIGN_REQUIRES_NEW_AUTHORITY"
    ]


def test_rm65_summary_states_safe_event_boundary_and_deferred_postgres_test() -> None:
    summary = SUMMARY.read_text(encoding="utf-8")
    for phrase in (
        "correction-burden.v1",
        "append-only",
        "opaque",
        "No raw source",
        "mutable totals",
            "RM-66 was the next permitted gate",
    ):
        assert phrase in summary
