#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Approve scoped G3.1-C readiness for the frozen Sprint 12 v3 track."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "evaluation/sprint-12/corpus/v3-frozen"
COVERAGE_MATRIX = ROOT / "evaluation/sprint-12/coverage-matrix.v1.json"
DEFAULT_OUTPUT = ROOT / "evaluation/sprint-12/gates/g3.1-c-v3-readiness.v1.json"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_report() -> dict[str, Any]:
    atomic_manifest = _read(FROZEN / "atomic-manifest.v1.json")
    scenario_manifest = _read(FROZEN / "scenario-manifest.v1.json")
    coverage = _read(FROZEN / "coverage.v1.json")["coverage"]
    provenance = _read(FROZEN / "provenance.v1.json")
    qa = _read(FROZEN / "qa-report.v1.json")
    matrix = _read(COVERAGE_MATRIX)
    atomic_counts = atomic_manifest["atomicCounts"]
    scenario_counts = scenario_manifest["scenarioCounts"]
    language_counts = coverage.get("languageCounts", {})
    language_minimums = matrix["languageMinimums"]
    language_gate = all(language_counts.get(language, 0) >= minimum for language, minimum in language_minimums.items())
    journey_rows = coverage["businessJourneyCoverage"]
    journey_checks = {}
    for journey in matrix["journeys"]:
        row = journey_rows.get(journey["id"], {"caseCount": 0, "scenarioCount": 0})
        journey_checks[journey["id"]] = {
            "atomicMinimum": journey["minimumAtomic"],
            "scenarioMinimum": journey["minimumScenarios"],
            "atomicObserved": row["caseCount"],
            "scenarioObserved": row["scenarioCount"],
            "pass": row["caseCount"] >= journey["minimumAtomic"] and row["scenarioCount"] >= journey["minimumScenarios"],
        }
    gates = {
        "frozenQaPass": qa["status"] == "FROZEN_QA_PASS" and all(qa["gates"].values()),
        "atomicMinimumForControlledScope": atomic_counts["total"] >= 200 and atomic_counts["development"] >= 120 and atomic_counts["validation"] >= 40,
        "scenarioMinimumForControlledScope": scenario_counts["total"] >= 24 and scenario_counts["development"] >= 12 and scenario_counts["validation"] >= 6,
        "languageMinimums": language_gate,
        "journeyMinimumsForRepresentedJourneys": all(journey_checks[f"J{number}"]["pass"] for number in range(1, 7)),
        "provenanceAndPrivacy": provenance["humanEvidence"] is False and provenance["rawSensitiveDataIncluded"] is False,
        "testCustodySeparate": atomic_counts["test"] == 0 and scenario_counts["test"] == 0 and provenance["testPayloadPresent"] is False,
    }
    return {
        "reportVersion": "s12.g31-c-v3-readiness.v1",
        "status": "G3_1_C_READY_SCOPED_TO_J1_J6_EXTRACTION" if all(gates.values()) else "G3_1_C_BLOCKED",
        "gates": gates,
        "scope": {
            "controlledDevelopment": True,
            "oneValidationRun": True,
            "representedJourneys": [f"J{number}" for number in range(1, 7)],
            "excludedJourneys": ["J7", "J8"],
            "benchmarkCompleteness": False,
            "mandatorySlicesNotClaimed": matrix["mandatorySlices"],
        },
        "coverage": {
            "atomicCounts": atomic_counts,
            "scenarioCounts": scenario_counts,
            "languageCounts": language_counts,
            "languageMinimums": language_minimums,
            "journeyChecks": journey_checks,
        },
        "authorization": {
            "providerExecutionAuthorized": False,
            "heldOutAccessAuthorized": False,
            "testPayloadRead": False,
            "nextRequiredControls": ["S12-R17 preregistration supersession", "S12-R18/R19 deterministic evidence tool", "S12-R20/R21 owner authorization"],
        },
        "limitations": [
            "This is a scoped extraction-contract readiness decision, not G6 business-benchmark approval.",
            "J7/J8 and mandatory adversarial/isolation slices are not represented in the frozen track.",
            "Human evidence remains false and test custody remains outside the repository.",
        ],
    }


def main() -> None:
    report = build_report()
    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "gates": report["gates"]}, indent=2))


if __name__ == "__main__":
    main()
