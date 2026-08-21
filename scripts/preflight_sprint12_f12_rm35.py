"""Read-only pre-execution preflight for the RM-35 v8 authorization."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm35-authorization.v8.json"
OWNER_REVIEW = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm35-owner-review.v1.json"
TRANSITION = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm35-authorization-transition.v1.json"
PREPARATION = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm34-authorization-preparation.v1.json"
PACKAGE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm32-execution-package.v8.json"
FREEZE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm32-technical-freeze.v8.json"
AUTHORIZATION_SCHEMA = ROOT / "evaluation/sprint-12/harness/s12-f-12-authorization.schema.v8.json"
REPORT_V6 = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json"
OUTPUT_V8 = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v8.json"
CURRENT_STATE = ROOT / "evaluation/sprint-12/current-state.v1.json"
PACKET = ROOT / "evaluation/sprint-12/optimization/g5-packet.v23.rm35-authorization.json"


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


def _require_false(mapping: dict[str, Any], *keys: str) -> None:
    for key in keys:
        if mapping.get(key) is not False:
            raise ValueError(f"governance lock is open: {key}")


def run_preflight() -> dict[str, object]:
    authorization = load(AUTHORIZATION)
    owner_review = load(OWNER_REVIEW)
    transition = load(TRANSITION)
    preparation = load(PREPARATION)
    package = load(PACKAGE)
    freeze = load(FREEZE)
    current = load(CURRENT_STATE)
    packet = load(PACKET)
    report_v6 = load(REPORT_V6)

    schema = load(AUTHORIZATION_SCHEMA)
    errors = sorted(Draft202012Validator(schema).iter_errors(authorization), key=lambda error: list(error.path))
    if errors:
        raise ValueError(f"RM-35 authorization schema failed: {errors[0].message}")
    if authorization["providerExecutionAuthorized"] is not True:
        raise ValueError("RM-35 authorization does not open exactly the reviewed execution")
    if authorization["providerCalls"] != 144 or authorization["retryPolicy"] != "none":
        raise ValueError("RM-35 authorization bounds changed")
    _require_false(
        authorization,
        "heldOutInspected",
        "heldOutAccessAuthorized",
        "validationAccessAuthorized",
        "stageBAuthorized",
        "candidateSelectionAuthorized",
        "promotionAuthorized",
    )

    if owner_review["status"] != "OWNER_REVIEW_APPROVED_ONE_BOUNDED_V8_STAGE_A":
        raise ValueError("RM-35 owner review status changed")
    if owner_review["issuedAuthorization"]["digest"] != digest(AUTHORIZATION):
        raise ValueError("RM-35 owner review authorization digest mismatch")
    if transition["ownerReview"]["digest"] != digest(OWNER_REVIEW):
        raise ValueError("RM-35 transition owner-review digest mismatch")
    if transition["authorization"]["digest"] != digest(AUTHORIZATION):
        raise ValueError("RM-35 transition authorization digest mismatch")
    if transition["preparation"]["digest"] != digest(PREPARATION):
        raise ValueError("RM-35 transition preparation digest mismatch")
    if transition["currentDecisionState"] != {
        "providerExecutionAuthorized": True,
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
        "nextPermittedAction": "EXECUTE_EXACT_S12_F12_V8_DEVELOPMENT_STAGE_A_ONCE",
    }:
        raise ValueError("RM-35 transition decision state changed")

    if authorization["executionCommitSha"] != transition["authorizedLineage"]["executionCommit"]:
        raise ValueError("RM-35 authorization commit mismatch")
    if authorization["executionPackageDigest"] != digest(PACKAGE):
        raise ValueError("RM-35 execution-package digest mismatch")
    if authorization["technicalFreezeDigest"] != digest(FREEZE):
        raise ValueError("RM-35 technical-freeze digest mismatch")
    if authorization["outputPath"] != "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v8.json":
        raise ValueError("RM-35 output path changed")
    if OUTPUT_V8.exists():
        raise ValueError("RM-35 preflight refuses an existing v8 output")

    commit = authorization["executionCommitSha"]
    runtime = package.get("runtimeBoundDigests")
    if not isinstance(runtime, dict) or len(runtime) != 22:
        raise ValueError("RM-35 runtime binding set is not exactly 22 blobs")
    for path_text, expected in runtime.items():
        if git_blob_digest(commit, str(path_text)) != expected:
            raise ValueError(f"RM-35 exact runtime blob mismatch: {path_text}")

    if current["status"] != "G5_F12_V8_AUTHORIZED_PENDING_EXECUTION":
        raise ValueError("authoritative current state is not RM-35 authorized")
    if packet["status"] != "G5_F12_V8_AUTHORIZED_PENDING_EXECUTION":
        raise ValueError("authoritative G5 packet is not RM-35 authorized")
    current_lineage = current["experimentState"]["currentLineage"]
    if current_lineage != {
        "lineageVersion": "v8",
        "preregistrationIssued": True,
        "technicalFreezeIssued": True,
        "authorizedExecutions": 1,
        "authorizedProviderCalls": 144,
        "providerCallsPerformed": 0,
        "relationBranchOutputs": 0,
        "retryCount": 0,
        "stageAReportExists": False,
        "providerExecutionAuthorized": True,
        "newAuthorizationIssued": True,
    }:
        raise ValueError("authoritative current v8 lineage state changed")
    _require_false(
        current["experimentState"]["currentGovernance"],
        "validationAccessAuthorized",
        "heldOutAccessAuthorized",
        "stageBAuthorized",
        "candidateSelectionAuthorized",
        "promotionAuthorized",
    )
    if packet["currentLineage"]["reportExists"] is not False:
        raise ValueError("authoritative packet reports a v8 output")
    if packet["authorizationBoundary"]["providerExecutionAuthorized"] is not True:
        raise ValueError("authoritative packet does not reflect RM-35 authority")
    _require_false(
        packet["authorizationBoundary"],
        "validationAuthorized",
        "validationAccessAuthorized",
        "heldOutAccessAuthorized",
        "stageBAuthorized",
        "candidateSelectionAuthorized",
        "promotionAuthorized",
        "retryAuthorized",
        "outputOverwriteAuthorized",
    )

    if digest(REPORT_V6) != "sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233":
        raise ValueError("immutable v6 report digest changed")
    if report_v6["accounting"]["providerCallsAttempted"] != 144 or report_v6["accounting"]["retryCount"] != 0:
        raise ValueError("immutable v6 accounting changed")

    return {
        "status": "F12_RM35_AUTHORIZED_ZERO_CALL_PRECHECK",
        "authorization": AUTHORIZATION.relative_to(ROOT).as_posix(),
        "executionCommitSha": commit,
        "authorizedExecutions": 1,
        "authorizedProviderCalls": 144,
        "providerCallsPerformed": 0,
        "runtimeBlobCount": len(runtime),
        "relationBranchOutputs": 96,
        "retryCount": 0,
        "outputPath": authorization["outputPath"],
        "outputExists": OUTPUT_V8.exists(),
        "historicalReportDigest": digest(REPORT_V6),
        "nextGate": "S12-RM-36_EXECUTE_EXACT_V8_STAGE_A_ONCE",
    }


if __name__ == "__main__":
    print(json.dumps(run_preflight(), ensure_ascii=False, indent=2, sort_keys=True))
