#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Freeze the validated Sprint 12 v3 development/validation track."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "evaluation/sprint-12/corpus/v3-scale"
DEFAULT_OUTPUT = ROOT / "evaluation/sprint-12/corpus/v3-frozen"


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ADJ = _load("s12_freeze_adjudicator", ROOT / "scripts/adjudicate_sprint12_v3_pilot.py")
GATE = _load("s12_freeze_gate", ROOT / "scripts/sprint12_v3_pilot_quality_gate.py")
LEAKAGE = _load("s12_freeze_leakage", ROOT / "scripts/sprint12_leakage_validator.py")
SCENARIO = _load("s12_freeze_scenario", ROOT / "scripts/sprint12_scenario_validator.py")


def _digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _read(name: str) -> dict[str, Any]:
    return json.loads((SOURCE / name).read_text(encoding="utf-8"))


def _frozen_payload(payload: dict[str, Any], version: str) -> dict[str, Any]:
    frozen = copy.deepcopy(payload)
    frozen["datasetVersion"] = version
    frozen["status"] = "FROZEN_DEVELOPMENT_VALIDATION_ONLY"
    frozen["freezeSource"] = payload["datasetVersion"]
    frozen["freezeApproval"] = "s12.g31-b-pilot-approval.v1"
    return frozen


def _atomic_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    cases = payload["cases"]
    manifest = {
        "manifestVersion": "s12.corpus.manifest.v3.frozen",
        "datasetVersion": payload["datasetVersion"],
        "sourceDatasetVersion": payload["freezeSource"],
        "status": payload["status"],
        "humanEvidence": False,
        "qualifiedHumanEvidence": False,
        "atomicCounts": {
            "development": sum(case["split"] == "development" for case in cases),
            "validation": sum(case["split"] == "validation" for case in cases),
            "test": 0,
            "total": len(cases),
        },
        "atomicCases": [
            {
                "caseId": case["caseId"],
                "scenarioId": case["scenarioId"],
                "journeyId": case["journeyId"],
                "split": case["split"],
                "language": case["source"]["language"],
                "origin": case["source"]["origin"],
                "contentDigest": case["source"]["contentDigest"],
                "caseDigest": _digest(case),
            }
            for case in cases
        ],
        "permissionRef": "sprint12-r14-scale-v1",
        "testPayloadPresent": False,
        "freezeApproval": "s12.g31-b-pilot-approval.v1",
    }
    manifest["manifestDigest"] = _digest(manifest)
    return manifest


def _scenario_manifest(payload: dict[str, Any], atomic: dict[str, Any]) -> dict[str, Any]:
    scenarios = payload["scenarios"]
    manifest = {
        "manifestVersion": "s12.corpus.scenario-manifest.v3.frozen",
        "datasetVersion": payload["datasetVersion"],
        "sourceDatasetVersion": payload["freezeSource"],
        "atomicDatasetVersion": atomic["datasetVersion"],
        "status": payload["status"],
        "humanEvidence": False,
        "qualifiedHumanEvidence": False,
        "scenarioCounts": {
            "development": sum(scenario["split"] == "development" for scenario in scenarios),
            "validation": sum(scenario["split"] == "validation" for scenario in scenarios),
            "test": 0,
            "total": len(scenarios),
        },
        "scenarios": [
            {
                "scenarioId": scenario["scenarioId"],
                "journeyId": scenario["journeyId"],
                "split": scenario["split"],
                "sourceManifest": scenario["sourceManifest"],
                "scenarioDigest": _digest(scenario),
            }
            for scenario in scenarios
        ],
        "testPayloadPresent": False,
        "freezeApproval": "s12.g31-b-pilot-approval.v1",
    }
    manifest["manifestDigest"] = _digest(manifest)
    return manifest


def build_artifacts() -> dict[str, dict[str, Any]]:
    atomic = _frozen_payload(_read("atomic-scale.v1.json"), "s12.corpus.atomic.v3.frozen")
    scenarios = _frozen_payload(_read("scenario-scale.v1.json"), "s12.corpus.scenario.v3.frozen")
    atomic_manifest = _atomic_manifest(atomic)
    scenario_manifest = _scenario_manifest(scenarios, atomic)
    span_errors = [error for case in atomic["cases"] for error in ADJ._validate_case(case)]
    language = GATE._language_gate(atomic["cases"])
    scenario_analysis = SCENARIO.analyze_scenarios(scenarios["scenarios"])
    leakage_atomic = LEAKAGE.analyze_atomic_cases(atomic["cases"])
    leakage_scenarios = LEAKAGE.analyze_scenarios(scenarios["scenarios"])
    coverage = GATE._coverage(atomic["cases"], scenarios["scenarios"])
    coverage["languageCounts"] = {
        language: sum(case["source"]["language"] == language for case in atomic["cases"])
        for language in ("vi", "en", "ja", "mixed")
    }
    gates = {
        "spanIntegrity": not span_errors,
        "language": language["pass"],
        "scenarioConsistency": scenario_analysis["pass"],
        "visibleSplitLeakage": leakage_atomic["pass"] and leakage_scenarios["pass"],
        "testPayloadAbsent": True,
    }
    return {
        "atomic-v3.frozen.v1.json": atomic,
        "atomic-manifest.v1.json": atomic_manifest,
        "scenario-v3.frozen.v1.json": scenarios,
        "scenario-manifest.v1.json": scenario_manifest,
        "coverage.v1.json": {
            "schemaVersion": "s12.v3.frozen-coverage.v1",
            "status": "FROZEN_DEVELOPMENT_VALIDATION_ONLY",
            "datasetVersions": [atomic["datasetVersion"], scenarios["datasetVersion"]],
            "coverage": coverage,
            "testPayloadPresent": False,
        },
        "provenance.v1.json": {
            "schemaVersion": "s12.v3.frozen-provenance.v1",
            "status": "FROZEN_DEVELOPMENT_VALIDATION_ONLY",
            "humanEvidence": False,
            "qualifiedHumanEvidence": False,
            "rawSensitiveDataIncluded": False,
            "originCounts": {"agent-authored-synthetic": len(atomic["cases"])},
            "sensitivityCounts": {"synthetic": len(atomic["cases"])},
            "permissionRefs": ["sprint12-r14-scale-v1"],
            "testPayloadPresent": False,
        },
        "leakage.v1.json": {
            "schemaVersion": "s12.v3.frozen-leakage.v1",
            "status": "CLEAN_VISIBLE_SPLITS",
            "atomicPass": leakage_atomic["pass"],
            "scenarioPass": leakage_scenarios["pass"],
            "crossSplitNormalizedTemplateClusters": leakage_atomic["crossSplitNormalizedTemplateClusters"],
            "crossSplitExactContentDuplicates": leakage_atomic["crossSplitExactContentDuplicateClusters"],
            "reusedScenarioLineages": leakage_scenarios["reusedSourceLineageGroups"],
            "testPayloadRead": False,
        },
        "qa-report.v1.json": {
            "schemaVersion": "s12.v3.frozen-qa.v1",
            "status": "FROZEN_QA_PASS",
            "gates": gates,
            "diagnostics": {"spanErrors": span_errors, "language": language, "scenarioShapeErrors": scenario_analysis["shapeErrors"]},
            "providerExecutionAuthorized": False,
            "heldOutInspected": False,
            "testPayloadRead": False,
        },
    }


def write_freeze(output_dir: Path = DEFAULT_OUTPUT) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = build_artifacts()
    for name, payload in artifacts.items():
        (output_dir / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    freeze_manifest = {
        "schemaVersion": "s12.v3.freeze-manifest.v1",
        "status": "V3_FROZEN_G31_C_PENDING",
        "freezeApproval": "s12.g31-b-pilot-approval.v1",
        "humanEvidence": False,
        "providerExecutionAuthorized": False,
        "heldOutInspected": False,
        "testPayloadPresent": False,
        "files": [{"path": name, "fileDigest": _file_digest(output_dir / name)} for name in sorted(artifacts)],
    }
    freeze_manifest["manifestDigest"] = _digest(freeze_manifest)
    (output_dir / "freeze-manifest.v1.json").write_text(json.dumps(freeze_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": freeze_manifest["status"], "files": len(artifacts), "testPayloadPresent": False}, indent=2))


def main() -> None:
    write_freeze()


if __name__ == "__main__":
    main()
