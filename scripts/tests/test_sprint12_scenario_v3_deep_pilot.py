"""Contract tests for the authored Sprint 12 scenario v3 deep pilot."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "evaluation/sprint-12/corpus/v3/scenario-deep-pilot.v1.json"
MANIFEST = ROOT / "evaluation/sprint-12/corpus/v3/scenario-manifest.v1.json"
ATOMIC = ROOT / "evaluation/sprint-12/corpus/v3/atomic-deep-pilot.v1.json"

SPEC = importlib.util.spec_from_file_location(
    "sprint12_scenario_validator", ROOT / "scripts/sprint12_scenario_validator.py"
)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def test_scenario_pilot_has_six_unique_lineages_and_split_custody() -> None:
    dataset = read_json(SCENARIO)
    manifest = read_json(MANIFEST)
    atomic = read_json(ATOMIC)
    scenarios = dataset["scenarios"]
    atomic_ids = {case["caseId"] for case in atomic["cases"]}
    assert dataset["datasetVersion"] == "s12.corpus.scenario.v3.deep-pilot"
    assert len(scenarios) == 6
    assert manifest["scenarioCounts"] == {
        "development": 4,
        "validation": 2,
        "test": 0,
        "total": 6,
    }
    assert len({tuple(scenario["sourceManifest"]) for scenario in scenarios}) == 6
    assert all(set(scenario["sourceManifest"]) <= atomic_ids for scenario in scenarios)
    assert all(scenario["split"] in {"development", "validation"} for scenario in scenarios)
    assert manifest["testPayloadPresent"] is False


def test_each_episode_has_chronology_actors_updates_conflict_and_questions() -> None:
    dataset = read_json(SCENARIO)
    for scenario in dataset["scenarios"]:
        events = scenario["events"]
        assert len(events) == 8
        assert [event["sequence"] for event in events] == list(range(1, 9))
        assert all(event["expectedReview"].get("rationale") for event in events)
        assert {event["expectedTemporalEffect"] for event in events} >= {
            "creates",
            "updates",
        }
        assert any(event["expectedTemporalEffect"] == "contradicts" for event in events)
        assert [checkpoint["afterSequence"] for checkpoint in scenario["checkpoints"]] == [
            2,
            4,
            6,
            8,
        ]
        assert scenario["checkpoints"][2]["contradictionIds"]
        assert len(scenario["competencyAnswers"]) == 2
        assert {answer["status"] for answer in scenario["competencyAnswers"]} == {
            "answerable",
            "ambiguous",
        }


def test_scenario_pilot_passes_consistency_shape_and_digest_checks() -> None:
    dataset = read_json(SCENARIO)
    manifest = read_json(MANIFEST)
    analysis = VALIDATOR.analyze_scenarios(dataset["scenarios"])
    assert analysis["pass"] is True
    assert analysis["shapeErrors"] == []
    assert analysis["repeatedSourceLineageGroups"] == []
    entries = {entry["scenarioId"]: entry for entry in manifest["scenarios"]}
    for scenario in dataset["scenarios"]:
        assert entries[scenario["scenarioId"]]["scenarioDigest"] == digest(scenario)
    serialized = json.dumps(dataset, ensure_ascii=False)
    assert "Evidence marker" not in serialized
    assert "distinguishing phrase" not in serialized
