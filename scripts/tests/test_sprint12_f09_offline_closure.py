"""Regression coverage for the offline-only S12-f-09 closure."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/issue_sprint12_f09_closure.py"
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("s12_f09_closure", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _scored_case(*, gold: int, predicted: int, exact: int, wrong_span: int) -> dict:
    return {
        "status": "scored",
        "entities": {"f1": 0.0},
        "abstentionAccuracy": 1.0,
        "hallucinationRate": 0.0,
        "relationInstrumentation": {
            "status": "scored",
            "totals": {
                "gold": gold,
                "predicted": predicted,
                "exactMatch": exact,
                "wrongSpan": wrong_span,
            },
        },
    }


def test_pooled_evidence_ratios_use_summed_denominators() -> None:
    cases = [
        (
            _scored_case(gold=1, predicted=1, exact=1, wrong_span=0),
            {"relations": [], "abstention": {"required": False}},
        ),
        (
            _scored_case(gold=3, predicted=3, exact=0, wrong_span=2),
            {"relations": [], "abstention": {"required": False}},
        ),
    ]
    metrics = MODULE._aggregate(cases)
    assert metrics["relationEvidenceSupportTruePositive"] == 3
    assert metrics["relationSemanticTruePositive"] == 3
    assert metrics["relationEvidenceSupport"] == 1.0
    assert metrics["relationEvidenceExact"] == 1 / 3


def test_missing_output_retains_gold_relation_denominator() -> None:
    case = {
        "status": "missing-output",
        "relations": {"gold": 1, "predicted": 0},
        "entities": {"f1": 0.0},
        "abstentionAccuracy": 0.0,
        "hallucinationRate": 0.0,
        "relationInstrumentation": {"status": "not-available"},
    }
    metric = MODULE.case_metric(case)
    assert metric["semanticGold"] == 1
    assert metric["semanticPredicted"] == 0
    assert metric["semanticTruePositive"] == 0


def test_f09_v3_and_g5_v11_are_digest_bound_and_no_selection() -> None:
    report = json.loads(MODULE.REPORT_V3.read_text(encoding="utf-8"))
    registry = json.loads(MODULE.REGISTRY_V11.read_text(encoding="utf-8"))
    packet = json.loads(MODULE.G5_V11.read_text(encoding="utf-8"))
    assert report["executionCount"] == 288
    assert report["attemptedCaseRuns"] == 288
    assert report["candidate"]["primaryMetrics"]["validCaseRuns"] == 141
    assert report["control"]["primaryMetrics"]["validCaseRuns"] == 136
    assert report["decision"] == "STAGE_A_NOT_ELIGIBLE_FOR_STAGE_B"
    assert (
        report["measurement"]["comparisonIntegrity"]
        == "DEGRADED_INDEPENDENT_STOCHASTIC_OUTPUTS"
    )
    assert registry["registryVersion"] == "s12.experiment-registry.v11"
    assert registry["selection"]["status"] == "NO_SELECTION"
    assert packet["registryDigest"] == registry["registryDigest"]
    assert packet["selection"]["status"] == "NO_SELECTION"
    assert packet["completedExperiment"]["offlineRepairV2Artifact"] == (
        "s12-f-09-relation-evidence-stage-a.v2.json"
    )
    assert len(packet["completedExperiment"]["reports"]) == 6


def test_evaluator_missing_output_preserves_relation_instrumentation() -> None:
    evaluator_path = ROOT / "scripts/sprint12_evaluator.py"
    spec = importlib.util.spec_from_file_location(
        "s12_evaluator_f09_regression", evaluator_path
    )
    assert spec is not None and spec.loader is not None
    evaluator = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = evaluator
    spec.loader.exec_module(evaluator)
    gold = {
        "entities": [],
        "relations": [
            {
                "predicate": "supports",
                "sourceEntityId": "s",
                "targetEntityId": "t",
                "span": {"start": 0, "end": 5},
            }
        ],
        "links": [],
        "abstention": {"required": False},
    }
    result = evaluator.score_extraction(gold, None, ["supports"])
    assert result["status"] == "missing-output"
    assert result["relationInstrumentation"]["status"] == "scored"
    assert result["relationInstrumentation"]["totals"]["gold"] == 1
