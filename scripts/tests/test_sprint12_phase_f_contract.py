"""Contract and adversarial self-tests for the Sprint 12 Phase F harness."""

import hashlib
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
    assert registry["status"] == "G5_PREPARATION_DEVELOPMENT_OPEN"
    assert registry["permittedSplits"] == ["development"]
    assert [item["dimension"] for item in registry["experiments"]] == [
        "prompt",
        "context",
        "agent-workflow",
        "tool",
        "model",
    ]
    assert all(item["status"] == "REGISTERED" for item in registry["experiments"])


def test_persisted_registry_v2_passes_executable_validator() -> None:
    registry = json.loads(
        (
            ROOT / "evaluation/sprint-12/optimization/experiment-registry.v2.json"
        ).read_text(encoding="utf-8")
    )
    assert registry["registryVersion"] == MODULE.REGISTRY_VERSION == (
        "s12.experiment-registry.v2"
    )
    MODULE.validate_registry(registry)


def test_registry_preserves_missing_runtime_boundary() -> None:
    report = baseline()
    report["status"] = "NOT_EXECUTED_MISSING_RUNTIME_CONFIGURATION"
    registry = MODULE.build_default_registry(report)
    assert registry["status"] == "G5_PREPARATION_BLOCKED_BASELINE_UNAVAILABLE"
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
        "caseCount": 1,
        "caseCoverage": [{"caseId": "case-1", "status": "scored"}],
        "omittedCaseCount": 0,
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
    assert packet["status"] == "G5_PREPARATION_DEVELOPMENT_OPEN"
    assert packet["selection"]["status"] == "NO_SELECTION"
    assert packet["optimizationAuthorized"] is False
    assert packet["developmentExperimentsAuthorized"] is True
    assert packet["heldOutInspected"] is False
    assert packet["rawSensitiveDataIncluded"] is False


def test_g41_summary_counts_are_derived_from_candidate_operational_accounting() -> None:
    packet = json.loads(
        (
            ROOT / "evaluation/sprint-12/baseline/g4.1-contract-alignment.v1.json"
        ).read_text(encoding="utf-8")
    )
    candidate = json.loads(
        (
            ROOT
            / "evaluation/sprint-12/optimization/contract-candidate-v2-stability/runs/run-03.report.v1.json"
        ).read_text(encoding="utf-8")
    )
    historical = packet["historicalContractEvidence"]
    assert historical["evidenceScope"] == "historicalContractEvidence"
    summary = historical["summary"]
    counts = candidate["operational"]["failureCounts"]
    assert summary["derivedFromOperationalAccounting"] is True
    assert summary["schemaInvalidCount"] == counts.get("schema_invalid", 0)
    assert summary["invalidEvidenceCount"] == counts.get("invalid_evidence", 0)
    assert historical["contractCandidate"]["schemaInvalidCount"] == counts.get(
        "schema_invalid", 0
    )
    assert historical["contractCandidate"]["invalidEvidenceCount"] == counts.get(
        "invalid_evidence", 0
    )


def test_stability_gate_remains_closed_after_three_no_retry_runs() -> None:
    stability = json.loads(
        (
            ROOT
            / "evaluation/sprint-12/optimization/contract-candidate-v2-stability.v2.json"
        ).read_text(encoding="utf-8")
    )
    assert stability["status"] == "STABILITY_GATE_FAIL"
    assert stability["independentRunCount"] == 3
    assert stability["totalCaseExecutions"] == 96
    assert stability["fixedModelConfiguration"] is True
    assert stability["noRetryWithinEachRun"] is True
    assert stability["aggregateFailureCounts"] == {
        "schema_invalid": 7,
        "invalid_evidence": 4,
    }
    packet = json.loads(
        (
            ROOT / "evaluation/sprint-12/baseline/g4.1-contract-alignment.v1.json"
        ).read_text(encoding="utf-8")
    )
    historical = packet["historicalContractEvidence"]
    assert historical["stabilityGate"]["derivedFromArtifact"] is True
    assert historical["stabilityGate"]["aggregateFailureCounts"] == stability[
        "aggregateFailureCounts"
    ]
    assert packet["currentPromptExperimentEvidence"]["evidenceScope"] == (
        "currentPromptExperimentEvidence"
    )


def test_s12_73_persists_each_run_and_keeps_empty_link_metric_non_promotional() -> None:
    experiment = json.loads(
        (
            ROOT
            / "evaluation/sprint-12/optimization/s12-73-prompt-supersession.v1.json"
        ).read_text(encoding="utf-8")
    )
    assert experiment["candidateSchemaEvidenceClean"] is True
    assert experiment["semanticMetricsImproved"] is True
    assert experiment["linkMetricUsable"] is False
    assert experiment["goldPositiveLinkCount"] == 0
    for variant in ("baseline", "candidate"):
        runs = experiment[variant]["runs"]
        assert len(runs) == 3
        assert len({run["reportDigest"] for run in runs}) == 3
        for run in runs:
            report_path = ROOT / run["reportPath"]
            assert report_path.exists()
            actual = "sha256:" + hashlib.sha256(report_path.read_bytes()).hexdigest()
            assert actual == run["reportDigest"]

    followup = json.loads(
        (
            ROOT
            / "evaluation/sprint-12/optimization/s12-73-prompt-followup-stability.v2.json"
        ).read_text(encoding="utf-8")
    )
    assert followup["status"] == "STABILITY_GATE_FAIL"
    assert followup["totalCaseExecutions"] == 96
    assert followup["aggregateFailureCounts"] == {
        "schema_invalid": 3,
        "invalid_evidence": 0,
    }
    for run in followup["runs"]:
        report_path = ROOT / run["reportPath"]
        assert report_path.exists()
        actual = "sha256:" + hashlib.sha256(report_path.read_bytes()).hexdigest()
        assert actual == run["reportDigest"]


def test_s12_73_registry_and_g5_packet_bind_completed_failed_execution() -> None:
    registry = json.loads(
        (
            ROOT
            / "evaluation/sprint-12/optimization/experiment-registry.v2.json"
        ).read_text(encoding="utf-8")
    )
    experiment = next(
        item for item in registry["experiments"] if item["experimentId"] == "s12-f-01"
    )
    assert experiment["status"] == "COMPLETED_STABILITY_FAILED"
    assert experiment["protocolVariance"] is True
    assert experiment["executionProtocol"] == {
        "initialCasesPerVariant": 8,
        "initialIndependentRunsPerVariant": 3,
        "followupCaseCount": 32,
        "followupIndependentRunCount": 3,
        "retryPolicy": "none",
        "noRetryWithinEachRun": True,
    }
    packet = json.loads(
        (
            ROOT / "evaluation/sprint-12/optimization/g5-packet.v2.json"
        ).read_text(encoding="utf-8")
    )
    assert packet["candidateAvailable"] is True
    assert packet["comparisons"]["s12-f-01"]["status"] == (
        "REJECTED_CANDIDATE_HARD_INVARIANT"
    )
    assert packet["hardInvariants"]["status"] == "FAIL"
    assert packet["candidateEvidence"]["failureCounts"] == {
        "schema_invalid": 3,
        "invalid_evidence": 0,
    }
    assert packet["selection"]["status"] == "NO_SELECTION"
    diagnostic = json.loads(
        (
            ROOT
            / "evaluation/sprint-12/optimization/s12-73-targeted-diagnostics.v1.json"
        ).read_text(encoding="utf-8")
    )
    assert diagnostic["caseIds"] == ["s12-a-0153", "s12-a-0187"]
    assert diagnostic["protocol"]["independentRunCount"] == 1
    assert diagnostic["protocol"]["noRetryWithinEachRun"] is True
    assert diagnostic["rawSensitiveDataIncluded"] is False
    assert diagnostic["credentialIncluded"] is False
    assert diagnostic["failureCounts"] == {}
    for outcome in diagnostic["outcomes"]:
        assert "rawText" not in outcome
        assert "sourceText" not in outcome
    assert packet["candidateEvidence"]["targetedDiagnostic"]["status"] == (
        "DIAGNOSTIC_COMPLETED"
    )


def test_phase_f_plan_stops_at_g5_approval_gate() -> None:
    plan = (ROOT / "docs/sprint-plans/sprint-12.md").read_text(encoding="utf-8")
    packet = (ROOT / "docs/sprint-plans/sprint-12/g5-optimization.md").read_text(
        encoding="utf-8"
    )
    assert "Status: `G6_PREPARATION_BLOCKED_CUSTODY_OR_CANDIDATE`" in plan
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
