#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""Validate the committed f10 technical freeze without authorizing execution."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from sprint12_pricing import file_digest

ROOT = Path(__file__).resolve().parents[1]
OPTIMIZATION = ROOT / "evaluation/sprint-12/optimization"
FREEZE = OPTIMIZATION / "s12-f-10-execution-package-freeze.v1.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _commit_is_ancestor(commit_sha: str) -> bool:
    try:
        subprocess.run(
            ("git", "merge-base", "--is-ancestor", commit_sha, "HEAD"),
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def build_preflight() -> dict[str, Any]:
    freeze = _load(FREEZE)
    package_path = ROOT / freeze["executionPackage"]
    prereg_path = ROOT / freeze["preregistrationDraft"]
    checks = {
        "freezeStatus": freeze.get("status") == "FROZEN_PENDING_AUTHORIZATION",
        "commitPresentInHead": _commit_is_ancestor(str(freeze.get("commitSha", ""))),
        "executionPackageDigest": freeze.get("executionPackageDigest")
        == file_digest(package_path),
        "preregistrationDraftDigest": freeze.get("preregistrationDraftDigest")
        == file_digest(prereg_path),
        "providerExecutionAuthorized": freeze.get("providerExecutionAuthorized") is False,
        "heldOutInspected": freeze.get("heldOutInspected") is False,
        "authorizationNotIssued": freeze.get("authorization", {}).get("status")
        == "NOT_ISSUED",
    }
    technical_freeze_valid = all(checks.values())
    return {
        "reportVersion": "s12.s12-f-10.freeze-preflight.v1",
        "status": (
            "TECHNICAL_FREEZE_VALID_PENDING_PREREGISTRATION_AUTHORIZATION"
            if technical_freeze_valid
            else "NO_GO_FREEZE_INTEGRITY_FAILURE"
        ),
        "checks": checks,
        "freezeRecord": FREEZE.name,
        "commitSha": freeze.get("commitSha"),
        "providerCallsPerformed": False,
        "providerExecutionAuthorized": False,
        "heldOutInspected": False,
    }


def main() -> None:
    print(json.dumps(build_preflight(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
