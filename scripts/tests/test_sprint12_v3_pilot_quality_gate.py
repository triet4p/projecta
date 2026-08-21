"""Contract tests for the offline G3.1-B v3 pilot quality gate."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "evaluation/sprint-12/gates/g3.1-b-v3-pilot-quality.v1.json"

SPEC = importlib.util.spec_from_file_location(
    "sprint12_v3_pilot_quality_gate", ROOT / "scripts/sprint12_v3_pilot_quality_gate.py"
)
assert SPEC is not None and SPEC.loader is not None
GATE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = GATE
SPEC.loader.exec_module(GATE)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_v3_quality_gate_is_ready_without_authorizing_test_or_provider_access() -> None:
    report = read_json(REPORT)
    assert report["reportVersion"] == "s12.g31-b-v3-pilot-quality.v1"
    assert report["status"] == "V3_PILOT_QUALITY_READY"
    assert all(report["gates"].values())
    assert report["humanEvidence"] is False
    assert report["qualifiedHumanEvidence"] is False
    assert report["readScope"]["testPayloadRead"] is False
    assert report["readScope"]["atomicSplits"]["test"] == 0
    assert report["readScope"]["scenarioSplits"]["test"] == 0
    assert "rawText" not in json.dumps(report, ensure_ascii=False)


def test_v3_quality_gate_publishes_slice_coverage_not_only_total_counts() -> None:
    coverage = read_json(REPORT)["coverage"]
    assert coverage["caseCounts"] == {"development": 32, "validation": 16}
    assert coverage["relationPositiveCases"] == 15
    assert coverage["relationNegativeCases"] == 33
    assert coverage["abstentionRequiredCases"] == 6
    assert coverage["abstentionNotRequiredCases"] == 42
    assert set(coverage["businessJourneyCoverage"]) == {"J1", "J2", "J3", "J4", "J5", "J6"}
    assert all(row["caseCount"] == 8 for row in coverage["businessJourneyCoverage"].values())
    assert coverage["entityTypeCounts"]["Assumption"] == 0
    assert coverage["relationPredicateCounts"]["resolves"] == 0


def test_v3_quality_gate_detects_schema_and_language_regressions() -> None:
    atomic = read_json(ROOT / "evaluation/sprint-12/corpus/v3/atomic-deep-pilot.v1.json")
    scenarios = read_json(ROOT / "evaluation/sprint-12/corpus/v3/scenario-deep-pilot.v1.json")
    atomic["cases"][0]["schemaVersion"] = "tampered"
    assert GATE._schema_errors(atomic, scenarios)

    language_case = atomic["cases"][1]
    language_case["source"]["language"] = "mixed"
    assert not GATE._language_gate([language_case])["pass"]
