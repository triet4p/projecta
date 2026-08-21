#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""Guarded S12-f-12 Stage A entrypoint prepared by RM-22.

This module validates the complete offline lineage before any adapter is
created. Missing or invalid authorization fails before the first capture.
The actual development run remains separately authorized by RM-23+.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22-execution-package.v1.json"
PREREGISTRATION = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22-prereg-draft.v1.json"
FREEZE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22-technical-freeze.v1.json"
OUTPUT = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v1.json"


class F12StageAError(RuntimeError):
    """Raised when the prepared f12 execution boundary is not safe."""


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise F12StageAError(f"cannot load artifact: {path}") from error
    if not isinstance(value, dict):
        raise F12StageAError(f"artifact is not an object: {path}")
    return value


def validate_preparation(
    package_path: Path = PACKAGE,
    *,
    preregistration_path: Path = PREREGISTRATION,
    freeze_path: Path = FREEZE,
    output_path: Path | None = None,
) -> dict[str, Any]:
    package = load(package_path)
    preregistration = load(preregistration_path)
    freeze = load(freeze_path)
    if package.get("status") != "EXECUTION_PACKAGE_PREPARED_PENDING_RM23_OWNER_REVIEW":
        raise F12StageAError("package is not pending RM-23 review")
    exact_false = ("providerExecutionAuthorized", "heldOutInspected", "stageBAuthorized", "candidateSelectionAuthorized", "promotionAuthorized")
    if any(package.get(key) is not False for key in exact_false):
        raise F12StageAError("package governance is not closed")
    if package.get("experimentId") != "s12-f-12":
        raise F12StageAError("package experiment mismatch")
    if package.get("providerCalls") != 144 or package.get("stage1ProviderCalls") != 48 or package.get("stage2ProviderCalls") != 96:
        raise F12StageAError("provider-call schedule is not the three-call two-step schedule")
    if package.get("retryPolicy") != "none" or package.get("outputOverwrite") is not False:
        raise F12StageAError("retry or overwrite policy is not fail closed")
    if package.get("preregistration", {}).get("path") != relative(preregistration_path) or package.get("preregistration", {}).get("digest") != digest(preregistration_path):
        raise F12StageAError("preregistration binding mismatch")
    if package.get("freezeRecord") != relative(freeze_path):
        raise F12StageAError("freeze path binding mismatch")
    if freeze.get("executionPackageDigest") != digest(package_path) or freeze.get("preregistrationDigest") != digest(preregistration_path):
        raise F12StageAError("freeze lineage digest mismatch")
    if freeze.get("providerExecutionAuthorized") is not False or freeze.get("commitSha") is not None:
        raise F12StageAError("freeze must remain unissued and commit-pending")
    if preregistration.get("preregistrationIssued") is not False or preregistration.get("providerExecutionAuthorized") is not False:
        raise F12StageAError("preregistration is not issuance-only")
    bindings = package.get("boundDigests")
    if not isinstance(bindings, dict) or not bindings:
        raise F12StageAError("package has no bound digests")
    for path_text, expected in bindings.items():
        path = ROOT / str(path_text)
        if not path.is_file() or digest(path) != expected:
            raise F12StageAError(f"bound digest mismatch: {path_text}")
    if output_path is not None and output_path.exists():
        raise F12StageAError("refusing to overwrite final report")
    return package


def run_stage_a(
    *,
    provider_adapter: Any,
    authorization_path: Path | None,
    output_path: Path = OUTPUT,
    package_path: Path = PACKAGE,
) -> dict[str, Any]:
    """Validate custody, then require a future exact authorization.

    The authorization check intentionally precedes all adapter operations.
    This ordering is the zero-call safety property tested by RM-22.
    """

    validate_preparation(package_path, output_path=output_path)
    if authorization_path is None:
        raise F12StageAError("separate f12 Stage A authorization is required before provider capture")
    authorization = load(authorization_path)
    if authorization.get("status") != "APPROVED_FOR_DEVELOPMENT_STAGE_A" or authorization.get("providerExecutionAuthorized") is not True:
        raise F12StageAError("authorization is not an exact live Stage A authorization")
    if authorization.get("experimentId") != "s12-f-12" or authorization.get("providerCalls") != 144:
        raise F12StageAError("authorization call schedule mismatch")
    if authorization.get("executionPackage", {}).get("digest") != digest(package_path):
        raise F12StageAError("authorization package digest mismatch")
    if authorization.get("freezeRecord", {}).get("digest") != digest(FREEZE):
        raise F12StageAError("authorization freeze digest mismatch")
    if output_path.exists():
        raise F12StageAError("refusing to overwrite final report")
    if not hasattr(provider_adapter, "capture_stage"):
        raise F12StageAError("f12 concrete provider adapter is required")
    raise F12StageAError("live case execution is intentionally not enabled by RM-22 preparation")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Guarded S12-f-12 Stage A runner")
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--output", default=OUTPUT, type=Path)
    parser.add_argument("--package", default=PACKAGE, type=Path)
    args = parser.parse_args(argv)
    validate_preparation(args.package.resolve(), output_path=args.output.resolve())
    if args.authorization is None:
        raise SystemExit("NO-GO: separate Stage A authorization is required; provider calls=0")
    raise SystemExit("NO-GO: RM-22 preparation does not execute provider calls")


if __name__ == "__main__":
    raise SystemExit(main())
