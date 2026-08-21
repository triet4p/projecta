"""Contract tests for the R14 v3 scale track."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCALE = ROOT / "evaluation/sprint-12/corpus/v3-scale"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ADJ = load_module("s12_scale_adjudicator", ROOT / "scripts/adjudicate_sprint12_v3_pilot.py")
GATE = load_module("s12_scale_gate", ROOT / "scripts/sprint12_v3_pilot_quality_gate.py")
LEAKAGE = load_module("s12_scale_leakage", ROOT / "scripts/sprint12_leakage_validator.py")
SCENARIO = load_module("s12_scale_scenario", ROOT / "scripts/sprint12_scenario_validator.py")


def read_json(name: str) -> dict:
    return json.loads((SCALE / name).read_text(encoding="utf-8"))


def test_scale_has_lineage_disjoint_visible_split_and_no_test_payload() -> None:
    atomic = read_json("atomic-scale.v1.json")
    atomic_manifest = read_json("manifest-scale.v1.json")
    scenario_manifest = read_json("scenario-manifest-scale.v1.json")
    assert atomic["datasetVersion"] == "s12.corpus.atomic.v3.scale"
    assert len(atomic["cases"]) == 208
    assert atomic_manifest["atomicCounts"] == {"development": 160, "validation": 48, "test": 0, "total": 208}
    assert scenario_manifest["scenarioCounts"] == {"development": 20, "validation": 6, "test": 0, "total": 26}
    assert atomic_manifest["testPayloadPresent"] is False
    assert scenario_manifest["testPayloadPresent"] is False
    lineages = {case["scenarioId"]: case["split"] for case in atomic["cases"]}
    assert len(lineages) == 26
    assert all(case["split"] == lineages[case["scenarioId"]] for case in atomic["cases"])


def test_scale_preserves_natural_variation_relation_depth_and_language_policy() -> None:
    atomic = read_json("atomic-scale.v1.json")
    cases = atomic["cases"]
    assert len({case["source"]["rawText"] for case in cases}) == 208
    serialized = json.dumps(atomic, ensure_ascii=False)
    assert "Evidence marker" not in serialized
    assert "distinguishing phrase" not in serialized
    assert sum(bool(case["gold"]["relations"]) for case in cases) == 52
    assert sum(case["gold"]["abstention"]["required"] for case in cases) == 26
    assert {case["source"]["language"] for case in cases} == {"en", "vi", "ja", "mixed"}
    assert GATE._language_gate(cases)["pass"] is True
    assert LEAKAGE.analyze_atomic_cases(cases)["pass"] is True


def test_scale_gold_spans_and_scenarios_are_integrity_bound() -> None:
    atomic = read_json("atomic-scale.v1.json")
    scenarios = read_json("scenario-scale.v1.json")
    errors = [error for case in atomic["cases"] for error in ADJ._validate_case(case)]
    assert errors == []
    assert SCENARIO.analyze_scenarios(scenarios["scenarios"])["pass"] is True
    assert LEAKAGE.analyze_scenarios(scenarios["scenarios"])["pass"] is True
    assert all(len(scenario["events"]) == 8 for scenario in scenarios["scenarios"])
    assert all([checkpoint["afterSequence"] for checkpoint in scenario["checkpoints"]] == [2, 4, 6, 8] for scenario in scenarios["scenarios"])
