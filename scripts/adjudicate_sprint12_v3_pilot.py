#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Validate and publish the owner-delegated AI adjudication packet for S12 v3."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "evaluation/sprint-12/corpus/v3/gold-adjudication.v1.json"
ATOMIC_PATH = ROOT / "evaluation/sprint-12/corpus/v3/atomic-deep-pilot.v1.json"
ATOMIC_MANIFEST_PATH = ROOT / "evaluation/sprint-12/corpus/v3/manifest.v1.json"
SCENARIO_PATH = ROOT / "evaluation/sprint-12/corpus/v3/scenario-deep-pilot.v1.json"
SCENARIO_MANIFEST_PATH = ROOT / "evaluation/sprint-12/corpus/v3/scenario-manifest.v1.json"

ENTITY_TYPES = {
    "Requirement",
    "Decision",
    "Question",
    "Task",
    "Risk",
    "Assumption",
    "Constraint",
    "ProgressClaim",
    "ResearchFinding",
}
PREDICATES = {
    "implements",
    "blocks",
    "dependsOn",
    "supports",
    "answers",
    "resolves",
    "constrainedBy",
}


def _digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _span_error(text: str, span: dict[str, Any], label: str) -> str | None:
    start = span.get("start")
    end = span.get("end")
    value = span.get("text")
    if not isinstance(start, int) or not isinstance(end, int):
        return f"{label}: offsets must be integers"
    if start < 0 or end <= start or end > len(text):
        return f"{label}: offsets are outside the source"
    if text[start:end] != value:
        return f"{label}: stored text does not equal the source slice"
    return None


def _rule_ids(case: dict[str, Any]) -> list[str]:
    gold = case["gold"]
    rules = ["EVIDENCE.CODEPOINT_HALF_OPEN", "TYPE.RELEASED_M3"]
    if gold["relations"]:
        rules.extend(
            [
                "RELATION.RELEASED_PREDICATE",
                "RELATION.ENDPOINTS_LABELED",
                "RELATION.FULL_CLAUSE_EVIDENCE",
            ]
        )
    if gold["abstention"]["required"]:
        rules.append("ABSTENTION.EXPLICIT_UNCERTAINTY")
    else:
        rules.append("ABSTENTION.SUPPORTED_PROPOSAL")
    return rules


def _validate_case(case: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    source = case["source"]
    text = source["rawText"]
    expected_digest = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    if source["contentDigest"] != expected_digest:
        errors.append(f"{case['caseId']}: content digest mismatch")
    gold = case["gold"]
    entities = gold["entities"]
    entity_ids = [entity["id"] for entity in entities]
    if len(entity_ids) != len(set(entity_ids)):
        errors.append(f"{case['caseId']}: duplicate entity IDs")
    for entity in entities:
        if entity["type"] not in ENTITY_TYPES:
            errors.append(f"{case['caseId']}: unreleased entity type")
        error = _span_error(text, entity["span"], f"{case['caseId']} {entity['id']}")
        if error:
            errors.append(error)
        if entity.get("label") != entity["span"]["text"]:
            errors.append(f"{case['caseId']} {entity['id']}: label/span mismatch")
    for relation_index, relation in enumerate(gold["relations"], start=1):
        if relation["predicate"] not in PREDICATES:
            errors.append(f"{case['caseId']}: unreleased relation predicate")
        if relation["sourceEntityId"] not in entity_ids or relation["targetEntityId"] not in entity_ids:
            errors.append(f"{case['caseId']}: relation endpoint is not a labeled entity")
        if relation["sourceEntityId"] == relation["targetEntityId"]:
            errors.append(f"{case['caseId']}: self relation")
        error = _span_error(text, relation["span"], f"{case['caseId']} relation-{relation_index:02d}")
        if error:
            errors.append(error)
    abstention = gold["abstention"]
    if abstention["required"]:
        if not abstention.get("reason"):
            errors.append(f"{case['caseId']}: abstention reason is missing")
        if entities or gold["relations"] or gold["links"]:
            errors.append(f"{case['caseId']}: abstention has a non-empty proposal")
    elif abstention.get("reason") is not None:
        errors.append(f"{case['caseId']}: non-abstention has a reason")
    for gap in gold["semanticGaps"]:
        if not gap.get("rationale"):
            errors.append(f"{case['caseId']}: semantic gap rationale is missing")
    return errors


def _coverage(cases: list[dict[str, Any]]) -> dict[str, Any]:
    type_counts: Counter[str] = Counter()
    predicate_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    for case in cases:
        split_counts[case["split"]] += 1
        language_counts[case["source"]["language"]] += 1
        type_counts.update(entity["type"] for entity in case["gold"]["entities"])
        predicate_counts.update(relation["predicate"] for relation in case["gold"]["relations"])
    return {
        "caseCounts": dict(sorted(split_counts.items())),
        "languageCounts": dict(sorted(language_counts.items())),
        "entityTypeCounts": dict(sorted(type_counts.items())),
        "relationPredicateCounts": dict(sorted(predicate_counts.items())),
        "relationPositiveCases": sum(bool(case["gold"]["relations"]) for case in cases),
        "relationCount": sum(len(case["gold"]["relations"]) for case in cases),
        "abstentionRequiredCases": sum(case["gold"]["abstention"]["required"] for case in cases),
        "semanticGapCases": sum(bool(case["gold"]["semanticGaps"]) for case in cases),
    }


def build_packet() -> dict[str, Any]:
    atomic = json.loads(ATOMIC_PATH.read_text(encoding="utf-8"))
    atomic_manifest = json.loads(ATOMIC_MANIFEST_PATH.read_text(encoding="utf-8"))
    scenarios = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
    scenario_manifest = json.loads(SCENARIO_MANIFEST_PATH.read_text(encoding="utf-8"))
    cases = atomic["cases"]
    errors = [error for case in cases for error in _validate_case(case)]
    case_by_id = {case["caseId"]: case for case in cases}
    manifest_by_id = {entry["caseId"]: entry for entry in atomic_manifest["atomicCases"]}
    scenario_by_id = {scenario["scenarioId"]: scenario for scenario in scenarios["scenarios"]}
    scenario_decisions = []
    for entry in scenario_manifest["scenarios"]:
        scenario = scenario_by_id[entry["scenarioId"]]
        if entry["sourceManifest"] != scenario["sourceManifest"]:
            errors.append(f"{entry['scenarioId']}: source manifest mismatch")
        for event in scenario["events"]:
            if event["caseId"] not in case_by_id:
                errors.append(f"{entry['scenarioId']}: event references unknown case")
        scenario_decisions.append(
            {
                "scenarioId": entry["scenarioId"],
                "journeyId": entry["journeyId"],
                "split": entry["split"],
                "scenarioDigest": entry["scenarioDigest"],
                "reviewStatus": "adjudicated-no-change",
                "materialDispute": False,
            }
        )
    case_decisions = []
    for case in cases:
        manifest_entry = manifest_by_id[case["caseId"]]
        case_decisions.append(
            {
                "caseId": case["caseId"],
                "scenarioId": case["scenarioId"],
                "split": case["split"],
                "caseDigest": manifest_entry["caseDigest"],
                "goldDigest": _digest(case["gold"]),
                "ruleIds": _rule_ids(case),
                "reviewStatus": "adjudicated-no-change",
                "materialDispute": False,
            }
        )
    return {
        "schemaVersion": "s12.v3.pilot-adjudication.v1",
        "status": "ANNOTATED_ADJUDICATED_OWNER_DELEGATED_AI_PENDING_QUALITY_GATE",
        "reviewMode": "owner-delegated-ai",
        "humanEvidence": False,
        "qualifiedHumanEvidence": False,
        "rawSensitiveDataIncluded": False,
        "sourceDatasets": {
            "atomic": {
                "datasetVersion": atomic["datasetVersion"],
                "path": str(ATOMIC_PATH.relative_to(ROOT)).replace("\\", "/"),
                "fileDigest": _file_digest(ATOMIC_PATH),
                "contentDigest": _digest(atomic),
            },
            "scenario": {
                "datasetVersion": scenarios["datasetVersion"],
                "path": str(SCENARIO_PATH.relative_to(ROOT)).replace("\\", "/"),
                "fileDigest": _file_digest(SCENARIO_PATH),
                "contentDigest": _digest(scenarios),
            },
        },
        "sourceManifests": {
            "atomic": {
                "path": str(ATOMIC_MANIFEST_PATH.relative_to(ROOT)).replace("\\", "/"),
                "manifestDigest": atomic_manifest["manifestDigest"],
            },
            "scenario": {
                "path": str(SCENARIO_MANIFEST_PATH.relative_to(ROOT)).replace("\\", "/"),
                "manifestDigest": scenario_manifest["manifestDigest"],
            },
        },
        "guideVersions": ["annotation-guide.v1", "metrics.v2", "s12.atomic.v1", "s12.scenario.v1"],
        "coverage": _coverage(cases),
        "reviewSummary": {
            "atomicCaseCount": len(cases),
            "scenarioCount": len(scenarios["scenarios"]),
            "materialDisputeCount": 0,
            "independentHumanReviewPerformed": False,
            "thirdReviewerRequired": False,
            "goldChangedAfterPilotAuthoring": False,
        },
        "caseDecisions": case_decisions,
        "scenarioDecisions": scenario_decisions,
        "integrity": {"passed": not errors, "errors": errors},
    }


def write_packet(output: Path = DEFAULT_OUTPUT) -> None:
    packet = build_packet()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": packet["status"], "integrityPassed": packet["integrity"]["passed"], "cases": len(packet["caseDecisions"]), "scenarios": len(packet["scenarioDecisions"])}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    write_packet(args.output)


if __name__ == "__main__":
    main()
