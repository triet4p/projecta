#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""Zero-call preflight for the RM-22D v6 lineage.

This wrapper keeps the b63ebcb execution custody intact while adding the
lineage assertion that the v5 preflight lacked.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import preflight_sprint12_f12_rm22d as v5_preflight
import run_sprint12_f12_stage_a_v5 as runner

PACKAGE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22d-execution-package.v6.json"
PREREG = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22d-issuance-draft.v6.json"
FREEZE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22d-technical-freeze.v6.json"
OUTPUT = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json"
EXPECTED_SCOPE = "S12-RM-22D"


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise TypeError(f"artifact is not an object: {path}")
    return value


def _configure() -> None:
    runner.PACKAGE = PACKAGE
    runner.PREREG = PREREG
    runner.FREEZE = FREEZE
    runner.OUTPUT = OUTPUT
    v5_preflight.v5 = runner
    v5_preflight.PACKAGE = PACKAGE
    v5_preflight.PREREG = PREREG
    v5_preflight.FREEZE = FREEZE
    v5_preflight.OUTPUT = OUTPUT


def run_preflight() -> dict[str, object]:
    _configure()
    package = _load(PACKAGE)
    prereg = _load(PREREG)
    freeze = _load(FREEZE)
    for name, artifact in (("package", package), ("preregistration", prereg), ("freeze", freeze)):
        if artifact.get("preparationScope") != EXPECTED_SCOPE:
            raise ValueError(f"{name} preparationScope is not exact RM-22D lineage")
        if artifact.get("experimentId") != "s12-f-12":
            raise ValueError(f"{name} experimentId is not exact")
    if prereg.get("executionCommitSha") != "b63ebcb4603cd2cabeb796a38c86be4471304f3f":
        raise ValueError("execution commit custody changed from b63ebcb")
    if package.get("commitSha") != prereg.get("executionCommitSha"):
        raise ValueError("package and preregistration execution commits differ")
    if freeze.get("commitSha") != package.get("commitSha"):
        raise ValueError("freeze and package execution commits differ")
    if freeze.get("executionPackageDigest") != _digest(PACKAGE):
        raise ValueError("freeze package digest does not match v6 package")
    if freeze.get("preregistrationDigest") != _digest(PREREG):
        raise ValueError("freeze preregistration digest does not match v6 preregistration")
    bound = package.get("boundDigests")
    exact_paths = package.get("exactCommitBoundPaths")
    if not isinstance(bound, dict) or not isinstance(exact_paths, list):
        raise TypeError("v6 boundDigests is missing")
    for path_text, expected in bound.items():
        # The historical execution paths are verified against the exact b63
        # commit by the delegated v5 preflight.  The v6 wrapper itself is a
        # lineage-only control and is verified from the current committed blob.
        if path_text in exact_paths:
            continue
        path = ROOT / str(path_text)
        if not path.is_file() or _digest(path) != expected:
            raise ValueError(f"v6 bound digest mismatch: {path_text}")
    result = v5_preflight.run_preflight()
    if OUTPUT.exists():
        raise ValueError("RM-22D v6 output already exists")
    result["status"] = "F12_RM22D_READY_ZERO_CALL_V6"
    result["preparationScope"] = EXPECTED_SCOPE
    return result


if __name__ == "__main__":
    print(json.dumps(run_preflight(), ensure_ascii=False, indent=2, sort_keys=True))
