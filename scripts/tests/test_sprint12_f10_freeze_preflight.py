"""Tests for the post-commit, pre-authorization f10 freeze preflight."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from preflight_sprint12_f10_freeze import build_preflight


def test_historical_f10_freeze_cannot_pass_with_an_incomplete_package() -> None:
    report = build_preflight()
    assert report["status"] == (
        "NO_GO_INCOMPLETE_EXECUTION_PACKAGE_OR_FREEZE_INTEGRITY_FAILURE"
    )
    assert report["checks"]["packageStatusComplete"] is False
    assert report["checks"]["packageRunnerImplemented"] is False
    assert report["commitSha"] == "620df83"
    assert report["providerCallsPerformed"] is False
    assert report["providerExecutionAuthorized"] is False
    assert report["heldOutInspected"] is False
