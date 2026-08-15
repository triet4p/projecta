"""Issue S12-f-07 authorization v2 after the execution package is frozen."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OPT = ROOT / "evaluation/sprint-12/optimization"
PREREG = OPT / "s12-f-07-relation-prompt-preregistration.v2.json"
AUTH_V1 = OPT / "s12-f-07-authorization.v1.json"
AUTH_V2 = OPT / "s12-f-07-authorization.v2.json"
REGISTRY_V6 = OPT / "experiment-registry.v6.json"
REGISTRY_V7 = OPT / "experiment-registry.v7.json"
G5_V6 = OPT / "g5-packet.v6.json"
G5_V7 = OPT / "g5-packet.v7.json"
G5_MD_V7 = ROOT / "docs/sprint-plans/sprint-12/g5-optimization.v7.md"
PROMPT_ARTIFACT = OPT / "s12-f-07-prompt-v4-relation-decision-rubric.v1.txt"


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def commit_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def execution_package() -> dict[str, Any]:
    return {
        "commitSha": commit_sha(),
        "digests": {
            "promptArtifact": digest(PROMPT_ARTIFACT),
            "promptImplementation": digest(
                ROOT / "apps/api/src/projecta_api/extraction/prompt.py"
            ),
            "stageRunnerCode": digest(
                ROOT / "scripts/run_sprint12_f07_prompt_experiment.py"
            ),
            "candidateRunnerCode": digest(
                ROOT / "scripts/run_sprint12_contract_candidate.py"
            ),
            "evaluatorCode": digest(ROOT / "scripts/sprint12_evaluator.py"),
        },
    }


def build_registry(prereg: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]:
    registry = copy.deepcopy(load(REGISTRY_V6))
    registry.pop("registryDigest", None)
    registry["registryVersion"] = "s12.experiment-registry.v7"
    registry["status"] = "G5_PREPARATION_DEVELOPMENT_OPEN_S12_F07_STAGE_A_AUTHORIZED"
    registry["openedExperimentId"] = "s12-f-07"
    registry["pendingExperiment"] = {
        "experimentId": "s12-f-07",
        "preregistration": {
            "artifact": PREREG.name,
            "digest": digest(PREREG),
        },
        "authorization": {
            "artifact": AUTH_V2.name,
            "status": "APPROVED_FOR_DEVELOPMENT_STAGE_A",
        },
        "executionAuthorized": True,
        "stageBAuthorized": False,
        "executionPackage": package,
    }
    experiment = next(
        item for item in registry["experiments"] if item["experimentId"] == "s12-f-07"
    )
    experiment["status"] = "REGISTERED"
    experiment["authorization"] = {
        "artifact": AUTH_V2.name,
        "status": "APPROVED_FOR_DEVELOPMENT_STAGE_A",
    }
    experiment["executionPackage"] = package
    registry["registryDigest"] = canonical_digest(registry)
    return registry


def build_authorization(
    prereg: dict[str, Any], registry: dict[str, Any], package: dict[str, Any]
) -> dict[str, Any]:
    authorization = copy.deepcopy(load(AUTH_V1))
    authorization.update(
        {
            "artifactVersion": "s12.s12-f-07.authorization.v2",
            "status": "APPROVED_FOR_DEVELOPMENT_STAGE_A",
            "approvalSource": "owner-authorized-after-execution-package-freeze",
            "preregistration": {"artifact": PREREG.name, "digest": digest(PREREG)},
            "registry": {
                "artifact": REGISTRY_V7.name,
                "digest": registry["registryDigest"],
            },
            "executionPackage": package,
            "authorizationHistory": {
                "priorArtifact": AUTH_V1.name,
                "priorDigest": digest(AUTH_V1),
                "priorStatus": "PENDING_USER_AUTHORIZATION",
            },
        }
    )
    return authorization


def build_g5(
    prereg: dict[str, Any],
    registry: dict[str, Any],
    authorization: dict[str, Any],
    package: dict[str, Any],
) -> dict[str, Any]:
    g5 = copy.deepcopy(load(G5_V6))
    g5.update(
        {
            "packetVersion": "s12.g5.packet.v7",
            "status": "G5_PREPARATION_DEVELOPMENT_OPEN_S12_F07_STAGE_A_AUTHORIZED",
            "registryVersion": registry["registryVersion"],
            "registryDigest": registry["registryDigest"],
            "executionPackage": package,
            "pendingExperiment": {
                "experimentId": "s12-f-07",
                "preregistrationArtifact": PREREG.name,
                "preregistrationDigest": digest(PREREG),
                "authorizationArtifact": AUTH_V2.name,
                "authorizationDigest": digest(AUTH_V2),
                "executionAuthorized": True,
                "stageBAuthorized": False,
            },
            "executionBlockedReasons": [
                "pricing must be bound and selection recomputed before selection or Stage B",
                "validation, candidate freeze and held-out remain locked",
            ],
            "selection": {
                "status": "NO_SELECTION",
                "reason": "Stage A is authorized but no Stage A result exists; pricing remains a pre-selection gate.",
                "heldOutInspected": False,
            },
        }
    )
    return g5


def write(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    prereg = load(PREREG)
    package = execution_package()
    registry = build_registry(prereg, package)
    authorization = build_authorization(prereg, registry, package)
    write(REGISTRY_V7, registry)
    write(AUTH_V2, authorization)
    g5 = build_g5(prereg, registry, authorization, package)
    write(G5_V7, g5)
    G5_MD_V7.write_text(
        "# Sprint 12 G5 Optimization Packet v7\n\n"
        "Status: `G5_PREPARATION_DEVELOPMENT_OPEN_S12_F07_STAGE_A_AUTHORIZED`\n\n"
        "S12-f-07 is authorized for one interleaved Stage A only: 16 development cases × 3 paired runs per arm, six total model invocations, no retry. Authorization v1 remains historical and immutable. Pricing is required before selection and Stage B, not before Stage A execution.\n\n"
        f"- Registry: `{REGISTRY_V7.name}` / `{registry['registryDigest']}`\n"
        f"- Authorization: `{AUTH_V2.name}` / `{digest(AUTH_V2)}`\n"
        f"- Frozen execution commit: `{package['commitSha']}`\n"
        "- Stage B, selection, validation, freeze and held-out remain locked.\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "authorization": AUTH_V2.name,
                "registry": REGISTRY_V7.name,
                "g5": G5_V7.name,
                "commitSha": package["commitSha"],
                "status": authorization["status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
