"""Zero-call preflight for the issued RM-43 v9 lineage.

This check validates the immutable RM-43 owner/transition records against the
RM-42 preparation artifacts and exact runtime Git blobs.  It never loads a
provider adapter and never creates an authorization or report.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import preflight_sprint12_f12_rm42 as rm42

ROOT = Path(__file__).resolve().parents[1]
OPT = ROOT / "evaluation/sprint-12/optimization"
OWNER = OPT / "s12-f-12-rm43-owner-review.v1.json"
TRANSITION = OPT / "s12-f-12-rm43-issuance-transition.v1.json"
PACKAGE = OPT / "s12-f-12-rm42-execution-package.v9.json"
PREREG = OPT / "s12-f-12-rm42-preregistration.v9.json"
FREEZE = OPT / "s12-f-12-rm42-technical-freeze.v9.json"
REPORT_V6 = OPT / "s12-f-12-stage-a-report.v6.json"
REPORT_V8 = OPT / "s12-f-12-stage-a-report.v8.json"
REPORT_V9 = OPT / "s12-f-12-stage-a-report.v9.json"

EXECUTION_COMMIT = "f81103b0b8f6c19a65b8d37ccfb0d08e8aeee11e"
V6_DIGEST = "sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233"


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"artifact must be an object: {path}")
    return value


def git_blob_digest(commit: str, path_text: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path_text}"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    return "sha256:" + hashlib.sha256(result.stdout).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def run_preflight() -> dict[str, object]:
    owner = load(OWNER)
    transition = load(TRANSITION)
    package = load(PACKAGE)
    prereg = load(PREREG)
    freeze = load(FREEZE)

    _require(owner["status"] == "OWNER_ISSUANCE_REVIEW_APPROVED_ISSUANCE_ONLY", "RM-43 owner review status mismatch")
    _require(
        transition["status"] == "CORRECTED_V9_PREREGISTRATION_AND_FREEZE_ISSUED_PROVIDER_AUTHORIZATION_PENDING",
        "RM-43 transition status mismatch",
    )
    _require(transition["ownerReview"]["digest"] == digest(OWNER), "RM-43 owner review digest mismatch")
    _require(owner["reviewedLineage"]["executionCommit"] == EXECUTION_COMMIT, "RM-43 execution commit mismatch")
    _require(transition["issuedLineage"]["executionCommit"] == EXECUTION_COMMIT, "RM-43 transition execution commit mismatch")
    _require(package["executionCommitSha"] == prereg["executionCommitSha"] == freeze["executionCommitSha"] == EXECUTION_COMMIT, "RM-42 lineage commit mismatch")

    for artifact, field, path in (
        (owner["reviewedLineage"], "preregistration", PREREG),
        (owner["reviewedLineage"], "executionPackage", PACKAGE),
        (owner["reviewedLineage"], "technicalFreeze", FREEZE),
        (transition["issuedLineage"], "preregistration", PREREG),
        (transition["issuedLineage"], "executionPackage", PACKAGE),
        (transition["issuedLineage"], "technicalFreeze", FREEZE),
    ):
        _require(artifact[field]["digest"] == digest(path), f"RM-43 {field} digest mismatch")

    runtime = package["runtimeBoundDigests"]
    _require(isinstance(runtime, dict) and len(runtime) == 19, "RM-42 runtime blob count is not 19")
    for path_text, expected in runtime.items():
        _require(git_blob_digest(EXECUTION_COMMIT, str(path_text)) == expected, f"runtime Git blob mismatch: {path_text}")

    for key in ("runner", "reportSchema", "authorizationSchema"):
        binding = owner["reviewedLineage"][key]
        _require(binding["exactGitBlobDigest"] == runtime[binding["path"]], f"RM-43 exact binding mismatch: {key}")
        _require(git_blob_digest(EXECUTION_COMMIT, binding["path"]) == binding["exactGitBlobDigest"], f"RM-43 Git blob mismatch: {key}")

    rm42_result = rm42.run_preflight()
    _require(rm42_result["status"] == "F12_RM42_READY_ZERO_CALL", "RM-42 preflight did not pass")
    _require(rm42_result["providerCalls"] == 0 and rm42_result["retryCount"] == 0, "RM-42 preflight is not zero-call")
    _require(not REPORT_V8.exists() and not REPORT_V9.exists(), "v8/v9 report output must be absent")
    _require(digest(REPORT_V6) == V6_DIGEST, "immutable v6 report digest changed")

    closed = (
        "providerExecutionAuthorized",
        "newAuthorizationIssued",
        "rerunAuthorized",
        "retryAuthorized",
        "validationAccessAuthorized",
        "heldOutAccessAuthorized",
        "stageBAuthorized",
        "candidateSelectionAuthorized",
        "promotionAuthorized",
    )
    for state in (owner["decision"], transition["currentDecisionState"]):
        _require(state["preregistrationIssued"] is True and state["technicalFreezeIssued"] is True, "RM-43 issuance flags are not open")
        _require(all(state[key] is False for key in closed), "RM-43 downstream governance lock is open")
    return {
        "status": "F12_RM43_ISSUED_ZERO_CALL",
        "ownerReviewDigest": digest(OWNER),
        "transitionDigest": digest(TRANSITION),
        "executionCommitSha": EXECUTION_COMMIT,
        "runtimeBlobCount": len(runtime),
        "providerCalls": 0,
        "retryCount": 0,
        "reportV9Exists": False,
        "historicalV6ReportDigest": digest(REPORT_V6),
        "nextPermittedTask": transition["currentDecisionState"]["nextPermittedAction"],
    }


if __name__ == "__main__":
    print(json.dumps(run_preflight(), ensure_ascii=False, indent=2, sort_keys=True))
