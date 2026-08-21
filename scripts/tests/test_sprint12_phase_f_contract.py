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


def test_s12_77_stage_a_is_preregistered_without_execution() -> None:
    prereg = json.loads(
        (
            ROOT
            / "evaluation/sprint-12/optimization/s12-77-model-preregistration.v1.json"
        ).read_text(encoding="utf-8")
    )
    assert prereg["status"] == "PREREGISTERED_NOT_EXECUTED"
    assert prereg["experimentId"] == "s12-f-05"
    assert prereg["candidateModel"] is None
    assert prereg["candidateModelSelectionRequired"] is True
    assert prereg["executionAuthorized"] is False
    assert prereg["stageA"]["caseCount"] == 16
    assert prereg["stageA"]["independentRunsPerModel"] == 3
    assert prereg["stageA"]["noRetryWithinEachRun"] is True
    assert {"s12-a-0153", "s12-a-0187"}.issubset(
        prereg["stageA"]["caseIds"]
    )
    assert prereg["stageA"]["hardGates"] == {
        "schema_invalid": 0,
        "invalid_evidence": 0,
        "missing_output": 0,
        "provenance": "no regression",
        "isolation": "no regression",
        "safety": "no regression",
    }


def test_s12_77_stage_a_result_keeps_stage_b_locked_and_registry_v3_valid() -> None:
    stage = json.loads(
        (
            ROOT / "evaluation/sprint-12/optimization/s12-77-model-stage-a.v1.json"
        ).read_text(encoding="utf-8")
    )
    assert stage["status"] == "STAGE_A_COMPLETED"
    assert stage["decision"] == "STAGE_A_NOT_ELIGIBLE_FOR_STAGE_B"
    assert stage["stageBAuthorized"] is False
    assert stage["candidate"]["model"] == "deepseek-v4-pro"
    assert stage["candidate"]["aggregateFailureCounts"] == {
        "cross_project_link": 1,
        "schema_invalid": 2,
    }
    assert stage["accounting"]["costAccountingStatus"] == (
        "NOT_AVAILABLE_PROVIDER_PRICE_CONFIGURATION"
    )
    registry = json.loads(
        (
            ROOT / "evaluation/sprint-12/optimization/experiment-registry.v3.json"
        ).read_text(encoding="utf-8")
    )
    MODULE.validate_registry(registry)
    experiment = next(
        item for item in registry["experiments"] if item["experimentId"] == "s12-f-05"
    )
    assert experiment["status"] == "COMPLETED_STAGE_A_NOT_ELIGIBLE_FOR_STAGE_B"
    registry_targeted = experiment["executionEvidence"]["targetedDiagnostic"]
    targeted_path = (
        ROOT / "evaluation/sprint-12/optimization/s12-77-targeted-diagnostics.v1.json"
    )
    targeted_digest = "sha256:" + hashlib.sha256(targeted_path.read_bytes()).hexdigest()
    assert registry_targeted["digest"] == targeted_digest
    assert registry_targeted["failureCounts"] == {}
    packet = json.loads(
        (ROOT / "evaluation/sprint-12/optimization/g5-packet.v3.json").read_text(
            encoding="utf-8"
        )
    )
    assert packet["stageBAuthorized"] is False
    assert packet["selection"]["status"] == "NO_SELECTION"
    targeted = packet["candidateEvidence"]["targetedDiagnostic"]
    assert targeted["artifact"] == "s12-77-targeted-diagnostics.v1.json"
    assert targeted["caseIds"] == ["s12-a-0121", "s12-a-0176"]
    assert targeted["status"] == "DIAGNOSTIC_COMPLETED"
    assert targeted["failureCounts"] == {}
    assert targeted["digest"] == targeted_digest


def test_s12_77_targeted_diagnostic_is_sanitized_and_no_retry() -> None:
    diagnostic = json.loads(
        (
            ROOT
            / "evaluation/sprint-12/optimization/s12-77-targeted-diagnostics.v1.json"
        ).read_text(encoding="utf-8")
    )
    assert diagnostic["status"] == "DIAGNOSTIC_COMPLETED"
    assert diagnostic["experimentId"] == "s12-f-05"
    assert diagnostic["model"] == "deepseek-v4-pro"
    assert diagnostic["caseIds"] == ["s12-a-0121", "s12-a-0176"]
    assert diagnostic["protocol"] == {
        "independentRunCount": 1,
        "oneAttemptPerCase": True,
        "noRetryWithinEachRun": True,
        "promptVariant": "m3.prompt.v3.supersession-guard",
        "samplingConfiguration": {
            "seed": "provider-controlled",
            "temperature": "provider-default",
            "topP": "provider-default",
        },
    }
    assert diagnostic["rawSensitiveDataIncluded"] is False
    assert diagnostic["credentialIncluded"] is False
    for outcome in diagnostic["outcomes"]:
        assert "rawText" not in outcome
        assert "sourceText" not in outcome
        assert "outputText" not in outcome
        assert "text" not in outcome


def test_s12_f06_sampling_experiment_is_preregistered_and_not_authorized() -> None:
    prereg = json.loads(
        (
            ROOT
            / "evaluation/sprint-12/optimization/s12-f-06-sampling-preregistration.v1.json"
        ).read_text(encoding="utf-8")
    )
    assert prereg["status"] == "PREREGISTERED_NOT_EXECUTED"
    assert prereg["experimentId"] == "s12-f-06"
    assert prereg["dimension"] == "sampling"
    assert prereg["executionAuthorized"] is False
    assert prereg["stageA"]["caseCount"] == 8
    assert prereg["stageA"]["independentRunsPerVariant"] == 3
    assert prereg["stageA"]["noRetryWithinEachRun"] is True
    assert prereg["control"]["configuration"]["model"] == "deepseek-v4-pro"
    assert prereg["candidate"]["configuration"]["model"] == "deepseek-v4-pro"
    assert (
        prereg["control"]["configuration"]["samplingConfiguration"]["temperature"]
        == "provider-default"
    )
    assert prereg["candidate"]["configuration"]["samplingConfiguration"] == {
        "temperature": 0.0,
        "topP": 1.0,
        "seed": "provider-controlled",
    }
    registry = json.loads(
        (
            ROOT / "evaluation/sprint-12/optimization/experiment-registry.v4.json"
        ).read_text(encoding="utf-8")
    )
    MODULE.validate_registry(registry)
    experiment = next(
        item for item in registry["experiments"] if item["experimentId"] == "s12-f-06"
    )
    assert experiment["status"] == "REGISTERED"
    assert experiment["changedArtifacts"] == ["sampling"]
    prereg_digest = "sha256:" + hashlib.sha256(
        (
            ROOT
            / "evaluation/sprint-12/optimization/s12-f-06-sampling-preregistration.v1.json"
        ).read_bytes()
    ).hexdigest()
    assert experiment["executionEvidence"]["digest"] == prereg_digest
    packet = json.loads(
        (ROOT / "evaluation/sprint-12/optimization/g5-packet.v4.json").read_text(
            encoding="utf-8"
        )
    )
    assert packet["pendingExperimentId"] == "s12-f-06"
    assert packet["pendingExperiment"]["executionAuthorized"] is False
    assert packet["stageBAuthorized"] is False


def test_s12_f06_stage_a_result_rejects_candidate_and_binds_v5_evidence() -> None:
    stage = json.loads(
        (
            ROOT
            / "evaluation/sprint-12/optimization/s12-f-06-sampling-stage-a.v1.json"
        ).read_text(encoding="utf-8")
    )
    assert stage["status"] == "STAGE_A_COMPLETED"
    assert stage["decision"] == "STAGE_A_NOT_ELIGIBLE_FOR_STAGE_B"
    assert stage["stageBAuthorized"] is False
    assert stage["control"]["aggregateFailureCounts"] == {"schema_invalid": 1}
    assert stage["candidate"]["aggregateFailureCounts"] == {}
    assert stage["candidate"]["aggregateMissingOutputCount"] == 0
    assert stage["comparison"]["semanticGates"] == {
        "entityMacroF1": False,
        "abstentionAccuracy": False,
        "hallucinationRate": True,
        "relationMacroF1": False,
    }
    assert stage["accounting"]["costAccountingStatus"] == (
        "NOT_AVAILABLE_PROVIDER_PRICE_CONFIGURATION"
    )
    authorization = json.loads(
        (
            ROOT
            / "evaluation/sprint-12/optimization/s12-f-06-sampling-authorization.v1.json"
        ).read_text(encoding="utf-8")
    )
    assert authorization["status"] == "APPROVED_FOR_DEVELOPMENT_STAGE_A"
    registry = json.loads(
        (
            ROOT / "evaluation/sprint-12/optimization/experiment-registry.v5.json"
        ).read_text(encoding="utf-8")
    )
    MODULE.validate_registry(registry)
    experiment = next(
        item for item in registry["experiments"] if item["experimentId"] == "s12-f-06"
    )
    assert experiment["status"] == "COMPLETED_STAGE_A_NOT_ELIGIBLE_FOR_STAGE_B"
    assert experiment["executionEvidence"]["decision"] == stage["decision"]
    assert experiment["executionEvidence"]["candidateHardGates"] == "PASS"
    assert experiment["executionEvidence"]["controlHardGates"] == "FAIL"
    assert experiment["executionEvidence"]["comparisonIntegrity"] == (
        "DEGRADED_UNEQUAL_VALID_OUTPUTS"
    )
    packet = json.loads(
        (ROOT / "evaluation/sprint-12/optimization/g5-packet.v5.json").read_text(
            encoding="utf-8"
        )
    )
    assert packet["executedExperimentId"] == "s12-f-06"
    assert packet["selection"]["status"] == "NO_SELECTION"
    assert packet["stageBAuthorized"] is False
    assert packet["candidateHardGates"] == "PASS"
    assert packet["controlHardGates"] == "FAIL"
    assert packet["comparisonIntegrity"] == "DEGRADED_UNEQUAL_VALID_OUTPUTS"


def test_s12_f06_erratum_separates_hard_gates_and_derives_common_metrics() -> None:
    erratum = json.loads(
        (
            ROOT / "evaluation/sprint-12/optimization/s12-f-06-sampling-erratum.v1.json"
        ).read_text(encoding="utf-8")
    )
    assert erratum["status"] == "ERRATUM_ISSUED_WITHOUT_RERUN"
    assert erratum["candidateHardGates"] == "PASS"
    assert erratum["controlHardGates"] == "FAIL"
    assert erratum["comparisonIntegrity"] == "DEGRADED_UNEQUAL_VALID_OUTPUTS"
    assert erratum["commonCaseMetrics"]["caseExecutionCount"] == 23
    assert erratum["commonCaseMetrics"]["caseCountByRun"] == {
        "run-01": 7,
        "run-02": 8,
        "run-03": 8,
    }
    metrics = erratum["commonCaseMetrics"]["metrics"]
    assert metrics["entityMacroF1"]["delta"] < -0.05
    assert metrics["abstentionAccuracy"]["delta"] < -0.05
    assert metrics["relationMacroF1"]["delta"] <= 0
    assert erratum["decision"] == "STAGE_A_NOT_ELIGIBLE_FOR_STAGE_B"


def test_phase_f_plan_stops_at_g5_approval_gate() -> None:
    plan = (ROOT / "docs/sprint-plans/sprint-12.md").read_text(encoding="utf-8")
    packet = (ROOT / "docs/sprint-plans/sprint-12/g5-optimization.md").read_text(
        encoding="utf-8"
    )
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


def test_phase_f_plan_inserts_g31_remediation_before_candidate_selection() -> None:
    plan = (ROOT / "docs/sprint-plans/sprint-12.md").read_text(encoding="utf-8")
    assert "Status: `G5_F12_CORRECTED_V9_LINEAGE_ISSUED_PROVIDER_AUTHORIZATION_PENDING`" in plan
    assert "[x] **S12-R01" in plan
    assert "[x] **S12-R02" in plan
    assert "[x] **S12-R03" in plan
    assert "[x] **S12-R04" in plan
    assert "[x] **S12-R05" in plan
    assert "[x] **S12-R06" in plan
    assert "[x] **S12-R07" in plan
    assert "[x] **S12-R08" in plan
    assert "[x] **S12-R09" in plan
    assert "[x] **S12-R10" in plan
    assert "[x] **S12-R11" in plan
    assert "[x] **S12-R12" in plan
    assert "[x] **S12-R13" in plan
    assert "[x] **S12-R14" in plan
    assert "[x] **S12-R15" in plan
    assert "[x] **S12-R16" in plan
    assert "[x] **S12-R17" in plan
    assert "[x] **S12-R18" in plan
    assert "[x] **S12-R19" in plan
    assert "[x] **S12-R20" in plan
    for number in range(21, 24):
        assert f"[x] **S12-R{number:02d}" in plan
    assert "[ ] **S12-R24" in plan
    assert "G3.1-A — Measurement" in plan
    assert "G3.1-B — Deep pilot" in plan
    assert "G3.1-C — Dataset freeze" in plan
    assert "G5-R Stage A" in plan
    assert plan.index("S12-f-08 preparation") < plan.index("S12-R01")
    assert plan.index("[x] **S12-R23") < plan.index("[ ] **S12-78")
    assert plan.index("[ ] **S12-R24") < plan.index("[ ] **S12-85")
