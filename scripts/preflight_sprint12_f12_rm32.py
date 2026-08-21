"""Zero-call RM-32 preflight with exact git-blob custody.

The execution commit contains runtime blobs only. Preparation evidence is
validated from the working tree and is excluded from exact execution binding.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm32-execution-package.v8.json"
PREREG = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm32-preregistration.v8.json"
FREEZE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm32-technical-freeze.v8.json"
REPORT_V6 = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json"
OUTPUT = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v8.json"


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"artifact must be an object: {path}")
    return value


def git_blob_digest(commit: str, path_text: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path_text}"], cwd=ROOT, capture_output=True, check=True
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
    from jsonschema import Draft202012Validator

    Draft202012Validator.check_schema(load(ROOT / path_text))


def run_preflight() -> dict[str, object]:
    package = load(PACKAGE)
    prereg = load(PREREG)
    freeze = load(FREEZE)
    if package.get("artifactVersion") != "s12.s12-f-12.execution-package.v8":
        raise ValueError("RM-32 package version is not v8")
    if package.get("status") != "EXECUTION_PACKAGE_PREPARED_PENDING_RM33_OWNER_ISSUANCE_REVIEW":
        raise ValueError("RM-32 package is not pending RM-33 owner review")
    commit = package.get("executionCommitSha")
    if not isinstance(commit, str) or len(commit) != 40:
        raise ValueError("RM-32 package must bind a full execution commit")
    if prereg.get("executionCommitSha") != commit or freeze.get("executionCommitSha") != commit:
        raise ValueError("package/preregistration/freeze commit mismatch")
    runtime = package.get("runtimeBoundDigests")
    preparation = package.get("preparationEvidence")
    if not isinstance(runtime, dict) or not runtime:
        raise ValueError("runtimeBoundDigests is empty")
    if not isinstance(preparation, dict) or not preparation:
        raise ValueError("preparationEvidence is empty")
    overlap = set(runtime) & set(preparation)
    if overlap:
        raise ValueError(f"runtime/preparation path overlap: {sorted(overlap)}")
    for path_text, expected in runtime.items():
        _require_git_blob(commit, str(path_text), str(expected))
    for path_text, expected in preparation.items():
        _require_current(str(path_text), str(expected))
    if freeze.get("executionPackageDigest") != digest(PACKAGE):
        raise ValueError("freeze package digest mismatch")
    if freeze.get("preregistrationDigest") != digest(PREREG):
        raise ValueError("freeze preregistration digest mismatch")
    for schema_path in (
        "evaluation/sprint-12/harness/s12-f-12-stage-a-report.schema.v8.json",
        "evaluation/sprint-12/harness/s12-f-12-authorization.schema.v8.json",
    ):
        _check_schema(schema_path)
    if digest(REPORT_V6) != "sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233":
        raise ValueError("immutable Stage A v6 report changed")
    if OUTPUT.exists():
        raise ValueError("RM-32 refuses to overwrite an existing v8 report")
    governance = package.get("governance", {})
    for key in (
        "preregistrationIssued", "technicalFreezeIssued", "providerExecutionAuthorized",
        "newAuthorizationIssued", "validationAccessAuthorized", "heldOutAccessAuthorized",
        "stageBAuthorized", "candidateSelectionAuthorized", "promotionAuthorized",
    ):
        if governance.get(key) is not False:
            raise ValueError(f"RM-32 governance lock is open: {key}")
    if package.get("providerCallsPerformed") != 0 or package.get("retryCount") != 0:
        raise ValueError("RM-32 preparation accounting is not zero-call")
    return {
        "status": "F12_RM32_READY_ZERO_CALL",
        "preparationScope": "S12-RM-32",
        "lineageVersion": "v8",
        "executionCommitSha": commit,
        "runtimeBlobCount": len(runtime),
        "preparationEvidenceCount": len(preparation),
        "providerCalls": 0,
        "retryCount": 0,
        "historicalReportDigest": digest(REPORT_V6),
        "outputPath": OUTPUT.relative_to(ROOT).as_posix(),
    }


if __name__ == "__main__":
    print(json.dumps(run_preflight(), ensure_ascii=False, indent=2, sort_keys=True))
