#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Preregister a single-variable sampling-configuration experiment."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPTIMIZATION = ROOT / "evaluation/sprint-12/optimization"
SOURCE_REGISTRY = OPTIMIZATION / "experiment-registry.v3.json"
STAGE_A = OPTIMIZATION / "s12-77-model-stage-a.v1.json"
PREREGISTRATION = OPTIMIZATION / "s12-f-06-sampling-preregistration.v1.json"
REGISTRY = OPTIMIZATION / "experiment-registry.v4.json"
G5_PACKET = OPTIMIZATION / "g5-packet.v4.json"
CASE_IDS = (
    "s12-a-0101",
    "s12-a-0121",
    "s12-a-0153",
    "s12-a-0162",
    "s12-a-0176",
    "s12-a-0187",
    "s12-a-0201",
    "s12-a-0233",
)


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def write_json(path: Path, value: object) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite artifact: {path}")
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    if any(path.exists() for path in (PREREGISTRATION, REGISTRY, G5_PACKET)):
        raise SystemExit("S12-f-06 artifacts already exist; refusing to overwrite")
    source_registry = json.loads(SOURCE_REGISTRY.read_text(encoding="utf-8"))
    stage = json.loads(STAGE_A.read_text(encoding="utf-8"))
    if stage["candidate"]["model"] != "deepseek-v4-pro":
        raise SystemExit("S12-f-06 requires the bound deepseek-v4-pro candidate")

    baseline_configuration = {
        "model": "deepseek-v4-pro",
        "schemaVersion": "m3.v2",
        "promptVersion": "m3.prompt.v3.supersession-guard",
        "samplingConfiguration": {
            "temperature": "provider-default",
            "topP": "provider-default",
            "seed": "provider-controlled",
        },
    }
    candidate_configuration = {
        **baseline_configuration,
        "samplingConfiguration": {
            "temperature": 0.0,
            "topP": 1.0,
            "seed": "provider-controlled",
        },
    }
    preregistration = {
        "artifactVersion": "s12.s12-f-06.sampling-preregistration.v1",
        "status": "PREREGISTERED_NOT_EXECUTED",
        "experimentId": "s12-f-06",
        "dimension": "sampling",
        "hypothesis": (
            "Explicit deterministic sampling reduces stochastic schema and relation "
            "normalization failures without changing model, prompt, dataset, or policy."
        ),
        "datasetVersion": stage["datasetVersion"],
        "datasetManifestDigest": stage["datasetManifestDigest"],
        "control": {
            "configuration": baseline_configuration,
            "configurationDigest": canonical_digest(baseline_configuration),
        },
        "candidate": {
            "configuration": candidate_configuration,
            "configurationDigest": canonical_digest(candidate_configuration),
        },
        "stageA": {
            "caseIds": list(CASE_IDS),
            "caseCount": len(CASE_IDS),
            "independentRunsPerVariant": 3,
            "pairedControlCandidate": True,
            "oneAttemptPerCase": True,
            "noRetryWithinEachRun": True,
            "selectionRationale": (
                "Includes both recurring S12-77 failures, positive entity/relation "
                "cases, abstention cases, and multiple development slices."
            ),
        },
        "hardGates": {
            "schema_invalid": 0,
            "invalid_evidence": 0,
            "missing_output": 0,
            "provenance": "no regression",
            "isolation": "no regression",
            "safety": "no regression",
        },
        "semanticThresholds": {
            "entityMacroF1MinimumDelta": 0.05,
            "abstentionAccuracyMinimumDelta": 0.05,
            "hallucinationRateMaximumIncrease": 0.0,
            "relationMacroF1MinimumDelta": 0.0,
        },
        "preservedArtifacts": [
            "dataset",
            "evaluator",
            "ontology",
            "policy",
            "review-contract",
            "model",
            "prompt",
        ],
        "executionAuthorized": False,
        "executionPrerequisites": {
            "samplingTransportImplemented": True,
            "providerPriceConfigurationRequired": True,
            "stageBRequiresStageAHardAndSemanticPass": True,
            "validationAuthorized": False,
            "heldOutInspected": False,
        },
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
    }
    write_json(PREREGISTRATION, preregistration)

    registry = copy.deepcopy(source_registry)
    registry["registryVersion"] = "s12.experiment-registry.v4"
    registry["openedExperimentId"] = "s12-f-06"
    registry["experiments"].append(
        {
            "experimentId": "s12-f-06",
            "hypothesis": preregistration["hypothesis"],
            "dimension": "sampling",
            "permittedSplit": "development",
            "baselineConfigurationDigest": preregistration["control"][
                "configurationDigest"
            ],
            "candidateConfigurationDigest": preregistration["candidate"][
                "configurationDigest"
            ],
            "metricTarget": {
                "semanticQuality": {"direction": "higher", "minimumDelta": 0.05}
            },
            "stoppingRule": (
                "Stop after Stage A if any hard gate fails; authorize Stage B only "
                "when all hard and registered semantic gates pass."
            ),
            "changedArtifacts": ["sampling"],
            "preservedArtifacts": preregistration["preservedArtifacts"],
            "status": "REGISTERED",
            "executionEvidence": {
                "artifact": PREREGISTRATION.name,
                "digest": file_digest(PREREGISTRATION),
                "status": preregistration["status"],
                "executionAuthorized": False,
            },
        }
    )
    registry.pop("registryDigest", None)
    registry["registryDigest"] = canonical_digest(registry)
    write_json(REGISTRY, registry)

    packet = {
        "packetVersion": "s12.g5.packet.v4",
        "status": "G5_PREPARATION_DEVELOPMENT_OPEN",
        "approvalStatus": "APPROVED_WITH_LIMITATIONS",
        "registryVersion": registry["registryVersion"],
        "registryDigest": registry["registryDigest"],
        "executedExperimentId": "s12-f-05",
        "pendingExperimentId": "s12-f-06",
        "pendingExperiment": {
            "artifact": PREREGISTRATION.name,
            "digest": file_digest(PREREGISTRATION),
            "status": preregistration["status"],
            "executionAuthorized": False,
            "dimension": "sampling",
        },
        "candidateAvailable": True,
        "candidateModel": "deepseek-v4-pro",
        "stageBAuthorized": False,
        "validationAuthorized": False,
        "candidateFreezeAuthorized": False,
        "heldOutInspected": False,
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
    }
    write_json(G5_PACKET, packet)
    print(
        json.dumps(
            {
                "experimentId": "s12-f-06",
                "status": preregistration["status"],
                "executionAuthorized": False,
                "registry": registry["registryDigest"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
