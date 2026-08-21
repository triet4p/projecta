#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Run the offline G3.1-B quality gate for the Sprint 12 v3 deep pilot."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "evaluation/sprint-12/corpus/v3"
DEFAULT_OUTPUT = ROOT / "evaluation/sprint-12/gates/g3.1-b-v3-pilot-quality.v1.json"


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ADJUDICATOR = _load_module("s12_v3_adjudicator", ROOT / "scripts/adjudicate_sprint12_v3_pilot.py")
LANGUAGE = _load_module("s12_language_validator", ROOT / "scripts/sprint12_language_validator.py")
LEAKAGE = _load_module("s12_leakage_validator", ROOT / "scripts/sprint12_leakage_validator.py")
SCENARIO = _load_module("s12_scenario_validator", ROOT / "scripts/sprint12_scenario_validator.py")

CASE_ID = re.compile(r"^s12-a-[0-9]{4}$")
SCENARIO_ID = re.compile(r"^s12-s-[0-9]{3}$")
SPLITS = ("development", "validation", "test")


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema_errors(atomic: dict[str, Any], scenarios: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if atomic.get("datasetVersion") != "s12.corpus.atomic.v3.deep-pilot":
        errors.append("atomic dataset version mismatch")
    if scenarios.get("datasetVersion") != "s12.corpus.scenario.v3.deep-pilot":
        errors.append("scenario dataset version mismatch")
    for case in atomic.get("cases", []):
        if not CASE_ID.fullmatch(case.get("caseId", "")):
            errors.append("invalid atomic case ID")
        if case.get("schemaVersion") != "s12.atomic.v1":
            errors.append(f"{case.get('caseId')}: atomic schema version mismatch")
        required = {"caseId", "schemaVersion", "journeyId", "scenarioId", "source", "split", "gold"}
        if not required <= case.keys():
            errors.append(f"{case.get('caseId')}: missing atomic fields")
    for scenario in scenarios.get("scenarios", []):
        if not SCENARIO_ID.fullmatch(scenario.get("scenarioId", "")):
            errors.append("invalid scenario ID")
        if scenario.get("schemaVersion") != "s12.scenario.v1":
            errors.append(f"{scenario.get('scenarioId')}: scenario schema version mismatch")
        required = {"scenarioId", "schemaVersion", "journeyId", "split", "events", "checkpoints", "competencyAnswers", "sourceManifest"}
        if not required <= scenario.keys():
            errors.append(f"{scenario.get('scenarioId')}: missing scenario fields")
    return errors


def _provenance_errors(atomic: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if atomic.get("humanEvidence") is not False or atomic.get("authoringTrack") != "agent-authored-synthetic":
        errors.append("atomic evidence boundary is not synthetic-only")
    if manifest.get("testPayloadPresent") is not False or manifest.get("atomicCounts", {}).get("test") != 0:
        errors.append("atomic test payload boundary is not empty")
    for case in atomic["cases"]:
        source = case["source"]
        if source.get("origin") != "agent-authored-synthetic":
            errors.append(f"{case['caseId']}: origin is not synthetic")
        if source.get("sensitivity") != "synthetic":
            errors.append(f"{case['caseId']}: sensitivity is not synthetic")
        if not source.get("license") or not source.get("permissionRef"):
            errors.append(f"{case['caseId']}: provenance reference is missing")
    return errors


def _language_gate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    mismatches = []
    inferred_counts: Counter[str] = Counter()
    for case in cases:
        source = case["source"]
        inferred = LANGUAGE.infer_language(source["rawText"])
        inferred_counts[inferred["language"]] += 1
        if source["language"] == "mixed":
            mixed_supported = bool(
                inferred["vietnameseDiacriticSignal"]
                and re.search(r"[A-Za-z]{2,}", source["rawText"])
            )
            if not mixed_supported:
                mismatches.append(case["caseId"])
        elif inferred["confidence"] == "high" and inferred["language"] != source["language"]:
            mismatches.append(case["caseId"])
    return {
        "mismatchCount": len(mismatches),
        "mismatchCaseIds": mismatches,
        "inferredLanguageCounts": dict(sorted(inferred_counts.items())),
        "policy": "high-confidence en/vi/ja must agree; mixed requires Vietnamese signal plus ASCII code-switch token",
        "pass": not mismatches,
    }


def _coverage(cases: list[dict[str, Any]], scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    journey: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"caseCount": 0, "relationPositiveCases": 0, "relationNegativeCases": 0, "abstentionRequiredCases": 0, "entityCount": 0, "relationCount": 0, "scenarioCount": 0}
    )
    type_counts: Counter[str] = Counter()
    predicate_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    for case in cases:
        row = journey[case["journeyId"]]
        relations = case["gold"]["relations"]
        row["caseCount"] += 1
        row["relationPositiveCases"] += bool(relations)
        row["relationNegativeCases"] += not bool(relations)
        row["abstentionRequiredCases"] += case["gold"]["abstention"]["required"]
        row["entityCount"] += len(case["gold"]["entities"])
        row["relationCount"] += len(relations)
        split_counts[case["split"]] += 1
        type_counts.update(entity["type"] for entity in case["gold"]["entities"])
        predicate_counts.update(relation["predicate"] for relation in relations)
    for scenario in scenarios:
        journey[scenario["journeyId"]]["scenarioCount"] += 1
    return {
        "caseCounts": dict(sorted(split_counts.items())),
        "businessJourneyCoverage": {key: journey[key] for key in sorted(journey)},
        "entityTypeCounts": {key: type_counts[key] for key in sorted(ADJUDICATOR.ENTITY_TYPES)},
        "relationPredicateCounts": {key: predicate_counts[key] for key in sorted(ADJUDICATOR.PREDICATES)},
        "relationPositiveCases": sum(bool(case["gold"]["relations"]) for case in cases),
        "relationNegativeCases": sum(not bool(case["gold"]["relations"]) for case in cases),
        "abstentionRequiredCases": sum(case["gold"]["abstention"]["required"] for case in cases),
        "abstentionNotRequiredCases": sum(not case["gold"]["abstention"]["required"] for case in cases),
    }


def build_report() -> dict[str, Any]:
    atomic = _read(CORPUS / "atomic-deep-pilot.v1.json")
    atomic_manifest = _read(CORPUS / "manifest.v1.json")
    scenarios = _read(CORPUS / "scenario-deep-pilot.v1.json")
    scenario_manifest = _read(CORPUS / "scenario-manifest.v1.json")
    adjudication = _read(CORPUS / "gold-adjudication.v1.json")
    schema_errors = _schema_errors(atomic, scenarios)
    provenance_errors = _provenance_errors(atomic, atomic_manifest)
    span_errors = [error for case in atomic["cases"] for error in ADJUDICATOR._validate_case(case)]
    language = _language_gate(atomic["cases"])
    scenario_analysis = SCENARIO.analyze_scenarios(scenarios["scenarios"])
    leakage_atomic = LEAKAGE.analyze_atomic_cases(atomic["cases"])
    leakage_scenarios = LEAKAGE.analyze_scenarios(scenarios["scenarios"])
    leakage_pass = leakage_atomic["pass"] and leakage_scenarios["pass"]
    gates = {
        "adjudicationIntegrity": adjudication["integrity"]["passed"],
        "schema": not schema_errors,
        "provenance": not provenance_errors,
        "spanIntegrity": not span_errors,
        "language": language["pass"],
        "scenarioConsistency": scenario_analysis["pass"],
        "visibleSplitLeakage": leakage_pass,
        "testPayloadUninspected": atomic_manifest["testPayloadPresent"] is False and scenario_manifest["testPayloadPresent"] is False,
    }
    return {
        "reportVersion": "s12.g31-b-v3-pilot-quality.v1",
        "status": "V3_PILOT_QUALITY_READY" if all(gates.values()) else "V3_PILOT_QUALITY_BLOCKED",
        "humanEvidence": False,
        "qualifiedHumanEvidence": False,
        "readScope": {
            "atomicSplits": atomic_manifest["atomicCounts"],
            "scenarioSplits": scenario_manifest["scenarioCounts"],
            "testPayloadRead": False,
            "testPayloadStatus": "not-available-custody",
        },
        "gates": gates,
        "coverage": _coverage(atomic["cases"], scenarios["scenarios"]),
        "diagnostics": {
            "schemaErrors": schema_errors,
            "provenanceErrors": provenance_errors,
            "spanErrors": span_errors,
            "language": language,
            "scenario": {
                "shapeErrors": scenario_analysis["shapeErrors"],
                "unresolvedConflictGroups": scenario_analysis["unresolvedConflictGroups"],
            },
            "leakage": {
                "atomicPass": leakage_atomic["pass"],
                "scenarioPass": leakage_scenarios["pass"],
                "crossSplitTemplateClusters": leakage_atomic["crossSplitNormalizedTemplateClusters"],
                "crossSplitExactDuplicates": leakage_atomic["crossSplitExactContentDuplicateClusters"],
                "reusedScenarioLineages": leakage_scenarios["reusedSourceLineageGroups"],
            },
        },
        "nextGate": "G3.1-B review / R13 approval before scale-up",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "gates": report["gates"]}, indent=2))


if __name__ == "__main__":
    main()
