#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""Zero-call preflight for the RM-22D v7 execution lineage."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import preflight_sprint12_f12_rm22d as delegated
import run_sprint12_f12_stage_a_v6 as runner

PACKAGE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22d-execution-package.v7.json"
PREREG = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22d-issuance-draft.v7.json"
FREEZE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22d-technical-freeze.v7.json"
OUTPUT = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json"
EXPECTED_SCOPE = "S12-RM-22D"
HISTORICAL_EXECUTION_COMMIT = "b63ebcb4603cd2cabeb796a38c86be4471304f3f"


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"artifact is not an object: {path}")
    return value


def _configure() -> None:
    runner.PACKAGE = PACKAGE
    runner.PREREG = PREREG
    runner.FREEZE = FREEZE
    runner.OUTPUT = OUTPUT
    delegated.v5 = runner
    delegated.PACKAGE = PACKAGE
    delegated.PREREG = PREREG
    delegated.FREEZE = FREEZE
    delegated.OUTPUT = OUTPUT


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
    commit = str(package.get("commitSha"))
    if not commit or commit == HISTORICAL_EXECUTION_COMMIT:
        raise ValueError("v7 must bind a new execution commit")
    if prereg.get("executionCommitSha") != commit or freeze.get("commitSha") != commit:
        raise ValueError("v7 execution commit is not identical across lineage")
    if freeze.get("executionPackageDigest") != _digest(PACKAGE):
        raise ValueError("v7 freeze package digest does not match package")
    if freeze.get("preregistrationDigest") != _digest(PREREG):
        raise ValueError("v7 freeze preregistration digest does not match preregistration")
    if package.get("executionRunner", {}).get("path") != "scripts/run_sprint12_f12_stage_a_v6.py":
        raise ValueError("v7 runner binding is not v6")
    if package.get("authorizationSchema", {}).get("path") != "evaluation/sprint-12/harness/s12-f-12-authorization.schema.v2.json":
        raise ValueError("v7 authorization schema binding is not v2")
    if package.get("outputPath") != "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json":
        raise ValueError("v7 output path is not report v6")
    bound = package.get("boundDigests")
    exact_paths = package.get("exactCommitBoundPaths")
    if not isinstance(bound, dict) or not isinstance(exact_paths, list):
        raise TypeError("v7 boundDigests or exactCommitBoundPaths is missing")
    for path_text, expected in bound.items():
        if path_text in exact_paths:
            continue
        path = ROOT / str(path_text)
        if not path.is_file() or _digest(path) != expected:
            raise ValueError(f"v7 bound digest mismatch: {path_text}")
    result = delegated.run_preflight()
    if OUTPUT.exists():
        raise ValueError("v7 report output already exists")
    result["status"] = "F12_RM22D_READY_ZERO_CALL_V7"
    result["preparationScope"] = EXPECTED_SCOPE
    result["executionCommitSha"] = commit
    return result


if __name__ == "__main__":
    print(json.dumps(run_preflight(), ensure_ascii=False, indent=2, sort_keys=True))
