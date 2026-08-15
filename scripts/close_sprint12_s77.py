#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Close S12-77 Stage A into immutable registry/G5 v3 evidence."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPTIMIZATION = ROOT / "evaluation/sprint-12/optimization"
REGISTRY_V2 = OPTIMIZATION / "experiment-registry.v2.json"
STAGE_A = OPTIMIZATION / "s12-77-model-stage-a.v1.json"
TARGETED_DIAGNOSTIC = OPTIMIZATION / "s12-77-targeted-diagnostics.v1.json"
REGISTRY_V3 = OPTIMIZATION / "experiment-registry.v3.json"
G5_V3 = OPTIMIZATION / "g5-packet.v3.json"


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def write_json(path: Path, value: object) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite existing artifact: {path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    registry = json.loads(REGISTRY_V2.read_text(encoding="utf-8"))
    stage = json.loads(STAGE_A.read_text(encoding="utf-8"))
    targeted_diagnostic = json.loads(TARGETED_DIAGNOSTIC.read_text(encoding="utf-8"))
    registry_v3 = copy.deepcopy(registry)
    registry_v3["registryVersion"] = "s12.experiment-registry.v3"
    registry_v3["openedExperimentId"] = "s12-f-05"
    for experiment in registry_v3["experiments"]:
        if experiment["experimentId"] == "s12-f-05":
            experiment["status"] = "COMPLETED_STAGE_A_NOT_ELIGIBLE_FOR_STAGE_B"
            experiment["executionEvidence"] = {
                "artifact": STAGE_A.name,
                "digest": file_digest(STAGE_A),
                "decision": stage["decision"],
                "stageBAuthorized": stage["stageBAuthorized"],
                "hardGatesPass": stage["hardGatesPass"],
                "semanticGatesPass": stage["comparison"]["semanticGatesPass"],
                "costAccountingStatus": stage["accounting"]["costAccountingStatus"],
                "targetedDiagnostic": {
                    "artifact": TARGETED_DIAGNOSTIC.name,
                    "digest": file_digest(TARGETED_DIAGNOSTIC),
                    "caseIds": targeted_diagnostic["caseIds"],
                    "status": targeted_diagnostic["status"],
                    "failureCounts": targeted_diagnostic["failureCounts"],
                },
            }
            experiment["resultSummary"] = {
                "controlModel": stage["control"]["model"],
                "candidateModel": stage["candidate"]["model"],
                "metricDeltas": stage["comparison"]["metricDeltas"],
                "controlFailureCounts": stage["control"]["aggregateFailureCounts"],
                "candidateFailureCounts": stage["candidate"]["aggregateFailureCounts"],
            }
    registry_v3.pop("registryDigest", None)
    registry_v3["registryDigest"] = canonical_digest(registry_v3)
    write_json(REGISTRY_V3, registry_v3)

    g5 = {
        "packetVersion": "s12.g5.packet.v3",
        "status": "G5_PREPARATION_DEVELOPMENT_OPEN",
        "approvalStatus": "APPROVED_WITH_LIMITATIONS",
        "registryVersion": registry_v3["registryVersion"],
        "registryDigest": registry_v3["registryDigest"],
        "datasetVersion": stage["datasetVersion"],
        "datasetManifestDigest": stage["datasetManifestDigest"],
        "executedExperimentId": "s12-f-05",
        "candidateAvailable": True,
        "candidateModel": stage["candidate"]["model"],
        "candidateEvidence": {
            "artifact": STAGE_A.name,
            "digest": file_digest(STAGE_A),
            "decision": stage["decision"],
            "targetedDiagnostic": {
                "artifact": TARGETED_DIAGNOSTIC.name,
                "digest": file_digest(TARGETED_DIAGNOSTIC),
                "caseIds": targeted_diagnostic["caseIds"],
                "status": targeted_diagnostic["status"],
                "failureCounts": targeted_diagnostic["failureCounts"],
            },
        },
        "controlModel": stage["control"]["model"],
        "hardInvariants": {
            "status": "FAIL",
            "controlFailureCounts": stage["control"]["aggregateFailureCounts"],
            "candidateFailureCounts": stage["candidate"]["aggregateFailureCounts"],
        },
        "comparison": stage["comparison"],
        "accounting": stage["accounting"],
        "selection": {
            "status": "NO_SELECTION",
            "reason": "S12-77 Stage A failed hard and semantic gates; Stage B is locked.",
            "heldOutInspected": False,
        },
        "stageBAuthorized": False,
        "validationAuthorized": False,
        "candidateFreezeAuthorized": False,
        "heldOutInspected": False,
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
    }
    write_json(G5_V3, g5)
    print(json.dumps({"registry": registry_v3["registryDigest"], "stageBAuthorized": False}, sort_keys=True))


if __name__ == "__main__":
    main()
