"""Read-only pre-execution preflight for the RM-45 v9 authorization."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm45-authorization.v9.json"
OWNER_REVIEW = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm45-owner-review.v1.json"
TRANSITION = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm45-authorization-transition.v1.json"
PREPARATION = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm44-authorization-preparation.v1.json"
PACKAGE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm42-execution-package.v9.json"
PREREG = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm42-preregistration.v9.json"
FREEZE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm42-technical-freeze.v9.json"
AUTHORIZATION_SCHEMA = ROOT / "evaluation/sprint-12/harness/s12-f-12-authorization.schema.v9.json"
REPORT_V6 = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json"
OUTPUT_V8 = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v8.json"
OUTPUT_V9 = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v9.json"
CURRENT_STATE = ROOT / "evaluation/sprint-12/current-state.v1.json"
PACKET = ROOT / "evaluation/sprint-12/optimization/g5-packet.v31.rm45-authorization.json"


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"artifact must be an object: {path}")
    return value


def git_blob_digest(commit: str, path_text: str) -> str:
    blob = subprocess.check_output(["git", "show", f"{commit}:{path_text}"], cwd=ROOT)
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def require_digest(path: Path, expected: str) -> None:
    if digest(path) != expected:
        raise ValueError(f"digest mismatch: {path}")


def require_false(mapping: dict[str, Any], *keys: str) -> None:
    for key in keys:
        if mapping.get(key) is not False:
            raise ValueError(f"governance lock is open: {key}")


def run_preflight() -> dict[str, object]:
    authorization = load(AUTHORIZATION)
    owner_review = load(OWNER_REVIEW)
    transition = load(TRANSITION)
    preparation = load(PREPARATION)
    package = load(PACKAGE)
    prereg = load(PREREG)
    freeze = load(FREEZE)
    current = load(CURRENT_STATE)
    packet = load(PACKET)
    runtime = load(ROOT / "evaluation/sprint-12/harness/s12-f-12-runtime-configuration.v1.json")
    report_v6 = load(REPORT_V6)

    schema = load(AUTHORIZATION_SCHEMA)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(authorization),
        key=lambda error: list(error.path),
    )
    if errors:
        raise ValueError(f"RM-45 authorization schema failed: {errors[0].message}")
    if authorization["providerExecutionAuthorized"] is not True:
        raise ValueError("RM-45 authorization does not open the reviewed execution")
    if authorization["providerCalls"] != 144 or authorization["retryPolicy"] != "none":
        raise ValueError("RM-45 authorization bounds changed")
    if authorization["costCeilingUsd"] != "10.00":
        raise ValueError("RM-45 authorization cost ceiling changed")
    require_false(
        authorization,
        "heldOutInspected",
        "heldOutAccessAuthorized",
        "validationAccessAuthorized",
        "stageBAuthorized",
        "candidateSelectionAuthorized",
        "promotionAuthorized",
    )

    if owner_review["status"] != "OWNER_REVIEW_APPROVED_ONE_BOUNDED_V9_STAGE_A":
        raise ValueError("RM-45 owner review status changed")
    if owner_review["issuedAuthorization"]["digest"] != digest(AUTHORIZATION):
        raise ValueError("RM-45 owner-review authorization digest mismatch")
    if transition["ownerReview"]["digest"] != digest(OWNER_REVIEW):
        raise ValueError("RM-45 transition owner-review digest mismatch")
    if transition["authorization"]["digest"] != digest(AUTHORIZATION):
        raise ValueError("RM-45 transition authorization digest mismatch")
    if transition["preparation"]["digest"] != digest(PREPARATION):
        raise ValueError("RM-45 transition preparation digest mismatch")
    if transition["currentDecisionState"] != {
        "providerExecutionAuthorized": True,
        "newAuthorizationIssued": True,
        "authorizedExecutions": 1,
        "authorizedProviderCalls": 144,
        "providerCallsPerformed": 0,
        "stageAReportExists": False,
        "retryAuthorized": False,
        "outputOverwriteAuthorized": False,
        "validationAccessAuthorized": False,
        "heldOutAccessAuthorized": False,
        "stageBAuthorized": False,
        "candidateSelectionAuthorized": False,
        "promotionAuthorized": False,
        "nextPermittedAction": "EXECUTE_EXACT_S12_F12_V9_DEVELOPMENT_STAGE_A_ONCE",
    }:
        raise ValueError("RM-45 transition decision state changed")

    commit = authorization["executionCommitSha"]
    if commit != package["executionCommitSha"] or commit != prereg["executionCommitSha"] or commit != freeze["executionCommitSha"]:
        raise ValueError("RM-45 exact execution commit chain changed")
    if authorization["executionPackageDigest"] != digest(PACKAGE):
        raise ValueError("RM-45 execution-package digest mismatch")
    if authorization["technicalFreezeDigest"] != digest(FREEZE):
        raise ValueError("RM-45 technical-freeze digest mismatch")
    if authorization["outputPath"] != "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v9.json":
        raise ValueError("RM-45 output path changed")
    if OUTPUT_V8.exists() or OUTPUT_V9.exists():
        raise ValueError("RM-45 preflight refuses v8/v9 output reuse or overwrite")

    bindings = package.get("runtimeBoundDigests")
    if not isinstance(bindings, dict) or len(bindings) != 19:
        raise ValueError("RM-45 runtime binding set is not exactly 19 blobs")
    for path_text, expected in bindings.items():
        if git_blob_digest(commit, str(path_text)) != expected:
            raise ValueError(f"RM-45 exact runtime blob mismatch: {path_text}")
    named = preparation["exactRuntimeBindings"]
    for name in ("runner", "reportSchema", "authorizationSchema"):
        binding = named[name]
        if git_blob_digest(commit, binding["path"]) != binding["digest"]:
            raise ValueError(f"RM-45 named runtime blob mismatch: {name}")

    contract = preparation["runtimeContract"]
    if contract["providerType"] != runtime["providerType"] or contract["transport"] != runtime["transport"]:
        raise ValueError("RM-45 provider transport contract changed")
    if contract["model"] != runtime["model"] or contract["promptVersion"] != runtime["promptVersion"]:
        raise ValueError("RM-45 model or prompt contract changed")
    if contract["datasetPath"] != "evaluation/sprint-12/corpus/v3-frozen/atomic-v3.frozen.v1.json":
        raise ValueError("RM-45 dataset boundary changed")

    if current["status"] != "G5_F12_CORRECTED_V9_LINEAGE_AUTHORIZED_ONE_STAGE_A_PENDING_EXECUTION":
        raise ValueError("authoritative current state is not RM-45 authorized")
    if current["currentEvidence"]["g5Packet"]["digest"] != digest(PACKET):
        raise ValueError("authoritative G5 packet digest mismatch")
    if packet["status"] != current["status"]:
        raise ValueError("authoritative G5 packet status mismatch")
    lineage = current["experimentState"]["currentLineage"]
    if lineage != {
        "lineageVersion": "v9",
        "preregistrationIssued": True,
        "technicalFreezeIssued": True,
        "authorizedExecutions": 1,
        "authorizedProviderCalls": 144,
        "providerCallsPerformed": 0,
        "providerResponsesReceived": 0,
        "relationBranchOutputs": None,
        "retryCount": 0,
        "accountingComplete": False,
        "aggregateCostAvailable": False,
        "stageAReportExists": False,
        "providerExecutionAuthorized": True,
        "newAuthorizationIssued": True,
        "authorizationSpent": False,
    }:
        raise ValueError("authoritative current v9 lineage state changed")
    governance = current["experimentState"]["currentGovernance"]
    require_false(
        governance,
        "validationAccessAuthorized",
        "heldOutAccessAuthorized",
        "stageBAuthorized",
        "candidateSelectionAuthorized",
        "promotionAuthorized",
    )
    if packet["currentLineage"]["stageAReportExists"] is not False:
        raise ValueError("authoritative packet reports a v9 output")
    if packet["authorizationBoundary"]["providerExecutionAuthorized"] is not True:
        raise ValueError("authoritative packet does not reflect RM-45 authority")
    require_false(
        packet["authorizationBoundary"],
        "rerunAuthorized",
        "retryAuthorized",
        "outputOverwriteAuthorized",
        "validationAccessAuthorized",
        "heldOutAccessAuthorized",
        "stageBAuthorized",
        "candidateSelectionAuthorized",
        "promotionAuthorized",
        "downstreamAccessAuthorized",
    )

    if digest(REPORT_V6) != preparation["historicalCustody"]["historicalV6ReportDigest"]:
        raise ValueError("immutable v6 report digest changed")
    if report_v6["accounting"]["providerCallsAttempted"] != 144 or report_v6["accounting"]["retryCount"] != 0:
        raise ValueError("immutable v6 accounting changed")

    return {
        "status": "F12_RM45_AUTHORIZED_ZERO_CALL_PRECHECK",
        "authorization": AUTHORIZATION.relative_to(ROOT).as_posix(),
        "executionCommitSha": commit,
        "authorizedExecutions": 1,
        "authorizedProviderCalls": 144,
        "providerCallsPerformed": 0,
        "runtimeBlobCount": len(bindings),
        "relationBranchOutputs": 96,
        "retryCount": 0,
        "costCeilingUsd": "10.00",
        "outputPath": authorization["outputPath"],
        "outputExists": OUTPUT_V9.exists(),
        "historicalReportDigest": digest(REPORT_V6),
        "nextGate": "S12-RM-46_EXECUTE_EXACT_V9_STAGE_A_ONCE",
    }


if __name__ == "__main__":
    print(json.dumps(run_preflight(), ensure_ascii=False, indent=2, sort_keys=True))
