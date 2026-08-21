"""Read-only zero-call preflight for the RM-34 v8 authorization preparation."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PREPARATION = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm34-authorization-preparation.v1.json"
CURRENT = ROOT / "evaluation/sprint-12/current-state.v1.json"
PACKET = ROOT / "evaluation/sprint-12/optimization/g5-packet.v21.json"
OWNER = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm33-owner-review.v1.json"
TRANSITION = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm33-issuance-transition.v1.json"
PACKAGE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm32-execution-package.v8.json"
PREREG = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm32-preregistration.v8.json"
FREEZE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm32-technical-freeze.v8.json"
REPORT_V6 = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json"
OUTPUT_V8 = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v8.json"


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
        raise ValueError(f"working-tree digest mismatch: {path}")


def run_preflight() -> dict[str, object]:
    preparation = load(PREPARATION)
    current = load(CURRENT)
    packet = load(PACKET)
    owner = load(OWNER)
    transition = load(TRANSITION)
    package = load(PACKAGE)
    prereg = load(PREREG)
    freeze = load(FREEZE)
    report = load(REPORT_V6)

    if preparation.get("status") != "PREPARED_PENDING_RM35_OWNER_AUTHORIZATION":
        raise ValueError("RM-34 preparation is not pending RM-35")
    if preparation.get("providerExecutionAuthorized") is not False:
        raise ValueError("RM-34 preparation opens provider execution")
    if preparation.get("newAuthorizationIssued") is not False:
        raise ValueError("RM-34 preparation issues a new authorization")

    for key in (
        "providerExecutionAuthorized",
        "newAuthorizationIssued",
        "validationAccessAuthorized",
        "heldOutAccessAuthorized",
        "stageBAuthorized",
        "candidateSelectionAuthorized",
        "promotionAuthorized",
    ):
        if preparation["governanceLocks"].get(key) is not False:
            raise ValueError(f"RM-34 governance lock is open: {key}")

    for path, expected in (
        (CURRENT, preparation["currentState"]["digest"]),
        (PACKET, preparation["g5Packet"]["digest"]),
        (OWNER, preparation["rm33OwnerReview"]["digest"]),
        (TRANSITION, preparation["rm33IssuanceTransition"]["digest"]),
        (PREREG, preparation["preparedLineage"]["preregistration"]["digest"]),
        (PACKAGE, preparation["preparedLineage"]["executionPackage"]["digest"]),
        (FREEZE, preparation["preparedLineage"]["technicalFreeze"]["digest"]),
    ):
        require_digest(path, expected)

    if transition["ownerReview"]["digest"] != digest(OWNER):
        raise ValueError("RM-33 owner-review digest is not internally bound")
    if transition["currentDecisionState"] != {
        "preregistrationIssued": True,
        "technicalFreezeIssued": True,
        "providerExecutionAuthorized": False,
        "newAuthorizationIssued": False,
        "validationAccessAuthorized": False,
        "heldOutAccessAuthorized": False,
        "stageBAuthorized": False,
        "candidateSelectionAuthorized": False,
        "promotionAuthorized": False,
        "stageAReportExists": False,
        "nextPermittedAction": "S12_RM34_PREPARE_EXACT_V8_STAGE_A_AUTHORIZATION",
    }:
        raise ValueError("RM-33 transition current decision state changed")

    commit = preparation["preparedLineage"]["executionCommit"]
    runtime = package.get("runtimeBoundDigests")
    if not isinstance(runtime, dict) or len(runtime) != 22:
        raise ValueError("RM-32 runtime binding set is not exactly 22 blobs")
    for path_text, expected in runtime.items():
        if git_blob_digest(commit, str(path_text)) != expected:
            raise ValueError(f"exact runtime blob mismatch: {path_text}")
    for name in ("runner", "authorizationSchema", "reportSchema"):
        binding = preparation["exactRuntimeBindings"][name]
        if git_blob_digest(commit, binding["path"]) != binding["digest"]:
            raise ValueError(f"named runtime binding mismatch: {name}")
    if not preparation["exactRuntimeBindings"]["reportSchema"][
        "rm33DigestMatchesExactExecutionBlob"
    ]:
        if not preparation["integrityFindings"]["ownerReviewReconciliationRequired"]:
            raise ValueError("RM-33 report-schema digest discrepancy was suppressed")
        if not preparation["integrityFindings"]["providerExecutionBlockedUntilReconciled"]:
            raise ValueError("provider execution is not blocked for schema reconciliation")

    if current["status"] != "G5_F12_V8_LINEAGE_ISSUED_PROVIDER_AUTHORIZATION_PENDING":
        raise ValueError("authoritative current state changed")
    if packet["currentLineage"]["reportExists"] is not False:
        raise ValueError("v8 output is already present in current packet")
    if packet["authorizationBoundary"]["providerExecutionAuthorized"] is not False:
        raise ValueError("current packet opens provider execution")
    if OUTPUT_V8.exists():
        raise ValueError("RM-34 refuses to overwrite an existing v8 report")

    if digest(REPORT_V6) != preparation["preparedLineage"]["historicalReport"]["digest"]:
        raise ValueError("immutable v6 report digest changed")
    if report["accounting"]["providerCallsAttempted"] != 144:
        raise ValueError("immutable v6 accounting changed")
    if report["accounting"]["retryCount"] != 0:
        raise ValueError("immutable v6 retry accounting changed")

    return {
        "status": "F12_RM34_PREPARED_ZERO_CALL",
        "preparationScope": "S12-RM-34",
        "lineageVersion": "v8",
        "executionCommitSha": commit,
        "runtimeBlobCount": len(runtime),
        "providerCalls": 0,
        "retryCount": 0,
        "mockAuthorizedCalls": preparation["mockEvidence"]["authorizedProviderCalls"],
        "mockRelationBranches": preparation["mockEvidence"]["relationBranches"],
        "historicalReportDigest": digest(REPORT_V6),
        "outputPath": OUTPUT_V8.relative_to(ROOT).as_posix(),
        "nextGate": "S12-RM-35_OWNER_AUTHORIZATION_REVIEW",
        "ownerReviewReconciliationRequired": preparation["integrityFindings"][
            "ownerReviewReconciliationRequired"
        ],
    }


if __name__ == "__main__":
    print(json.dumps(run_preflight(), ensure_ascii=False, indent=2, sort_keys=True))
