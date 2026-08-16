"""Governance contract for the S12-f-10 Approval-A issuance record."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPTIMIZATION = ROOT / "evaluation/sprint-12/optimization"


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_approval_a_issues_only_the_frozen_preregistration() -> None:
    approval = json.loads(
        (OPTIMIZATION / "s12-f-10-approval-a.v1.json").read_text(encoding="utf-8")
    )
    freeze = OPTIMIZATION / "s12-f-10-execution-package-freeze.v4.json"
    preregistration = (
        OPTIMIZATION
        / "s12-f-10-relation-evidence-shared-response-preregistration.v3.json"
    )
    package = OPTIMIZATION / "s12-f-10-execution-package.v4.json"

    assert approval["status"] == "APPROVED_FOR_ISSUANCE_ONLY"
    assert approval["commitSha"] == "3dffcf5"
    assert approval["freezeDigest"] == _digest(freeze)
    assert approval["preregistrationDigest"] == _digest(preregistration)
    assert approval["executionPackageDigest"] == _digest(package)
    assert approval["providerExecutionAuthorized"] is False
    assert approval["stageAAuthorized"] is False
    assert approval["stageBAuthorized"] is False
    assert approval["heldOutInspected"] is False
    assert approval["selectionStatus"] == "NO_SELECTION"
