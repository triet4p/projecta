"""Close the single S12-f-08 Stage A evidence packet without rerun."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OPT = ROOT / "evaluation/sprint-12/optimization"
REGISTRY_V9 = OPT / "experiment-registry.v9.json"
REGISTRY_V10 = OPT / "experiment-registry.v10.json"
G5_V9 = OPT / "g5-packet.v9.json"
G5_V10 = OPT / "g5-packet.v10.json"
AGGREGATE = OPT / "s12-f-08-relation-prompt-stage-a.v1.json"
RUNS_DIR = OPT / "s12-f-08-relation-prompt-stage-a"
AUTHORIZATION = OPT / "s12-f-08-authorization.v2.json"
PRICING = OPT / "s12-f-08-pricing-deepseek-v4-flash.v1.json"


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite immutable artifact: {path}")
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def reports() -> list[dict[str, str]]:
    paths = sorted(RUNS_DIR.glob("*.report.v1.json"))
    if len(paths) != 6:
        raise SystemExit("S12-f-08 closure requires exactly six report artifacts")
    return [
        {
            "artifact": path.relative_to(ROOT).as_posix(),
            "digest": file_digest(path),
        }
        for path in paths
    ]


def build_registry(aggregate: dict[str, Any]) -> dict[str, Any]:
    registry = copy.deepcopy(load(REGISTRY_V9))
    registry.pop("registryDigest", None)
    registry["registryVersion"] = "s12.experiment-registry.v10"
    registry["status"] = "G5_PREPARATION_DEVELOPMENT_CLOSED_S12_F08_REJECTED"
    f08 = next(item for item in registry["experiments"] if item["experimentId"] == "s12-f-08")
    f08.update(
        {
            "status": "COMPLETED_REJECTED",
            "executionEvidence": {
                "aggregate": {
                    "artifact": AGGREGATE.name,
                    "digest": file_digest(AGGREGATE),
                },
                "reports": reports(),
                "decision": "REJECTED_NO_STAGE_B_NO_SELECTION",
                "stageATechnicalPass": aggregate["stageATechnicalPass"],
                "candidateHardGatesPass": aggregate["candidate"]["hardGatesPass"],
                "controlHardGatesPass": aggregate["control"]["hardGatesPass"],
            },
            "noStageB": True,
            "noCandidateSelection": True,
        }
    )
    registry["pendingExperiment"] = {
        "experimentId": "s12-f-08",
        "status": "COMPLETED_REJECTED",
        "executionAuthorized": False,
        "stageBAuthorized": False,
        "authorizationArtifact": AUTHORIZATION.name,
        "authorizationDigest": file_digest(AUTHORIZATION),
        "aggregateArtifact": AGGREGATE.name,
        "aggregateDigest": file_digest(AGGREGATE),
    }
    registry["selection"] = {
        "status": "NO_SELECTION",
        "reason": "S12-f-08 failed Stage A relation gates; no Stage B or candidate selection is authorized.",
        "heldOutInspected": False,
    }
    registry["registryDigest"] = canonical_digest(registry)
    return registry


def build_g5(registry: dict[str, Any], aggregate: dict[str, Any]) -> dict[str, Any]:
    packet = copy.deepcopy(load(G5_V9))
    packet["packetVersion"] = "s12.g5.packet.v10"
    packet["status"] = "G5_PREPARATION_DEVELOPMENT_CLOSED_S12_F08_REJECTED"
    packet["approvalStatus"] = "COMPLETED_REJECTED_NO_STAGE_B"
    packet["registryVersion"] = registry["registryVersion"]
    packet["registryDigest"] = registry["registryDigest"]
    packet["candidateAvailable"] = False
    packet["candidateFreezeAuthorized"] = False
    packet["optimizationAuthorized"] = False
    packet["selection"] = {
        "status": "NO_SELECTION",
        "reason": "S12-f-08 failed Stage A relation gates; no Stage B or candidate selection is authorized.",
        "heldOutInspected": False,
    }
    packet["executionBlockedReasons"] = [
        "S12-f-08 Stage A relation gates failed",
        "no Stage B or candidate selection is authorized",
        "the six report artifacts and aggregate are immutable",
    ]
    packet["completedExperiment"] = {
        "experimentId": "s12-f-08",
        "status": "COMPLETED_REJECTED",
        "aggregateArtifact": AGGREGATE.name,
        "aggregateDigest": file_digest(AGGREGATE),
        "reports": reports(),
        "stageATechnicalPass": aggregate["stageATechnicalPass"],
        "noStageB": True,
        "noCandidateSelection": True,
        "pricingArtifact": PRICING.name,
        "pricingDigest": file_digest(PRICING),
    }
    packet["pendingExperiment"] = {
        "experimentId": "s12-f-08",
        "status": "COMPLETED_REJECTED",
        "executionAuthorized": False,
        "stageBAuthorized": False,
        "aggregateArtifact": AGGREGATE.name,
        "aggregateDigest": file_digest(AGGREGATE),
    }
    return packet


def main() -> None:
    aggregate = load(AGGREGATE)
    if aggregate.get("status") != "STAGE_A_COMPLETED":
        raise SystemExit("S12-f-08 aggregate is not complete")
    if aggregate.get("decision") != "STAGE_A_NOT_ELIGIBLE_FOR_STAGE_B":
        raise SystemExit("S12-f-08 is not rejected; closure would be unsafe")
    registry = build_registry(aggregate)
    write_new(REGISTRY_V10, registry)
    write_new(G5_V10, build_g5(registry, aggregate))
    print(json.dumps({
        "registryDigest": registry["registryDigest"],
        "aggregateDigest": file_digest(AGGREGATE),
        "reportDigests": reports(),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
