#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Create the execution-locked S12-f-09 tool-dimension preregistration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "evaluation/sprint-12/corpus/v3-frozen"
OPTIMIZATION = ROOT / "evaluation/sprint-12/optimization"
OUTPUT = OPTIMIZATION / "s12-f-09-relation-evidence-preregistration.v1.json"
PRICING = OPTIMIZATION / "s12-f-08-pricing-deepseek-v4-flash.v1.json"
EVALUATOR = ROOT / "scripts/sprint12_evaluator.py"
PROMPT = ROOT / "apps/api/src/projecta_api/extraction/prompt.py"
MATERIALIZER = ROOT / "apps/api/src/projecta_api/extraction/relation_evidence.py"


def _digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def build_preregistration() -> dict[str, Any]:
    atomic = json.loads((FROZEN / "atomic-v3.frozen.v1.json").read_text(encoding="utf-8"))
    atomic_manifest = json.loads((FROZEN / "atomic-manifest.v1.json").read_text(encoding="utf-8"))
    development = [case for case in atomic["cases"] if case["split"] == "development"]
    stage_cases = development[:48]
    case_ids = [case["caseId"] for case in stage_cases]
    control_configuration = {
        "model": "deepseek-v4-flash",
        "promptVersion": "m3.prompt.v3.supersession-guard",
        "samplingConfiguration": {"seed": "provider-controlled", "temperature": "provider-default", "topP": "provider-default"},
        "schemaVersion": "m3.v2",
        "tool": "llm-authored-relation-evidence-legacy",
    }
    candidate_configuration = {**control_configuration, "tool": "server-owned-relation-evidence.v1"}
    return {
        "artifactVersion": "s12.s12-f-09.relation-evidence-preregistration.v1",
        "experimentId": "s12-f-09",
        "status": "PREREGISTERED_NOT_EXECUTED",
        "changedDimension": "tool",
        "executionAuthorized": False,
        "executionDeferredByUserInstruction": True,
        "control": {"configuration": control_configuration, "configurationDigest": _digest(control_configuration)},
        "candidate": {"configuration": candidate_configuration, "configurationDigest": _digest(candidate_configuration)},
        "fixedArtifacts": {
            "datasetVersion": atomic["datasetVersion"],
            "datasetManifestPath": "evaluation/sprint-12/corpus/v3-frozen/atomic-manifest.v1.json",
            "datasetManifestDigest": _file_digest(FROZEN / "atomic-manifest.v1.json"),
            "evaluator": "s12.evaluator.v4",
            "promptVersion": "m3.prompt.v3.supersession-guard",
            "tool": "changed-only",
            "schemaVersion": "m3.v2",
            "retryPolicy": "none",
        },
        "executionPackage": {
            "stage": "A",
            "oneAttemptPerCase": True,
            "retryPolicy": "none",
            "independentPairedRuns": 3,
            "temporalPairing": {
                "strategy": "interleaved_paired_runs",
                "schedule": [
                    {"pairId": "pair-1", "runNumber": 1, "armOrder": ["control", "candidate"]},
                    {"pairId": "pair-2", "runNumber": 2, "armOrder": ["candidate", "control"]},
                    {"pairId": "pair-3", "runNumber": 3, "armOrder": ["control", "candidate"]},
                ],
            },
            "digests": {
                "datasetManifest": _file_digest(FROZEN / "atomic-manifest.v1.json"),
                "evaluatorCode": _file_digest(EVALUATOR),
                "promptImplementation": _file_digest(PROMPT),
                "relationEvidenceMaterializer": _file_digest(MATERIALIZER),
                "pricingArtifact": _file_digest(PRICING),
            },
        },
        "stageA": {
            "caseCount": len(stage_cases),
            "caseRunsPerArm": len(stage_cases) * 3,
            "caseSelectionDigest": _digest(case_ids),
            "caseIds": case_ids,
            "independentPairedRuns": 3,
            "oneAttemptPerCase": True,
            "noRetryWithinEachRun": True,
            "split": "development",
            "selectionRationale": "Six complete frozen v3 development lineages provide relation-positive depth, abstention negatives, multilingual notes and longitudinally coherent domains without reading validation or test custody.",
            "relationPositiveCases": sum(bool(case["gold"]["relations"]) for case in stage_cases),
            "abstentionRequiredCases": sum(case["gold"]["abstention"]["required"] for case in stage_cases),
        },
        "relationTool": {
            "llmOutput": ["entity candidates", "predicate", "source/target candidate IDs", "optional relation-trigger quote"],
            "serverOutput": ["canonical entity spans", "deterministic clause/sentence evidence span"],
            "failClosedOn": ["invalid endpoint span", "missing trigger when required", "ambiguous boundary", "cross-sentence endpoints"],
        },
        "measurementContract": {
            "evaluatorVersion": "s12.evaluator.v4",
            "relationInstrumentationVersion": "s12.relation-instrumentation.v4",
            "metricContract": "s12.metric-contract.v2",
            "semanticIdentityExcludesEvidenceSpan": True,
            "perCaseAndPerSliceDenominatorsRequired": True,
        },
        "hardGates": {"schema_invalid": 0, "invalid_evidence": 0, "missing_output": 0},
        "semanticGates": {
            "relationSemanticF1Minimum": 0.80,
            "relationEvidenceSupportMinimum": 0.85,
            "relationEvidenceExactMinimum": 0.85,
            "entityMacroF1Minimum": 0.85,
            "abstentionF1Minimum": 0.90,
            "hallucinationRateMaximum": 0.05,
            "sliceFloorRequired": True,
        },
        "pricingContract": {
            "artifact": PRICING.name,
            "artifactDigest": _file_digest(PRICING),
            "model": "deepseek-v4-flash",
            "currency": "USD",
            "requiredBeforeExecution": True,
            "requiredBeforeSelection": True,
            "costCeilingUsd": "10.00",
        },
        "prohibitedBeforeStageA": ["prompt-sweep", "model-sweep", "sampling-sweep", "held-out-inspection", "gold-or-ontology-change", "retry"],
        "heldOutInspected": False,
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
        "sourceEvidence": {
            "stalePreregs": "s12-f-02-04-v3-supersession.v1.json",
            "g31cReadiness": "evaluation/sprint-12/gates/g3.1-c-v3-readiness.v1.json",
            "frozenDataset": "evaluation/sprint-12/corpus/v3-frozen/atomic-v3.frozen.v1.json",
            "frozenManifest": atomic_manifest["manifestDigest"],
        },
    }


def main() -> None:
    OUTPUT.write_text(json.dumps(build_preregistration(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"experimentId": "s12-f-09", "status": "PREREGISTERED_NOT_EXECUTED", "executionAuthorized": False}, indent=2))


if __name__ == "__main__":
    main()
