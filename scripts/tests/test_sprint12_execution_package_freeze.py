"""Offline integrity checks for the frozen-but-not-authorized f10 package."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from sprint12_pricing import file_digest

ROOT = Path(__file__).resolve().parents[2]
OPTIMIZATION = ROOT / "evaluation/sprint-12/optimization"
FREEZE = OPTIMIZATION / "s12-f-10-execution-package-freeze.v1.json"


def test_f10_freeze_binds_existing_commit_and_stays_unauthorized() -> None:
    record = json.loads(FREEZE.read_text(encoding="utf-8"))
    package_path = ROOT / record["executionPackage"]
    commit_sha = record["commitSha"]
    subprocess.run(
        ("git", "merge-base", "--is-ancestor", commit_sha, "HEAD"),
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    assert record["status"] == "FROZEN_PENDING_AUTHORIZATION"
    assert record["executionPackageDigest"] == file_digest(package_path)
    assert record["providerExecutionAuthorized"] is False
    assert record["authorization"]["status"] == "NOT_ISSUED"
    assert record["heldOutInspected"] is False
    assert record["selectionStatus"] == "NO_SELECTION"
