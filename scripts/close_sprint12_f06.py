#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Close S12-f-06 Stage A into immutable registry/G5 v5 evidence."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPTIMIZATION = ROOT / "evaluation/sprint-12/optimization"
SOURCE_REGISTRY = OPTIMIZATION / "experiment-registry.v4.json"
STAGE_A = OPTIMIZATION / "s12-f-06-sampling-stage-a.v1.json"
ERRATUM = OPTIMIZATION / "s12-f-06-sampling-erratum.v1.json"
AUTHORIZATION = OPTIMIZATION / "s12-f-06-sampling-authorization.v1.json"
REGISTRY = OPTIMIZATION / "experiment-registry.v5.json"
G5_PACKET = OPTIMIZATION / "g5-packet.v5.json"


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
    if REGISTRY.exists() or G5_PACKET.exists():
        raise SystemExit("S12-f-06 closure artifacts already exist")
    registry = json.loads(SOURCE_REGISTRY.read_text(encoding="utf-8"))
    stage = json.loads(STAGE_A.read_text(encoding="utf-8"))
    erratum = json.loads(ERRATUM.read_text(encoding="utf-8"))
    authorization = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    if authorization["status"] != "APPROVED_FOR_DEVELOPMENT_STAGE_A":
        raise SystemExit("S12-f-06 authorization is not valid")

    registry_v5 = copy.deepcopy(registry)
    registry_v5["registryVersion"] = "s12.experiment-registry.v5"
    registry_v5["openedExperimentId"] = "s12-f-06"
    for experiment in registry_v5["experiments"]:
        if experiment["experimentId"] != "s12-f-06":
            continue
        experiment["status"] = "COMPLETED_STAGE_A_NOT_ELIGIBLE_FOR_STAGE_B"
        experiment["executionEvidence"] = {
            "artifact": STAGE_A.name,
            "digest": file_digest(STAGE_A),
            "authorizationArtifact": AUTHORIZATION.name,
            "authorizationDigest": file_digest(AUTHORIZATION),
            "decision": stage["decision"],
            "hardGatesPass": stage["hardGatesPass"],
            "semanticGatesPass": stage["comparison"]["semanticGatesPass"],
            "stageBAuthorized": stage["stageBAuthorized"],
            "costAccountingStatus": stage["accounting"]["costAccountingStatus"],
            "candidateHardGates": erratum["candidateHardGates"],
            "controlHardGates": erratum["controlHardGates"],
            "comparisonIntegrity": erratum["comparisonIntegrity"],
            "erratum": {
                "artifact": ERRATUM.name,
                "digest": file_digest(ERRATUM),
                "commonCaseExecutionCount": erratum["commonCaseMetrics"][
                    "caseExecutionCount"
                ],
                "status": erratum["status"],
            },
        }
        experiment["resultSummary"] = {
            "controlFailureCounts": stage["control"]["aggregateFailureCounts"],
            "candidateFailureCounts": stage["candidate"]["aggregateFailureCounts"],
            "controlMissingOutputCount": stage["control"]["aggregateMissingOutputCount"],
            "candidateMissingOutputCount": stage["candidate"]["aggregateMissingOutputCount"],
            "metricDeltas": stage["comparison"]["metricDeltas"],
        }
    registry_v5.pop("registryDigest", None)
    registry_v5["registryDigest"] = canonical_digest(registry_v5)
    write_json(REGISTRY, registry_v5)

    packet = {
        "packetVersion": "s12.g5.packet.v5",
        "status": "G5_PREPARATION_DEVELOPMENT_OPEN",
        "approvalStatus": "APPROVED_WITH_LIMITATIONS",
        "registryVersion": registry_v5["registryVersion"],
        "registryDigest": registry_v5["registryDigest"],
        "datasetVersion": stage["datasetVersion"],
        "datasetManifestDigest": stage["datasetManifestDigest"],
        "executedExperimentId": "s12-f-06",
        "candidateAvailable": True,
        "controlModel": stage["control"]["model"],
        "candidateModel": stage["candidate"]["model"],
        "candidateEvidence": {
            "artifact": STAGE_A.name,
            "digest": file_digest(STAGE_A),
            "decision": stage["decision"],
            "authorizationArtifact": AUTHORIZATION.name,
            "authorizationDigest": file_digest(AUTHORIZATION),
            "erratum": {
                "artifact": ERRATUM.name,
                "digest": file_digest(ERRATUM),
                "commonCaseExecutionCount": erratum["commonCaseMetrics"][
                    "caseExecutionCount"
                ],
                "status": erratum["status"],
            },
        },
        "hardInvariants": {
            "status": "FAIL",
            "controlFailureCounts": stage["control"]["aggregateFailureCounts"],
            "candidateFailureCounts": stage["candidate"]["aggregateFailureCounts"],
            "controlMissingOutputCount": stage["control"]["aggregateMissingOutputCount"],
            "candidateMissingOutputCount": stage["candidate"]["aggregateMissingOutputCount"],
            "candidateHardGates": erratum["candidateHardGates"],
            "controlHardGates": erratum["controlHardGates"],
            "comparisonIntegrity": erratum["comparisonIntegrity"],
        },
        "comparison": stage["comparison"],
        "accounting": stage["accounting"],
        "selection": {
            "status": "NO_SELECTION",
            "reason": "S12-f-06 Stage A failed hard and semantic gates; Stage B is locked.",
            "heldOutInspected": False,
        },
        "stageBAuthorized": False,
        "validationAuthorized": False,
        "candidateFreezeAuthorized": False,
        "heldOutInspected": False,
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
    }
    write_json(G5_PACKET, packet)
    print(json.dumps({"registry": registry_v5["registryDigest"], "stageBAuthorized": False}))


if __name__ == "__main__":
    main()
