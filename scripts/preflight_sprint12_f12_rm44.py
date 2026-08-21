"""Read-only zero-call preflight for the RM-44 v9 authorization preparation."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PREPARATION = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm44-authorization-preparation.v1.json"
CURRENT = ROOT / "evaluation/sprint-12/current-state.v1.json"
PACKET = ROOT / "evaluation/sprint-12/optimization/g5-packet.v29.rm43-issuance.json"
OWNER = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm43-owner-review.v1.json"
TRANSITION = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm43-issuance-transition.v1.json"
PACKAGE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm42-execution-package.v9.json"
PREREG = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm42-preregistration.v9.json"
FREEZE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm42-technical-freeze.v9.json"
REPORT_V6 = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json"
OUTPUT_V8 = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v8.json"
OUTPUT_V9 = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v9.json"
RM44_PREFLIGHT = ROOT / "scripts/preflight_sprint12_f12_rm44.py"


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


def require_preparation_evidence(preparation: dict[str, Any]) -> str:
    """Verify this preflight from external preparation evidence.

    The preparation binds this script, but the script never binds its own
    preparation digest.  That one-way binding keeps the evidence check
    non-circular while exact runtime custody remains Git-blob based.
    """

    evidence = preparation.get("preparationEvidence")
    if not isinstance(evidence, dict) or evidence.get("digestMode") != "working_tree_sha256":
        raise ValueError("RM-44 preparation evidence digest mode is not explicit")
    binding = evidence.get("rm44Preflight")
    if not isinstance(binding, dict) or binding.get("path") != "scripts/preflight_sprint12_f12_rm44.py":
        raise ValueError("RM-44 preflight preparation evidence is not bound")
    expected = binding.get("digest")
    if not isinstance(expected, str) or not expected.startswith("sha256:"):
        raise ValueError("RM-44 preflight preparation evidence digest is invalid")
    require_digest(RM44_PREFLIGHT, expected)
    return expected


def require_exact_runtime_bindings(preparation: dict[str, Any], package: dict[str, Any]) -> int:
    commit = preparation["preparedLineage"]["executionCommit"]
    runtime = package.get("runtimeBoundDigests")
    if not isinstance(runtime, dict) or len(runtime) != 19:
        raise ValueError("RM-42 runtime binding set is not exactly 19 blobs")
    for path_text, expected in runtime.items():
        if git_blob_digest(commit, str(path_text)) != expected:
            raise ValueError(f"exact runtime blob mismatch: {path_text}")
    named = preparation["exactRuntimeBindings"]
    for name in ("runner", "reportSchema", "authorizationSchema"):
        binding = named.get(name)
        if not isinstance(binding, dict) or git_blob_digest(commit, binding["path"]) != binding["digest"]:
            raise ValueError(f"named runtime binding mismatch: {name}")
    return len(runtime)


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

    if preparation.get("status") != "PREPARED_PENDING_RM45_OWNER_AUTHORIZATION_REVIEW":
        raise ValueError("RM-44 preparation is not pending RM-45")
    if preparation.get("providerExecutionAuthorized") is not False or preparation.get("newAuthorizationIssued") is not False:
        raise ValueError("RM-44 preparation opens or issues provider authorization")
    preparation_preflight_digest = require_preparation_evidence(preparation)

    for key in (
        "providerExecutionAuthorized", "newAuthorizationIssued", "rerunAuthorized",
        "retryAuthorized", "validationAccessAuthorized", "heldOutAccessAuthorized",
        "stageBAuthorized", "candidateSelectionAuthorized", "promotionAuthorized",
    ):
        if preparation["governanceLocks"].get(key) is not False:
            raise ValueError(f"RM-44 governance lock is open: {key}")

    for path, expected in (
        (CURRENT, preparation["authoritativeState"]["digest"]),
        (PACKET, preparation["rm43Issuance"]["g5PacketDigest"]),
        (OWNER, preparation["rm43OwnerReview"]["digest"]),
        (TRANSITION, preparation["rm43Issuance"]["transitionDigest"]),
        (PREREG, preparation["preparedLineage"]["preregistration"]["digest"]),
        (PACKAGE, preparation["preparedLineage"]["executionPackage"]["digest"]),
        (FREEZE, preparation["preparedLineage"]["technicalFreeze"]["digest"]),
    ):
        require_digest(path, expected)

    if owner["decision"]["preregistrationIssued"] is not True or owner["decision"]["technicalFreezeIssued"] is not True:
        raise ValueError("RM-43 owner issuance is not bound")
    if any(owner["decision"].get(key) is not False for key in (
        "providerExecutionAuthorized", "newAuthorizationIssued", "rerunAuthorized",
        "retryAuthorized", "validationAccessAuthorized", "heldOutAccessAuthorized",
        "stageBAuthorized", "candidateSelectionAuthorized", "promotionAuthorized",
    )):
        raise ValueError("RM-43 owner review has an open downstream lock")
    if transition["ownerReview"]["digest"] != digest(OWNER):
        raise ValueError("RM-43 transition owner-review digest is not internally bound")
    expected_state = {
        "preregistrationIssued": True, "technicalFreezeIssued": True,
        "providerExecutionAuthorized": False, "newAuthorizationIssued": False,
        "rerunAuthorized": False, "retryAuthorized": False,
        "validationAccessAuthorized": False, "heldOutAccessAuthorized": False,
        "stageBAuthorized": False, "candidateSelectionAuthorized": False,
        "promotionAuthorized": False, "stageAReportExists": False,
        "nextPermittedAction": "PREPARE_EXACT_V9_STAGE_A_AUTHORIZATION_OFFLINE",
    }
    if transition["currentDecisionState"] != expected_state:
        raise ValueError("RM-43 transition current decision state changed")

    if current["status"] != "G5_F12_CORRECTED_V9_LINEAGE_ISSUED_PROVIDER_AUTHORIZATION_PENDING":
        raise ValueError("authoritative current state changed")
    if packet["currentLineage"]["stageAReportExists"] is not False or packet["authorizationBoundary"]["providerExecutionAuthorized"] is not False:
        raise ValueError("authoritative G5 packet opens v9 execution")
    if prereg["executionCommitSha"] != preparation["preparedLineage"]["executionCommit"] or freeze["executionCommitSha"] != preparation["preparedLineage"]["executionCommit"]:
        raise ValueError("RM-42 package/prereg/freeze commit chain changed")
    if OUTPUT_V8.exists() or OUTPUT_V9.exists():
        raise ValueError("RM-44 refuses to reuse or overwrite v8/v9 output")

    runtime_blob_count = require_exact_runtime_bindings(preparation, package)
    if digest(REPORT_V6) != preparation["historicalCustody"]["historicalV6ReportDigest"]:
        raise ValueError("immutable v6 report digest changed")
    if report["accounting"]["providerCallsAttempted"] != 144 or report["accounting"]["retryCount"] != 0:
        raise ValueError("immutable v6 accounting changed")
    if preparation["providerCallsPerformedAtPreparation"] != 0:
        raise ValueError("RM-44 preparation performed provider calls")

    return {
        "status": "F12_RM44_PREPARED_ZERO_CALL",
        "preparationScope": "S12-RM-44",
        "lineageVersion": "v9",
        "executionCommitSha": preparation["preparedLineage"]["executionCommit"],
        "runtimeBlobCount": runtime_blob_count,
        "providerCalls": 0,
        "retryCount": 0,
        "plannedProviderCalls": preparation["executionBounds"]["providerCalls"],
        "plannedRelationBranches": preparation["executionBounds"]["relationBranchOutputs"],
        "mockAuthorizedCalls": preparation["mockEvidence"]["authorizedProviderCalls"],
        "mockRelationBranches": preparation["mockEvidence"]["relationBranches"],
        "historicalV6Digest": digest(REPORT_V6),
        "outputPath": OUTPUT_V9.relative_to(ROOT).as_posix(),
        "nextGate": "S12-RM-45_OWNER_AUTHORIZATION_REVIEW",
        "preparationPreflightDigest": preparation_preflight_digest,
    }


if __name__ == "__main__":
    print(json.dumps(run_preflight(), ensure_ascii=False, indent=2, sort_keys=True))
