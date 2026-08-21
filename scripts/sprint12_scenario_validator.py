#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Audit Sprint 12 scenario semantic consistency without held-out access."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "evaluation/sprint-12/corpus"
VALIDATOR_VERSION = "s12.scenario-validator.v2"
DIMENSIONS = (
    "temporalEffects",
    "reviewDispositions",
    "checkpoints",
    "competencyAnswers",
)


class ScenarioValidationError(ValueError):
    """Raised when the validator receives malformed or sealed input."""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash(value: object) -> str:
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _dimension_projection(scenario: dict[str, Any], dimension: str) -> object:
    if dimension == "temporalEffects":
        return [event.get("expectedTemporalEffect") for event in scenario["events"]]
    if dimension == "reviewDispositions":
        return [event.get("expectedReview") for event in scenario["events"]]
    if dimension == "checkpoints":
        return scenario.get("checkpoints", [])
    if dimension == "competencyAnswers":
        return scenario.get("competencyAnswers", [])
    raise ScenarioValidationError(f"unknown consistency dimension: {dimension}")


def _validate_shape(scenario: dict[str, Any]) -> list[str]:
    scenario_id = str(scenario.get("scenarioId"))
    source_manifest = scenario.get("sourceManifest")
    events = scenario.get("events")
    errors: list[str] = []
    if not isinstance(source_manifest, list) or not all(
        isinstance(case_id, str) for case_id in source_manifest
    ):
        return [f"{scenario_id}: invalid sourceManifest"]
    if not isinstance(events, list) or len(events) != len(source_manifest):
        errors.append(f"{scenario_id}: event/sourceManifest length mismatch")
        return errors
    sequences = [event.get("sequence") for event in events]
    if sequences != list(range(1, len(events) + 1)):
        errors.append(f"{scenario_id}: event sequences are not contiguous")
    event_case_ids = [event.get("caseId") for event in events]
    if event_case_ids != source_manifest:
        errors.append(f"{scenario_id}: event case IDs differ from sourceManifest")
    if len(set(event_case_ids)) != len(event_case_ids):
        errors.append(f"{scenario_id}: repeated event case ID")
    return errors


def _lineage_row(lineage_key: str, scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    dimension_hashes = {
        dimension: sorted(
            {
                _hash(_dimension_projection(scenario, dimension))
                for scenario in scenarios
            }
        )
        for dimension in DIMENSIONS
    }
    conflicting_dimensions = [
        dimension
        for dimension, hashes in dimension_hashes.items()
        if len(hashes) > 1
    ]
    rationales_present = sum(
        isinstance(scenario.get("semanticVariationRationale"), str)
        and bool(scenario["semanticVariationRationale"].strip())
        for scenario in scenarios
    )
    unresolved = conflicting_dimensions if rationales_present == 0 else []
    return {
        "lineageHash": _hash(lineage_key),
        "scenarioCount": len(scenarios),
        "scenarioIds": sorted(str(scenario["scenarioId"]) for scenario in scenarios),
        "splits": sorted({str(scenario["split"]) for scenario in scenarios}),
        "dimensionHashes": dimension_hashes,
        "conflictingDimensions": conflicting_dimensions,
        "rationalePresentCount": rationales_present,
        "unresolvedConflictingDimensions": unresolved,
    }


def analyze_scenarios(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    if any(scenario.get("split") == "test" for scenario in scenarios):
        raise ScenarioValidationError(
            "test payload was supplied; scenario validation must not read held-out data"
        )
    shape_errors = [
        error for scenario in scenarios for error in _validate_shape(scenario)
    ]
    by_lineage: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for scenario in scenarios:
        by_lineage["|".join(scenario["sourceManifest"])].append(scenario)
    rows = [
        _lineage_row(lineage_key, lineage_scenarios)
        for lineage_key, lineage_scenarios in by_lineage.items()
        if len(lineage_scenarios) > 1
    ]
    rows.sort(key=lambda row: row["lineageHash"])
    unresolved_rows = [row for row in rows if row["unresolvedConflictingDimensions"]]
    return {
        "payloadScenarioCount": len(scenarios),
        "uniqueSourceLineageCount": len(by_lineage),
        "repeatedSourceLineageGroups": rows,
        "unresolvedConflictGroups": unresolved_rows,
        "shapeErrors": shape_errors,
        "pass": not unresolved_rows and not shape_errors,
    }


def validate(
    scenario_payload: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    scenarios = scenario_payload["scenarios"]
    analysis = analyze_scenarios(scenarios)
    return {
        "reportVersion": VALIDATOR_VERSION,
        "datasetVersion": scenario_payload.get("datasetVersion"),
        "status": "BLOCKED_SCENARIO_INCONSISTENCY"
        if not analysis["pass"]
        else "SCENARIO_CONSISTENCY_READY",
        "readScope": {
            "scenarioPayloadSplits": {
                split: sum(scenario.get("split") == split for scenario in scenarios)
                for split in ("development", "validation")
            },
            "testPayloadRead": False,
            "testPayloadStatus": "not-available-custody",
            "testManifestCount": manifest.get("scenarioCounts", {}).get("test"),
        },
        "dimensions": list(DIMENSIONS),
        "analysis": analysis,
        "gates": {
            "shapeIntegrity": not analysis["shapeErrors"],
            "noUnexplainedLineageConflicts": not analysis["unresolvedConflictGroups"],
            "longitudinalBusinessReady": analysis["pass"],
        },
    }


def validate_paths(scenario_path: Path, manifest_path: Path) -> dict[str, Any]:
    return validate(read_json(scenario_path), read_json(manifest_path))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        type=Path,
        default=CORPUS / "scenario-development-validation.v2.json",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=CORPUS / "manifest.v2.json",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate_paths(args.scenario, args.manifest)
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")


if __name__ == "__main__":
    main()
