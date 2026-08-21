"""Contract tests for the S12 v3 pilot annotation and adjudication packet."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / "evaluation/sprint-12/corpus/v3/gold-adjudication.v1.json"

SPEC = importlib.util.spec_from_file_location(
    "adjudicate_sprint12_v3_pilot", ROOT / "scripts/adjudicate_sprint12_v3_pilot.py"
)
assert SPEC is not None and SPEC.loader is not None
ADJUDICATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ADJUDICATOR
SPEC.loader.exec_module(ADJUDICATOR)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_pilot_packet_is_owner_ai_adjudicated_without_human_evidence() -> None:
    packet = read_json(PACKET)
    assert packet["schemaVersion"] == "s12.v3.pilot-adjudication.v1"
    assert packet["status"] == "ANNOTATED_ADJUDICATED_OWNER_DELEGATED_AI_PENDING_QUALITY_GATE"
    assert packet["integrity"] == {"passed": True, "errors": []}
    assert packet["humanEvidence"] is False
    assert packet["qualifiedHumanEvidence"] is False
    assert packet["rawSensitiveDataIncluded"] is False
    assert packet["reviewSummary"] == {
        "atomicCaseCount": 48,
        "scenarioCount": 6,
        "materialDisputeCount": 0,
        "independentHumanReviewPerformed": False,
        "thirdReviewerRequired": False,
        "goldChangedAfterPilotAuthoring": False,
    }
    assert len(packet["caseDecisions"]) == 48
    assert len(packet["scenarioDecisions"]) == 6


def test_pilot_coverage_is_explicit_and_relation_positive_enough_for_gate() -> None:
    coverage = read_json(PACKET)["coverage"]
    assert coverage["caseCounts"] == {"development": 32, "validation": 16}
    assert coverage["languageCounts"] == {"en": 20, "ja": 2, "mixed": 8, "vi": 18}
    assert coverage["relationPositiveCases"] == 15
    assert coverage["relationCount"] == 15
    assert coverage["abstentionRequiredCases"] == 6
    assert coverage["entityTypeCounts"] == {
        "Constraint": 3,
        "Decision": 6,
        "ProgressClaim": 5,
        "Question": 7,
        "Requirement": 12,
        "Risk": 9,
        "Task": 16,
    }
    assert coverage["relationPredicateCounts"] == {
        "answers": 1,
        "blocks": 5,
        "constrainedBy": 3,
        "dependsOn": 2,
        "implements": 3,
        "supports": 1,
    }


def test_adjudicator_rejects_tampered_span_and_abstention() -> None:
    dataset = read_json(ROOT / "evaluation/sprint-12/corpus/v3/atomic-deep-pilot.v1.json")
    case = copy.deepcopy(dataset["cases"][0])
    case["gold"]["entities"][0]["span"]["text"] = "tampered"
    assert ADJUDICATOR._validate_case(case)

    abstention = copy.deepcopy(dataset["cases"][7])
    abstention["gold"]["abstention"]["reason"] = None
    assert ADJUDICATOR._validate_case(abstention)
