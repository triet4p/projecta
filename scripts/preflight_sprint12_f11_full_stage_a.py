#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pydantic>=2,<3",
# ]
# ///
"""Zero-call preflight for the prepared S12-f-11 full Stage A package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_sprint12_f11_full_stage_a import (
    FULL_FREEZE,
    FULL_PACKAGE,
    FULL_PREREGISTRATION,
    FULL_RUNTIME,
    FullStageAError,
    _digest,
    validate_full_package,
)


def run_preflight(
    *,
    package_path: Path = FULL_PACKAGE,
    freeze_path: Path = FULL_FREEZE,
    output_path: Path,
) -> dict[str, Any]:
    validate_full_package(package_path, output_path=output_path)
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if freeze.get("status") != "FROZEN_PENDING_FULL_STAGE_A_AUTHORIZATION":
        raise FullStageAError("freeze is not pending full Stage A authorization")
    if freeze.get("experimentId") != "s12-f-11":
        raise FullStageAError("freeze experiment is not f11")
    if freeze.get("commitSha") in (None, ""):
        raise FullStageAError("freeze commit is not exact")
    if freeze.get("executionPackageDigest") != _digest(package_path):
        raise FullStageAError("freeze package digest mismatch")
    if freeze.get("preregistrationDigest") != _digest(FULL_PREREGISTRATION):
        raise FullStageAError("freeze preregistration digest mismatch")
    if freeze.get("runtimeConfigurationDigest") != _digest(FULL_RUNTIME):
        raise FullStageAError("freeze runtime digest mismatch")
    if freeze.get("providerExecutionAuthorized") is not False:
        raise FullStageAError("freeze authorizes provider execution")
    if freeze.get("heldOutInspected") is not False:
        raise FullStageAError("freeze permits held-out access")
    if freeze.get("stageBAuthorized") is not False:
        raise FullStageAError("freeze opens Stage B")
    if freeze.get("authorization", {}).get("status") != "NOT_ISSUED":
        raise FullStageAError("full Stage A authorization is already issued")
    return {
        "status": "PREAUTHORIZATION_READY_FULL_STAGE_A",
        "experimentId": "s12-f-11",
        "packagePath": package_path.relative_to(ROOT).as_posix(),
        "freezePath": freeze_path.relative_to(ROOT).as_posix(),
        "packageDigest": _digest(package_path),
        "freezeDigest": _digest(freeze_path),
        "commitSha": freeze["commitSha"],
        "providerExecutionAuthorized": False,
        "providerCalls": 48,
        "branchOutputs": 96,
        "zeroProviderCallsPerformed": True,
        "outputPathAbsent": not output_path.exists(),
        "heldOutInspected": False,
        "stageBAuthorized": False,
        "candidateSelectionAuthorized": False,
        "promotionAuthorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="S12-f-11 full Stage A zero-call preflight"
    )
    parser.add_argument("--package", default=FULL_PACKAGE, type=Path)
    parser.add_argument("--freeze", default=FULL_FREEZE, type=Path)
    parser.add_argument(
        "--output",
        default=ROOT
        / "evaluation/sprint-12/optimization/s12-f-11-full-stage-a-report.v1.json",
        type=Path,
    )
    args = parser.parse_args(argv)
    print(
        json.dumps(
            run_preflight(
                package_path=args.package,
                freeze_path=args.freeze,
                output_path=args.output,
            ),
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
