#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Open the versioned S12-73 prompt-only development experiment."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPTIMIZATION = ROOT / "evaluation/sprint-12/optimization"
REGISTRY_V1 = OPTIMIZATION / "experiment-registry.v1.json"
REGISTRY_V2 = OPTIMIZATION / "experiment-registry.v2.json"
PACKET_V2 = OPTIMIZATION / "g5-packet.v2.json"
MANIFEST_V2 = ROOT / "evaluation/sprint-12/corpus/manifests/development-validation.manifest.v2.json"
S73_PATH = OPTIMIZATION / "s12-73-prompt-supersession.v1.json"
S73_FOLLOWUP_PATH = OPTIMIZATION / "s12-73-prompt-followup-stability.v2.json"
DIAGNOSTIC_PATH = OPTIMIZATION / "s12-73-targeted-diagnostics.v1.json"


def digest(value: object) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    source = json.loads(REGISTRY_V1.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_V2.read_text(encoding="utf-8"))
    experiment_result = json.loads(S73_PATH.read_text(encoding="utf-8"))
    followup_result = json.loads(S73_FOLLOWUP_PATH.read_text(encoding="utf-8"))
    diagnostic_result = (
        json.loads(DIAGNOSTIC_PATH.read_text(encoding="utf-8"))
        if DIAGNOSTIC_PATH.exists()
        else None
    )
    registry = copy.deepcopy(source)
    registry["registryVersion"] = "s12.experiment-registry.v2"
    registry["datasetVersion"] = "s12.corpus.atomic.v2"
    registry["datasetManifestDigest"] = manifest["manifestDigest"]
    registry["status"] = "G5_PREPARATION_DEVELOPMENT_OPEN"
    for experiment in registry["experiments"]:
        experiment["datasetManifestDigest"] = manifest["manifestDigest"]
        if experiment["experimentId"] == "s12-f-01":
            experiment["hypothesis"] = (
                "A bounded supersession-guard prompt avoids unsupported Requirement "
                "proposals while preserving m3.v2 evidence and candidate IDs."
            )
            experiment["candidateConfigurationDigest"] = digest(
                {
                    "datasetVersion": "s12.corpus.atomic.v2",
                    "datasetManifestDigest": manifest["manifestDigest"],
                    "promptVariant": "m3.prompt.v3.supersession-guard",
                    "schemaVersion": "m3.v2",
                }
            )
            experiment["status"] = "COMPLETED_STABILITY_FAILED"
            experiment["protocolVariance"] = True
            experiment["protocolAmendment"] = (
                "The registered one-run development stopping rule was amended for "
                "measurement stability: execute three independent 8-case runs per "
                "variant, then a three-run 32-case guarded-prompt follow-up. No retry "
                "was used within a run."
            )
            experiment["executionProtocol"] = {
                "initialCasesPerVariant": 8,
                "initialIndependentRunsPerVariant": 3,
                "followupCaseCount": 32,
                "followupIndependentRunCount": 3,
                "retryPolicy": "none",
                "noRetryWithinEachRun": True,
            }
            experiment["executionEvidence"] = {
                "initialExperiment": {
                    "artifact": S73_PATH.name,
                    "digest": file_digest(S73_PATH),
                    "status": experiment_result.get("status"),
                },
                "stabilityFollowup": {
                    "artifact": S73_FOLLOWUP_PATH.name,
                    "digest": file_digest(S73_FOLLOWUP_PATH),
                    "status": followup_result.get("status"),
                    "failureCounts": followup_result.get("aggregateFailureCounts"),
                },
            }
            if diagnostic_result is not None:
                experiment["executionEvidence"]["targetedDiagnostic"] = {
                    "artifact": DIAGNOSTIC_PATH.name,
                    "digest": file_digest(DIAGNOSTIC_PATH),
                    "status": diagnostic_result.get("status"),
                    "caseIds": diagnostic_result.get("caseIds"),
                    "failureCounts": diagnostic_result.get("failureCounts"),
                }
            experiment["resultSummary"] = {
                "status": "COMPLETED_NOT_PROMOTED",
                "candidateSchemaEvidenceClean": experiment_result.get(
                    "candidateSchemaEvidenceClean"
                ),
                "semanticMetricsImproved": experiment_result.get(
                    "semanticMetricsImproved"
                ),
                "followupStatus": followup_result.get("status"),
                "followupFailureCounts": followup_result.get(
                    "aggregateFailureCounts"
                ),
            }
    registry.pop("registryDigest", None)
    registry["openedExperimentId"] = "s12-f-01"
    registry["promptDevelopmentExperimentAuthorized"] = True
    registry["validationAuthorized"] = False
    registry["heldOutInspected"] = False
    registry["registryDigest"] = digest(registry)
    write_json(REGISTRY_V2, registry)

    packet = {
        "packetVersion": "s12.g5.packet.v2",
        "status": "G5_PREPARATION_DEVELOPMENT_OPEN",
        "approvalStatus": "APPROVED_WITH_LIMITATIONS",
        "registryVersion": registry["registryVersion"],
        "registryDigest": registry["registryDigest"],
        "datasetVersion": "s12.corpus.atomic.v2",
        "datasetManifestDigest": manifest["manifestDigest"],
        "g4Status": "CONTRACT_ALIGNED_STABILITY_FAILED",
        "experimentCount": len(registry["experiments"]),
        "openedExperimentId": "s12-f-01",
        "promptDevelopmentExperimentAuthorized": True,
        "developmentExperimentsAuthorized": True,
        "optimizationAuthorized": False,
        "candidateAvailable": True,
        "candidateEvidence": {
            "artifact": S73_FOLLOWUP_PATH.name,
            "digest": file_digest(S73_FOLLOWUP_PATH),
            "status": followup_result.get("status"),
            "failureCounts": followup_result.get("aggregateFailureCounts"),
        },
        "comparisons": {
            "s12-f-01": {
                "status": "REJECTED_CANDIDATE_HARD_INVARIANT",
                "reason": "candidate exists but the 32-case stability follow-up has schema_invalid failures",
                "failureCounts": followup_result.get("aggregateFailureCounts"),
            }
        },
        "selection": {
            "status": "NO_SELECTION",
            "reason": "candidate exists but failed the guarded-prompt stability follow-up; no candidate promotion is authorized.",
            "heldOutInspected": False,
        },
        "validationAuthorized": False,
        "candidateFreezeAuthorized": False,
        "hardInvariants": {
            "status": "FAIL",
            "schemaValidity": False,
            "followupFailureCounts": followup_result.get("aggregateFailureCounts"),
        },
        "heldOutInspected": False,
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
    }
    if diagnostic_result is not None:
        packet["candidateEvidence"]["targetedDiagnostic"] = {
            "artifact": DIAGNOSTIC_PATH.name,
            "digest": file_digest(DIAGNOSTIC_PATH),
            "status": diagnostic_result.get("status"),
            "caseIds": diagnostic_result.get("caseIds"),
            "failureCounts": diagnostic_result.get("failureCounts"),
        }
    write_json(PACKET_V2, packet)
    print(
        json.dumps(
            {
                "status": packet["status"],
                "experimentId": packet["openedExperimentId"],
                "registryDigest": registry["registryDigest"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
