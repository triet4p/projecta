"""Publish the post-revision S12-f-08 governance chain after package freeze."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import run_sprint12_f08_prompt_experiment as runner


ROOT = Path(__file__).resolve().parents[1]
OPT = ROOT / "evaluation/sprint-12/optimization"
PREREG_V1 = OPT / "s12-f-08-relation-prompt-preregistration.v1.json"
PREREG_V2 = OPT / "s12-f-08-relation-prompt-preregistration.v2.json"
REGISTRY_V8 = OPT / "experiment-registry.v8.json"
REGISTRY_V9 = OPT / "experiment-registry.v9.json"
G5_V8 = OPT / "g5-packet.v8.json"
G5_V9 = OPT / "g5-packet.v9.json"
AUTH_V1 = OPT / "s12-f-08-authorization.v1.json"
AUTH_V2 = OPT / "s12-f-08-authorization.v2.json"
PRICING = OPT / "s12-f-08-pricing-deepseek-v4-flash.v1.json"
PROMPT = OPT / "s12-f-08-prompt-v5-composed-relation-contract.v1.txt"
MANIFEST = ROOT / "evaluation/sprint-12/corpus/manifests/development-validation.manifest.v2.json"


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def current_commit() -> str:
    return subprocess.check_output(
        ("git", "rev-parse", "HEAD"), cwd=ROOT, text=True
    ).strip()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite immutable artifact: {path}")
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def execution_package(commit_sha: str) -> dict[str, Any]:
    return {
        "commitSha": commit_sha,
        "digests": runner.execution_package_digests(),
        "oneAttemptPerCase": True,
        "retryPolicy": "none",
        "stage": "A",
    }


def build_prereg(package: dict[str, Any]) -> dict[str, Any]:
    prereg = copy.deepcopy(load(PREREG_V1))
    prereg["artifactVersion"] = "s12.s12-f-08.relation-prompt-preregistration.v2"
    prereg["fixedArtifacts"]["evaluator"] = "s12.evaluator.v2"
    prereg["fixedArtifacts"]["datasetManifestDigest"] = load(MANIFEST)["manifestDigest"]
    prereg["fixedArtifacts"]["runner"] = "scripts/run_sprint12_f08_prompt_experiment.py"
    prereg["fixedArtifacts"]["pricingArtifact"] = PRICING.name
    prereg["promptArtifact"]["implementationDigest"] = file_digest(
        ROOT / "apps/api/src/projecta_api/extraction/prompt.py"
    )
    prereg["promptArtifact"]["digest"] = file_digest(PROMPT)
    prereg["pricingContract"] = {
        "artifact": PRICING.name,
        "artifactDigest": file_digest(PRICING),
        "model": "deepseek-v4-flash",
        "requiredBeforeExecution": True,
        "requiredBeforeSelection": True,
        "status": "BOUND",
        "sourceUrl": "https://api-docs.deepseek.com/quick_start/pricing",
        "retrievedAt": "2026-08-16",
        "currency": "USD",
        "unit": "USD per 1M tokens",
        "rateClasses": [
            "inputCacheHitUsdPer1M",
            "inputCacheMissUsdPer1M",
            "outputUsdPer1M",
        ],
    }
    prereg["executionPackage"] = package
    prereg["measurementContract"] = {
        "evaluatorVersion": "s12.evaluator.v2",
        "positiveRelationDenominator": "fail-closed-all-positive-gold-case-runs",
        "relationInstrumentationVersion": "s12.relation-instrumentation.v2",
        "usageContract": "cache-hit-cache-miss-output-v1",
    }
    prereg["sourceEvidence"]["f07ScoringErratumDigest"] = file_digest(
        OPT / prereg["sourceEvidence"]["f07ScoringErratum"]
    )
    return prereg


def build_registry(prereg: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]:
    registry = copy.deepcopy(load(REGISTRY_V8))
    registry.pop("registryDigest", None)
    registry["registryVersion"] = "s12.experiment-registry.v9"
    registry["evaluatorVersion"] = "s12.evaluator.v2"
    registry["openedExperimentId"] = "s12-f-08"
    f08 = next(item for item in registry["experiments"] if item["experimentId"] == "s12-f-08")
    f08.update(
        {
            "status": "REGISTERED",
            "evaluatorVersion": "s12.evaluator.v2",
            "preregistration": {
                "artifact": PREREG_V2.name,
                "digest": file_digest(PREREG_V2),
            },
            "executionPackage": package,
            "pricingContract": prereg["pricingContract"],
            "measurementContract": prereg["measurementContract"],
        }
    )
    registry["pendingExperiment"] = {
        "experimentId": "s12-f-08",
        "preregistration": {
            "artifact": PREREG_V2.name,
            "digest": file_digest(PREREG_V2),
        },
        "authorization": {
            "artifact": AUTH_V2.name,
            "status": "APPROVED_FOR_DEVELOPMENT_STAGE_A",
        },
        "executionAuthorized": True,
        "stageBAuthorized": False,
    }
    registry["status"] = "G5_DEVELOPMENT_STAGE_A_AUTHORIZED_S12_F08"
    registry["registryDigest"] = canonical_digest(registry)
    return registry


def build_authorization(
    prereg: dict[str, Any], registry: dict[str, Any], package: dict[str, Any]
) -> dict[str, Any]:
    return {
        "artifactVersion": "s12.s12-f-08.authorization.v2",
        "experimentId": "s12-f-08",
        "status": "APPROVED_FOR_DEVELOPMENT_STAGE_A",
        "approvalSource": "owner-approved-development-stage-a",
        "authorizationHistory": {
            "priorArtifact": AUTH_V1.name,
            "priorDigest": file_digest(AUTH_V1),
            "priorStatus": load(AUTH_V1)["status"],
        },
        "preregistration": {
            "artifact": PREREG_V2.name,
            "digest": file_digest(PREREG_V2),
        },
        "registry": {
            "artifact": REGISTRY_V9.name,
            "digest": registry["registryDigest"],
            "fileDigest": file_digest(REGISTRY_V9),
        },
        "executionPackage": package,
        "pricingContract": prereg["pricingContract"],
        "scope": {
            "stage": "A",
            "caseCount": 16,
            "independentPairedRuns": 3,
            "developmentOnly": True,
            "heldOutInspected": False,
            "noRetryWithinEachRun": True,
            "stageBAuthorized": False,
            "validationAuthorized": False,
        },
        "credentialIncluded": False,
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
    }


def build_g5(
    prereg: dict[str, Any], registry: dict[str, Any], auth: dict[str, Any]
) -> dict[str, Any]:
    old = load(G5_V8)
    packet = copy.deepcopy(old)
    packet.update(
        {
            "packetVersion": "s12.g5.packet.v9",
            "status": "G5_DEVELOPMENT_STAGE_A_AUTHORIZED_S12_F08",
            "approvalStatus": "APPROVED_FOR_DEVELOPMENT_STAGE_A",
            "registryVersion": registry["registryVersion"],
            "registryDigest": registry["registryDigest"],
            "pricingContract": prereg["pricingContract"],
            "executionBlockedReasons": [
                "S12-f-07 is closed as COMPLETED_REJECTED with no Stage B or selection",
                "S12-f-08 Stage A is authorized once and must not retry or overwrite evidence",
            ],
            "pendingExperiment": {
                "experimentId": "s12-f-08",
                "preregistrationArtifact": PREREG_V2.name,
                "preregistrationDigest": file_digest(PREREG_V2),
                "authorizationArtifact": AUTH_V2.name,
                "authorizationDigest": file_digest(AUTH_V2),
                "executionAuthorized": True,
                "stageBAuthorized": False,
            },
            "selection": {
                "status": "NO_SELECTION",
                "reason": "S12-f-08 Stage A is authorized; no Stage B or candidate selection is authorized.",
                "heldOutInspected": False,
            },
        }
    )
    return packet


def main() -> None:
    commit_sha = current_commit()
    if not subprocess.run(
        ("git", "diff", "--quiet"), cwd=ROOT, check=False
    ).returncode == 0:
        raise SystemExit("execution package must be committed before governance publication")
    package = execution_package(commit_sha)
    prereg = build_prereg(package)
    write_new(PREREG_V2, prereg)
    registry = build_registry(prereg, package)
    write_new(REGISTRY_V9, registry)
    authorization = build_authorization(prereg, registry, package)
    write_new(AUTH_V2, authorization)
    g5 = build_g5(prereg, registry, authorization)
    write_new(G5_V9, g5)
    print(json.dumps({
        "commitSha": commit_sha,
        "preregistrationDigest": file_digest(PREREG_V2),
        "registryDigest": registry["registryDigest"],
        "authorizationDigest": file_digest(AUTH_V2),
        "g5Digest": file_digest(G5_V9),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
