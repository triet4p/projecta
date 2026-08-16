"""Offline preflight tests for the next-tool execution-package draft."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from preflight_sprint12_remediation import build_preflight


def test_draft_preflight_stays_fail_closed_without_runner_or_commit() -> None:
    report = build_preflight()

    assert report["status"] == "NO_GO_PENDING_EXECUTION_PACKAGE_COMMIT_AND_RUNNER"
    assert report["providerCallsPerformed"] is False
    assert report["providerExecutionAuthorized"] is False
    assert report["checks"]["allBoundDigestsMatch"] is True
    assert report["checks"]["executionRunnerImplemented"] is False
    assert report["checks"]["commitBound"] is False
    assert report["checks"]["authorizationIssued"] is False
    assert report["checks"]["heldOutInspected"] is False
    assert report["checks"]["caseSelectionBound"] is True
    assert report["checks"]["preregistrationDraftBound"] is True
