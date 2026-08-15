#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Preregister S12-77 Stage A without executing a model comparison."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPTIMIZATION = ROOT / "evaluation/sprint-12/optimization"
REGISTRY_PATH = OPTIMIZATION / "experiment-registry.v2.json"
FOLLOWUP_PATH = OPTIMIZATION / "s12-73-prompt-followup-stability.v2.json"
OUTPUT_PATH = OPTIMIZATION / "s12-77-model-preregistration.v1.json"

STAGE_A_CASE_IDS = [
    "s12-a-0101",
    "s12-a-0105",
    "s12-a-0121",
    "s12-a-0122",
    "s12-a-0151",
    "s12-a-0153",
    "s12-a-0161",
    "s12-a-0162",
    "s12-a-0176",
    "s12-a-0177",
    "s12-a-0186",
    "s12-a-0187",
    "s12-a-0201",
    "s12-a-0202",
    "s12-a-0226",
    "s12-a-0233",
]


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT_PATH.exists():
        raise SystemExit(f"refusing to overwrite existing preregistration: {OUTPUT_PATH}")
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    followup = json.loads(FOLLOWUP_PATH.read_text(encoding="utf-8"))
    experiment = next(
        item for item in registry["experiments"] if item["experimentId"] == "s12-f-05"
    )
    control_model = followup["runs"][0]["configuration"]["model"]
    artifact = {
        "artifactVersion": "s12.s77.model-preregistration.v1",
        "status": "PREREGISTERED_NOT_EXECUTED",
        "experimentId": "s12-f-05",
        "taskId": "S12-77",
        "registryVersion": registry["registryVersion"],
        "registryDigest": registry["registryDigest"],
        "experimentStatus": experiment["status"],
        "datasetVersion": followup["datasetVersion"],
        "datasetManifestDigest": followup["runs"][0]["digests"]["manifest"],
        "controlModel": control_model,
        "candidateModel": None,
        "candidateModelSelectionRequired": True,
        "executionAuthorized": False,
        "heldOutInspected": False,
        "fixedArtifacts": {
            "promptVariant": "m3.prompt.v3.supersession-guard",
            "schemaVersion": "m3.v2",
            "context": "unchanged",
            "tool": "unchanged",
            "ontology": "unchanged",
            "evaluator": "unchanged",
            "policy": "unchanged",
            "retryPolicy": "none",
        },
        "stageA": {
            "caseCount": len(STAGE_A_CASE_IDS),
            "caseIds": STAGE_A_CASE_IDS,
            "independentRunsPerModel": 3,
            "pairedControlCandidate": True,
            "oneAttemptPerCase": True,
            "noRetryWithinEachRun": True,
            "samplingConfiguration": {
                "temperature": "provider-default",
                "topP": "provider-default",
                "seed": "provider-controlled",
            },
            "hardGates": {
                "schema_invalid": 0,
                "invalid_evidence": 0,
                "missing_output": 0,
                "provenance": "no regression",
                "isolation": "no regression",
                "safety": "no regression",
            },
            "semanticGates": {
                "entityMacroF1": "meaningful improvement over control",
                "abstentionAccuracy": "improve over control",
                "hallucinationRate": "decrease versus control",
                "relationMacroF1": "no regression versus control",
                "latencyUsageCost": "accounted for both models",
            },
        },
        "stageB": {
            "caseCount": 32,
            "independentRuns": 3,
            "authorizedOnlyAfterStageA": True,
            "requires": [
                "stage A hard gates pass",
                "candidate model is bound",
                "paired configuration digests are complete",
            ],
        },
        "protocolDigests": {
            "registry": file_digest(REGISTRY_PATH),
            "followupEvidence": file_digest(FOLLOWUP_PATH),
        },
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
    }
    OUTPUT_PATH.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": artifact["status"],
                "experimentId": artifact["experimentId"],
                "caseCount": artifact["stageA"]["caseCount"],
                "candidateModelSelectionRequired": artifact[
                    "candidateModelSelectionRequired"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
