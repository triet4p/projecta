"""Zero-call RM-42 preflight for the exact v9 superseding lineage.

Runtime custody is verified from Git blobs at the bound commit. Preparation
evidence is verified from the current working tree and is intentionally kept
outside the execution commit's runtime binding.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
OPT = ROOT / "evaluation/sprint-12/optimization"
PACKAGE = OPT / "s12-f-12-rm42-execution-package.v9.json"
PREREG = OPT / "s12-f-12-rm42-preregistration.v9.json"
FREEZE = OPT / "s12-f-12-rm42-technical-freeze.v9.json"
REPORT_V6 = OPT / "s12-f-12-stage-a-report.v6.json"
REPORT_V8 = OPT / "s12-f-12-stage-a-report.v8.json"
REPORT_V9 = OPT / "s12-f-12-stage-a-report.v9.json"


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


def _require_git_blob(commit: str, path_text: str, expected: str) -> None:
    try:
        actual = git_blob_digest(commit, path_text)
    except subprocess.CalledProcessError as error:
        raise ValueError(f"runtime blob absent at exact commit: {path_text}") from error
    if actual != expected:
        raise ValueError(f"runtime git-blob digest mismatch: {path_text}")


def _require_current(path_text: str, expected: str) -> None:
    path = ROOT / path_text
    if not path.is_file() or digest(path) != expected:
        raise ValueError(f"preparation evidence digest mismatch: {path_text}")


def _check_schema(path_text: str) -> None:
    Draft202012Validator.check_schema(load(ROOT / path_text))


def _require_closed_governance(artifact: dict[str, Any]) -> None:
    for key in (
        "preregistrationIssued",
        "technicalFreezeIssued",
        "providerExecutionAuthorized",
        "newAuthorizationIssued",
        "rerunAuthorized",
        "retryAuthorized",
        "validationAccessAuthorized",
        "heldOutAccessAuthorized",
        "stageBAuthorized",
        "candidateSelectionAuthorized",
        "promotionAuthorized",
    ):
        if artifact.get(key) is not False:
            raise ValueError(f"RM-42 governance lock is open: {key}")


def run_preflight() -> dict[str, object]:
    package = load(PACKAGE)
    prereg = load(PREREG)
    freeze = load(FREEZE)
    if package.get("artifactVersion") != "s12.s12-f-12.execution-package.v9":
        raise ValueError("RM-42 package version is not v9")
    if package.get("status") != "EXECUTION_PACKAGE_PREPARED_PENDING_RM43_OWNER_ISSUANCE_REVIEW":
        raise ValueError("RM-42 package is not pending RM-43 owner issuance review")
    commit = package.get("executionCommitSha")
    if not isinstance(commit, str) or len(commit) != 40:
        raise ValueError("RM-42 package must bind a full execution commit")
    if prereg.get("executionCommitSha") != commit or freeze.get("executionCommitSha") != commit:
        raise ValueError("package/preregistration/freeze commit mismatch")
    runtime = package.get("runtimeBoundDigests")
    preparation = package.get("preparationEvidence")
    if not isinstance(runtime, dict) or not runtime:
        raise ValueError("runtimeBoundDigests is empty")
    if not isinstance(preparation, dict) or not preparation:
        raise ValueError("preparationEvidence is empty")
    if set(runtime) & set(preparation):
        raise ValueError("runtime and preparation evidence paths overlap")
    if package.get("runtimeBinding", {}).get("digestMode") != "git_blob_sha256":
        raise ValueError("runtime binding is not git-blob custody")
    if package.get("runtimeBinding", {}).get("preparationEvidenceExcludedFromExecutionCommit") is not True:
        raise ValueError("preparation evidence is not excluded from execution commit")
    for path_text, expected in runtime.items():
        _require_git_blob(commit, str(path_text), str(expected))
    for path_text, expected in preparation.items():
        _require_current(str(path_text), str(expected))

    if freeze.get("executionPackageDigest") != digest(PACKAGE):
        raise ValueError("freeze package digest mismatch")
    if freeze.get("preregistrationDigest") != digest(PREREG):
        raise ValueError("freeze preregistration digest mismatch")
    for schema_path in (
        "evaluation/sprint-12/harness/s12-f-12-stage-a-report.schema.v9.json",
        "evaluation/sprint-12/harness/s12-f-12-authorization.schema.v9.json",
    ):
        _check_schema(schema_path)

    if digest(REPORT_V6) != (
        "sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233"
    ):
        raise ValueError("immutable Stage A v6 report changed")
    if REPORT_V8.exists() or REPORT_V9.exists():
        raise ValueError("RM-42 preparation refuses an existing v8 or v9 report")
    for artifact in (package, prereg, freeze):
        _require_closed_governance(artifact)
    governance = package.get("governance", {})
    for key in (
        "supersedingLineagePreparationAuthorized",
        "preregistrationPreparationAuthorized",
        "technicalFreezePreparationAuthorized",
        "executionPackagePreparationAuthorized",
    ):
        if governance.get(key) is not True:
            raise ValueError(f"RM-42 preparation flag is not open: {key}")
    if package.get("providerCallsPerformed") != 0 or package.get("retryCount") != 0:
        raise ValueError("RM-42 preparation accounting is not zero-call")
    if package.get("plannedProviderCalls") != 144 or package.get("relationBranchOutputs") != 96:
        raise ValueError("RM-42 prospective schedule is not 144/96")
    runner = ROOT / "scripts/run_sprint12_f12_stage_a_v9.py"
    source = runner.read_text(encoding="utf-8")
    if "rm40.diagnose_arm" not in source or "_arm_record_v9" not in source:
        raise ValueError("v9 runner is not bound to RM-40 behavior")
    return {
        "status": "F12_RM42_READY_ZERO_CALL",
        "preparationScope": "S12-RM-42",
        "lineageVersion": "v9",
        "executionCommitSha": commit,
        "runtimeBlobCount": len(runtime),
        "preparationEvidenceCount": len(preparation),
        "providerCalls": 0,
        "retryCount": 0,
        "plannedProviderCalls": 144,
        "plannedRelationBranchOutputs": 96,
        "historicalReportDigest": digest(REPORT_V6),
        "outputPath": REPORT_V9.relative_to(ROOT).as_posix(),
    }


if __name__ == "__main__":
    print(json.dumps(run_preflight(), ensure_ascii=False, indent=2, sort_keys=True))
