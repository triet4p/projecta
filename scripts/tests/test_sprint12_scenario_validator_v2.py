"""Contract tests for Sprint 12 scenario semantic consistency validation."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sprint12_scenario_validator", ROOT / "scripts/sprint12_scenario_validator.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

CORPUS = ROOT / "evaluation/sprint-12/corpus"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_historical_v2_fixture_reports_unexplained_lineage_conflicts() -> None:
    report = MODULE.validate_paths(
        CORPUS / "scenario-development-validation.v2.json",
        CORPUS / "manifest.v2.json",
    )
    assert report["reportVersion"] == "s12.scenario-validator.v2"
    assert report["status"] == "BLOCKED_SCENARIO_INCONSISTENCY"
    assert report["analysis"]["payloadScenarioCount"] == 18
    assert report["analysis"]["uniqueSourceLineageCount"] == 6
    assert len(report["analysis"]["repeatedSourceLineageGroups"]) == 6
    assert len(report["analysis"]["unresolvedConflictGroups"]) == 6
    assert all(
        "temporalEffects" in row["unresolvedConflictingDimensions"]
        and "reviewDispositions" in row["unresolvedConflictingDimensions"]
        for row in report["analysis"]["unresolvedConflictGroups"]
    )
    assert report["gates"]["longitudinalBusinessReady"] is False
    assert report["readScope"]["testPayloadRead"] is False

    serialized = json.dumps(report, ensure_ascii=False)
    assert "rawText" not in serialized
    assert "expectedTemporalEffect" not in serialized


def test_rationale_can_explain_a_repeated_lineage() -> None:
    base = {
        "scenarioId": "s-a",
        "split": "development",
        "sourceManifest": ["a-1"],
        "events": [
            {
                "caseId": "a-1",
                "sequence": 1,
                "expectedTemporalEffect": "creates",
                "expectedReview": {"disposition": "confirmed"},
            }
        ],
        "checkpoints": [{"afterSequence": 1, "assertedIds": ["fact-a"]}],
        "competencyAnswers": [{"questionId": "CQ-1", "status": "answerable"}],
    }
    variant = json.loads(json.dumps(base))
    variant["scenarioId"] = "s-b"
    variant["events"][0]["expectedTemporalEffect"] = "updates"
    variant["semanticVariationRationale"] = "The second episode records a later revision."
    result = MODULE.analyze_scenarios([base, variant])
    assert result["pass"] is True
    assert result["unresolvedConflictGroups"] == []


def test_shape_and_test_custody_guards_fail_closed() -> None:
    malformed = {
        "scenarioId": "s-bad",
        "split": "development",
        "sourceManifest": ["a-1"],
        "events": [{"caseId": "other", "sequence": 2}],
        "checkpoints": [],
        "competencyAnswers": [],
    }
    result = MODULE.analyze_scenarios([malformed])
    assert result["pass"] is False
    assert result["shapeErrors"]

    sealed = dict(malformed)
    sealed["split"] = "test"
    with pytest.raises(MODULE.ScenarioValidationError, match="held-out"):
        MODULE.analyze_scenarios([sealed])
