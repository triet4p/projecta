"""Contract tests for the execution-locked S12-f-09 preregistration."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "evaluation/sprint-12/optimization/s12-f-09-relation-evidence-preregistration.v1.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_f09_changes_only_the_tool_dimension_and_is_execution_locked() -> None:
    prereg = read_json(PREREG)
    control = prereg["control"]["configuration"]
    candidate = prereg["candidate"]["configuration"]
    assert prereg["experimentId"] == "s12-f-09"
    assert prereg["status"] == "PREREGISTERED_NOT_EXECUTED"
    assert prereg["executionAuthorized"] is False
    assert control.keys() == candidate.keys()
    assert {key for key in control if control[key] != candidate[key]} == {"tool"}
    assert control["model"] == candidate["model"] == "deepseek-v4-flash"
    assert control["promptVersion"] == candidate["promptVersion"] == "m3.prompt.v3.supersession-guard"
    assert candidate["tool"] == "server-owned-relation-evidence.v1"


def test_f09_binds_frozen_v3_metrics_pricing_and_paired_stage_a() -> None:
    prereg = read_json(PREREG)
    fixed = prereg["fixedArtifacts"]
    stage = prereg["stageA"]
    assert fixed["datasetVersion"] == "s12.corpus.atomic.v3.frozen"
    assert fixed["evaluator"] == "s12.evaluator.v4"
    assert fixed["schemaVersion"] == "m3.v2"
    assert fixed["retryPolicy"] == "none"
    assert stage["caseCount"] == 48
    assert stage["caseRunsPerArm"] == 144
    assert stage["independentPairedRuns"] == 3
    assert stage["oneAttemptPerCase"] is True
    assert stage["noRetryWithinEachRun"] is True
    assert len(stage["caseIds"]) == 48
    assert stage["relationPositiveCases"] == 12
    assert stage["abstentionRequiredCases"] == 6
    assert prereg["pricingContract"]["requiredBeforeExecution"] is True
    assert prereg["pricingContract"]["requiredBeforeSelection"] is True
    assert prereg["measurementContract"]["perCaseAndPerSliceDenominatorsRequired"] is True
    assert prereg["semanticGates"]["sliceFloorRequired"] is True


def test_f09_keeps_heldout_and_sweeps_prohibited() -> None:
    prereg = read_json(PREREG)
    assert prereg["heldOutInspected"] is False
    assert prereg["humanEvidence"] is False
    assert prereg["rawSensitiveDataIncluded"] is False
    assert {"prompt-sweep", "model-sweep", "sampling-sweep", "held-out-inspection", "retry"} <= set(prereg["prohibitedBeforeStageA"])
    assert prereg["relationTool"]["serverOutput"] == ["canonical entity spans", "deterministic clause/sentence evidence span"]
