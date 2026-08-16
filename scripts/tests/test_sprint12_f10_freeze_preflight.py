"""Tests for the post-commit, pre-authorization f10 freeze preflight."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from preflight_sprint12_f10_freeze import build_preflight


def test_f10_technical_freeze_is_valid_but_authorization_remains_blocked() -> None:
    report = build_preflight()
    assert report["status"] == (
        "TECHNICAL_FREEZE_VALID_PENDING_PREREGISTRATION_AUTHORIZATION"
    )
    assert all(report["checks"].values())
    assert report["commitSha"] == "620df83"
    assert report["providerCallsPerformed"] is False
    assert report["providerExecutionAuthorized"] is False
    assert report["heldOutInspected"] is False
