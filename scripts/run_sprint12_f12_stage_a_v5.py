# /// script
# requires-python = ">=3.12"
# dependencies = ["jsonschema>=4.23,<5"]
# ///
"""RM-22D runner wrapper with preregistration-bound report and auth schemas."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_sprint12_f12_stage_a_v4 as v4

v3 = v4.v3

PACKAGE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22d-execution-package.v5.json"
PREREG = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22d-issuance-draft.v5.json"
FREEZE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22d-technical-freeze.v5.json"
REPORT_SCHEMA = ROOT / "evaluation/sprint-12/harness/s12-f-12-stage-a-report.schema.v5.json"
AUTHORIZATION_SCHEMA = ROOT / "evaluation/sprint-12/harness/s12-f-12-authorization.schema.v1.json"
OUTPUT = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v5.json"

digest = v4.digest


def _validate_report_schema(report: dict[str, Any]) -> None:
    report["artifactVersion"] = "s12-f-12.stage-a-report.v5"
    try:
        from jsonschema import Draft202012Validator
    except ImportError as error:
        raise v4.v3.F12StageAV3Error(
            "jsonschema is required; refusing permissive fallback validation"
        ) from error
    schema = v4.v3.load(REPORT_SCHEMA)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(report),
        key=lambda item: list(item.path),
    )
    if errors:
        location = ".".join(str(item) for item in errors[0].path) or "<root>"
        raise v4.v3.F12StageAV3Error(
            f"report v5 JSON Schema validation failed at {location}: {errors[0].message}"
        )


def validate_authorization(
    authorization_path: Path,
    *,
    package_path: Path = PACKAGE,
    freeze_path: Path = FREEZE,
    output_path: Path = OUTPUT,
) -> dict[str, Any]:
    authorization = v4.v3.load(authorization_path)
    try:
        from jsonschema import Draft202012Validator
    except ImportError as error:
        raise v4.v3.F12StageAV3Error(
            "jsonschema is required; refusing authorization without schema validation"
        ) from error
    schema = v4.v3.load(AUTHORIZATION_SCHEMA)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(authorization),
        key=lambda item: list(item.path),
    )
    if errors:
        location = ".".join(str(item) for item in errors[0].path) or "<root>"
        raise v4.v3.F12StageAV3Error(
            f"authorization schema validation failed at {location}: {errors[0].message}"
        )
    if authorization.get("experimentId") != "s12-f-12":
        raise v4.v3.F12StageAV3Error("authorization experimentId is not s12-f-12")
    return v4._ORIGINAL_VALIDATE_AUTHORIZATION(
        authorization_path,
        package_path=package_path,
        freeze_path=freeze_path,
        output_path=output_path,
    )


def _configure() -> None:
    v4.PACKAGE = PACKAGE
    v4.PREREG = PREREG
    v4.FREEZE = FREEZE
    v4.REPORT_SCHEMA = REPORT_SCHEMA
    v4.OUTPUT = OUTPUT
    v4._validate_report_schema = _validate_report_schema
    v4.validate_authorization = validate_authorization


def run_stage_a(**kwargs: Any) -> dict[str, Any]:
    names = ("PACKAGE", "PREREG", "FREEZE", "REPORT_SCHEMA", "OUTPUT", "_validate_report_schema", "validate_authorization")
    old = {name: getattr(v4, name) for name in names}
    _configure()
    kwargs.setdefault("package_path", PACKAGE)
    kwargs.setdefault("output_path", OUTPUT)
    try:
        return v4.run_stage_a(**kwargs)
    finally:
        for name, value in old.items():
            setattr(v4, name, value)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Guarded S12-f-12 Stage A runner v5")
    parser.add_argument("--authorization", required=True, type=Path)
    parser.add_argument("--output", default=OUTPUT, type=Path)
    args = parser.parse_args(argv)
    from sprint12_f12_provider_adapter_v2 import F12ProviderAdapterV2

    run_stage_a(
        provider_adapter=F12ProviderAdapterV2.from_environment(),
        authorization_path=args.authorization.resolve(),
        output_path=args.output.resolve(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
