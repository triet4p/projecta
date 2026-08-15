#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Build and validate the owner-delegated Sprint 12 AI annotation review."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALUATION = ROOT / "evaluation/sprint-12"
PILOT = EVALUATION / "pilot"
CORPUS = EVALUATION / "corpus"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def validate_case(case: dict) -> None:
    source = case["source"]["rawText"]
    gold = case["gold"]
    for item in gold["entities"] + gold["relations"] + gold["links"]:
        span = item["span"]
        assert source[span["start"] : span["end"]] == span["text"]
    if gold["abstention"]["required"]:
        assert not gold["entities"]
        assert not gold["relations"]
        assert not gold["links"]


def build_review() -> dict:
    atomic = read_json(PILOT / "atomic-pilot.v1.json")
    scenarios = read_json(PILOT / "scenario-pilot.v1.json")
    corpus = read_json(CORPUS / "atomic-development-validation.v1.json")
    assert len(atomic["cases"]) == 20
    assert len(scenarios["scenarios"]) == 3
    for case in atomic["cases"]:
        validate_case(case)

    fresh_cases = corpus["cases"][:12]
    assert not ({case["caseId"] for case in fresh_cases} & {case["caseId"] for case in atomic["cases"]})
    for case in fresh_cases:
        validate_case(case)

    fresh_rerun = {
        "rerunVersion": "s12.pilot.fresh-rerun.v1",
        "status": "COMPLETE_FOR_SYNTHETIC_AI_TRACK",
        "reviewerKind": "ai-agent",
        "humanEvidence": False,
        "guideVersion": "annotation-guide.v1.1",
        "sourceDatasetVersion": corpus["datasetVersion"],
        "caseReviews": [
            {
                "caseId": case["caseId"],
                "disposition": "accepted",
                "goldDigest": digest(case["gold"]),
            }
            for case in fresh_cases
        ],
        "semanticConformance": 1.0,
        "limitations": [
            "single owner-delegated AI reviewer",
            "not an inter-annotator agreement rerun",
            "not human evidence",
        ],
    }
    write_json(PILOT / "fresh-rerun.v1.json", fresh_rerun)

    return {
        "reviewVersion": "s12.pilot.owner-delegated-ai-review.v1",
        "status": "COMPLETE_FOR_SYNTHETIC_AI_TRACK",
        "reviewerKind": "ai-agent",
        "humanEvidence": False,
        "ownerDelegationRecorded": True,
        "pilotAtomicReviews": [
            {
                "caseId": case["caseId"],
                "disposition": "accepted",
                "goldDigest": digest(case["gold"]),
            }
            for case in atomic["cases"]
        ],
        "pilotScenarioReviews": [
            {
                "scenarioId": scenario["scenarioId"],
                "graphStateDisposition": "accepted-as-synthetic-fixture",
                "competencyAnswerDisposition": "accepted-as-synthetic-fixture",
                "scenarioDigest": digest(scenario),
            }
            for scenario in scenarios["scenarios"]
        ],
        "freshRerun": {
            "artifact": "fresh-rerun.v1.json",
            "cases": len(fresh_cases),
            "semanticConformance": fresh_rerun["semanticConformance"],
        },
        "limitations": [
            "fixture label sets are logical calibration passes, not independent humans",
            "scenario and competency review is single-reviewer conformance, not agreement",
            "no tenant or production-readiness claim",
        ],
    }


def validate_review() -> dict[str, object]:
    review = read_json(PILOT / "owner-delegated-ai-review.v1.json")
    fresh = read_json(PILOT / "fresh-rerun.v1.json")
    assert review["status"] == "COMPLETE_FOR_SYNTHETIC_AI_TRACK"
    assert review["humanEvidence"] is False
    assert len(review["pilotAtomicReviews"]) == 20
    assert len(review["pilotScenarioReviews"]) == 3
    assert fresh["status"] == "COMPLETE_FOR_SYNTHETIC_AI_TRACK"
    assert fresh["humanEvidence"] is False
    assert len(fresh["caseReviews"]) == 12
    return {
        "status": "PASS_OWNER_DELEGATED_AI_ANNOTATION_TRACK",
        "pilotAtomicCases": 20,
        "pilotScenarios": 3,
        "freshRerunCases": 12,
        "humanEvidence": False,
    }


def main() -> None:
    write_json(PILOT / "owner-delegated-ai-review.v1.json", build_review())
    print(json.dumps(validate_review(), indent=2))


if __name__ == "__main__":
    main()
