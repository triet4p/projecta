"""Zero-call preflight for the RM-32 superseding f12 lineage preparation.

This preflight validates only repository-local artifacts and digest bindings.
It intentionally does not import the provider adapter or invoke the guarded
runner.  RM-33 must review and issue the prepared lineage before either can be
used for execution.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm32-execution-package.v8.json"
PREREG = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm32-preregistration.v8.json"
FREEZE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm32-technical-freeze.v8.json"
OUTPUT = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v8.json"
REPORT_V6 = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json"
RM31_OWNER = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm31-owner-review.v1.json"
RM31_TRANSITION = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm31-approval-transition.v1.json"


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"artifact must be an object: {path}")
    return value


def _require_digest(path: Path, expected: str, label: str) -> None:
    if not path.is_file() or digest(path) != expected:
        raise ValueError(f"{label} digest mismatch: {path}")


def run_preflight() -> dict[str, object]:
    package = load(PACKAGE)
    prereg = load(PREREG)
    freeze = load(FREEZE)
    for label, artifact in (("package", package), ("preregistration", prereg), ("freeze", freeze)):
        if artifact.get("experimentId") != "s12-f-12":
            raise ValueError(f"{label} experimentId is not exact")
        if artifact.get("preparationScope") != "S12-RM-32":
            raise ValueError(f"{label} preparationScope is not RM-32")
        if artifact.get("lineageVersion") != "v8":
            raise ValueError(f"{label} lineageVersion is not v8")

    if package.get("executionCommitSha") != "1a3ffed08a8a96c6ea76f2ae2bf2f868254475a5":
        raise ValueError("RM-32 execution commit is not the reviewed exact base commit")
    if prereg.get("executionCommitSha") != package.get("executionCommitSha"):
        raise ValueError("preregistration execution commit does not match package")
    if freeze.get("executionCommitSha") != package.get("executionCommitSha"):
        raise ValueError("freeze execution commit does not match package")
    if freeze.get("executionPackageDigest") != digest(PACKAGE):
        raise ValueError("freeze package digest does not match package")
    if freeze.get("preregistrationDigest") != digest(PREREG):
        raise ValueError("freeze preregistration digest does not match preregistration")

    owner = load(RM31_OWNER)
    transition = load(RM31_TRANSITION)
    if transition.get("ownerReview", {}).get("digest") != digest(RM31_OWNER):
        raise ValueError("RM-31 transition does not bind owner review")
    if owner.get("status") != "OWNER_REVIEW_APPROVED_SUPERSEDING_LINEAGE_PREPARATION_ONLY":
        raise ValueError("RM-31 owner review is not the approved preparation decision")
    if transition.get("status") != "SUPERSEDING_LINEAGE_PREPARATION_APPROVED_OFFLINE_ONLY":
        raise ValueError("RM-31 transition is not the approved preparation transition")

    for path_text, expected in package["boundDigests"].items():
        _require_digest(ROOT / str(path_text), str(expected), str(path_text))
    _require_digest(REPORT_V6, "sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233", "immutable report v6")
    if OUTPUT.exists():
        raise ValueError("RM-32 refuses to overwrite an existing v8 report output")

    governance = package["governance"]
    for key in (
        "preregistrationIssued",
        "technicalFreezeIssued",
        "providerExecutionAuthorized",
        "newAuthorizationIssued",
        "validationAccessAuthorized",
        "heldOutAccessAuthorized",
        "stageBAuthorized",
        "candidateSelectionAuthorized",
        "promotionAuthorized",
    ):
        if governance.get(key) is not False:
            raise ValueError(f"RM-32 governance lock is open: {key}")
    if governance.get("supersedingLineagePreparationAuthorized") is not True:
        raise ValueError("RM-32 preparation authorization is not true")

    return {
        "status": "F12_RM32_READY_ZERO_CALL",
        "preparationScope": "S12-RM-32",
        "lineageVersion": "v8",
        "providerCalls": 0,
        "retryCount": 0,
        "historicalReportDigest": digest(REPORT_V6),
        "outputPath": OUTPUT.relative_to(ROOT).as_posix(),
    }


if __name__ == "__main__":
    print(json.dumps(run_preflight(), ensure_ascii=False, indent=2, sort_keys=True))
