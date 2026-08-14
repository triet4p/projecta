"""Contract and adversarial self-tests for the Sprint 12 Phase F harness."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sprint12_optimization", ROOT / "scripts/sprint12_optimization.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def baseline() -> dict:
    return json.loads(
        (ROOT / "evaluation/sprint-12/baseline/baseline-report.v1.json").read_text(
            encoding="utf-8"
        )
    )


def test_default_registry_is_development_only_and_has_five_dimensions() -> None:
    registry = MODULE.build_default_registry(baseline())
    assert registry["status"] == "G5_PREPARATION_BLOCKED_BASELINE_UNAVAILABLE"
    assert registry["permittedSplits"] == ["development"]
    assert [item["dimension"] for item in registry["experiments"]] == [
        "prompt",
        "context",
        "agent-workflow",
        "tool",
        "model",
    ]
    assert all(
        item["status"] == "NOT_EXECUTED_BASELINE_UNAVAILABLE"
        for item in registry["experiments"]
    )


def test_registry_rejects_test_split_and_multi_dimension_change() -> None:
    registry = MODULE.build_default_registry(baseline())
    broken = dict(registry["experiments"][0])
    broken["permittedSplit"] = "validation"
    with pytest.raises(MODULE.OptimizationError, match="not development-only"):
        MODULE.validate_experiment(broken)
    broken = dict(registry["experiments"][0])
    broken["changedArtifacts"] = ["prompt", "model"]
    with pytest.raises(MODULE.OptimizationError, match="more than one dimension"):
        MODULE.validate_experiment(broken)


def test_hard_invariant_regression_rejects_weakened_candidate() -> None:
    result = MODULE.hard_invariant_regression(
        {"safety": True, "provenance": True}, {"safety": True, "provenance": False}
    )
    assert result == {
        "status": "FAIL",
        "regressions": ["provenance"],
        "checked": ["provenance", "safety"],
    }


def test_comparison_and_selection_fail_closed_without_scored_runs() -> None:
    comparison = MODULE.compare_results(
        {"status": "NOT_EXECUTED"},
        {"status": "SCORED"},
        {"semanticQuality": {"direction": "higher", "minimumDelta": 0.01}},
    )
    assert comparison["status"] == "NOT_EXECUTED_BASELINE_UNAVAILABLE"
    selection = MODULE.select_candidate({"s12-f-01": comparison})
    assert selection["status"] == "NO_SELECTION"
    assert selection["heldOutInspected"] is False


def test_scored_comparison_requires_hard_invariants_and_metric_target() -> None:
    target = {"semanticQuality": {"direction": "higher", "minimumDelta": 0.01}}
    baseline_run = {
        "status": "SCORED",
        "hardInvariants": {"safety": True},
        "metrics": {"semanticQuality": 0.80},
    }
    candidate_run = {
        "status": "SCORED",
        "hardInvariants": {"safety": True},
        "metrics": {"semanticQuality": 0.82},
    }
    comparison = MODULE.compare_results(baseline_run, candidate_run, target)
    assert comparison["status"] == "PASS"
    candidate_run["hardInvariants"]["safety"] = False
    assert (
        MODULE.compare_results(baseline_run, candidate_run, target)["status"]
        == "REJECTED_HARD_INVARIANT"
    )


def test_freeze_requires_selected_executed_candidate() -> None:
    spec = MODULE.build_default_registry(baseline())["experiments"][0]
    result = MODULE.freeze_candidate(
        {"status": "SELECTED", "experimentId": "s12-f-01"}, spec
    )
    assert result["status"] == "NOT_FROZEN"


def test_g5_packet_has_no_candidate_and_no_optimization_unlock() -> None:
    report = baseline()
    registry = MODULE.build_default_registry(report)
    packet = MODULE.build_g5_packet(registry, report)
    assert packet["status"] == "G5_PREPARATION_BLOCKED_BASELINE_UNAVAILABLE"
    assert packet["selection"]["status"] == "NO_SELECTION"
    assert packet["optimizationAuthorized"] is False
    assert packet["heldOutInspected"] is False
    assert packet["rawSensitiveDataIncluded"] is False


def test_phase_f_plan_stops_at_g5_approval_gate() -> None:
    plan = (ROOT / "docs/sprint-plans/sprint-12.md").read_text(encoding="utf-8")
    packet = (ROOT / "docs/sprint-plans/sprint-12/g5-optimization.md").read_text(
        encoding="utf-8"
    )
    assert "Status: `G5_APPROVED_WITH_LIMITATIONS_G6_PENDING`" in plan
    assert "[x] **S12-72" in plan
    assert "[x] **S12-82" in plan
    assert "[x] **S12-83" in plan
    assert "`APPROVED_WITH_LIMITATIONS`" in packet
    for number in range(72, 84):
        summary = (
            ROOT
            / f"docs/sprint-plans/sprint-12/artifacts/task_S12-{number:02d}_summary.md"
        )
        assert summary.exists(), summary
        assert "## Testing" in summary.read_text(encoding="utf-8")
