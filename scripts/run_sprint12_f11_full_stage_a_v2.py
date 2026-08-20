#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pydantic>=2,<3",
# ]
# ///
"""Superseding full S12-f-11 runner with one final-report write."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_sprint12_f11_full_stage_a as v1
import run_sprint12_next_tool_experiment as legacy
from sprint12_pricing import merged_environment
from sprint12_provider_adapter import (
    DeepSeekProviderAdapter,
    DeepSeekRuntimeConfiguration,
    ProviderAdapter,
)

FULL_PACKAGE = (
    ROOT
    / "evaluation/sprint-12/optimization/s12-f-11-full-stage-a-execution-package.v3.json"
)
FULL_FREEZE = (
    ROOT / "evaluation/sprint-12/optimization/s12-f-11-full-stage-a-freeze.v3.json"
)
FULL_PREREGISTRATION = (
    ROOT
    / "evaluation/sprint-12/optimization/s12-f-11-full-stage-a-preregistration.v2.json"
)
FULL_RUNTIME = (
    ROOT
    / "evaluation/sprint-12/harness/s12-f-11-full-stage-a-runtime-configuration.v1.json"
)
AUTHORIZATION_CONTRACT = (
    ROOT
    / "evaluation/sprint-12/harness/s12-f-11-full-stage-a-authorization.schema.v1.json"
)
PROMPT = (
    ROOT
    / "evaluation/sprint-12/optimization/s12-f-11-m3-prompt-v7-relation-trigger-envelope-examples.v2.txt"
)
SCHEMA = ROOT / "evaluation/sprint-12/harness/relation-evidence-envelope.schema.v2.json"
OUTPUT = ROOT / "evaluation/sprint-12/optimization/s12-f-11-full-stage-a-report.v3.json"
EXPECTED_PROMPT = "m3.prompt.v7.relation-trigger-envelope-examples"
EXPECTED_SCHEMA = "relation-evidence-envelope.v1"


class FullStageAV2Error(RuntimeError):
    """Raised when the superseding full Stage A contract is unsafe."""


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FullStageAV2Error(f"artifact is not an object: {path.name}")
    return value


def _digest(path: Path) -> str:
    return legacy._bound_file_digest(path)


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def validate_full_package(
    package_path: Path = FULL_PACKAGE, *, output_path: Path | None = None
) -> dict[str, Any]:
    package = _load(package_path)
    expected = {
        "status": "EXECUTION_PACKAGE_FROZEN_PENDING_AUTHORIZATION",
        "experimentId": "s12-f-11",
        "providerExecutionAuthorized": False,
        "heldOutInspected": False,
        "stageBAuthorized": False,
        "candidateSelectionAuthorized": False,
        "promotionAuthorized": False,
        "executionRunnerImplemented": True,
        "caseCount": 16,
        "providerCalls": 48,
        "branchOutputs": 96,
        "requiredSchemaValidResponses": 48,
        "expectedUsageValidResponses": 48,
        "expectedPricedCalls": 48,
        "retryPolicy": "none",
        "authorizationContract": _relative(AUTHORIZATION_CONTRACT),
    }
    if any(package.get(key) != value for key, value in expected.items()):
        raise FullStageAV2Error(
            "package field does not match the canonical full Stage A contract"
        )
    runner = package.get("executionRunner")
    if (
        not isinstance(runner, dict)
        or runner.get("path") != _relative(Path(__file__))
        or runner.get("digest") != _digest(Path(__file__))
    ):
        raise FullStageAV2Error("v2 runner binding mismatch")
    runtime = package.get("runtimeConfiguration")
    if (
        not isinstance(runtime, dict)
        or runtime.get("path") != _relative(FULL_RUNTIME)
        or runtime.get("digest") != _digest(FULL_RUNTIME)
    ):
        raise FullStageAV2Error("runtime binding mismatch")
    adapter = package.get("providerAdapter")
    if (
        not isinstance(adapter, dict)
        or adapter.get("path") != "scripts/sprint12_provider_adapter.py"
        or adapter.get("digest") != _digest(ROOT / adapter["path"])
    ):
        raise FullStageAV2Error("adapter binding mismatch")
    arms = package.get("arms")
    if package.get("providerResponseSchema") != EXPECTED_SCHEMA or not isinstance(
        arms, dict
    ):
        raise FullStageAV2Error("shared provider schema binding is missing")
    if any(
        not isinstance(arm, dict)
        or arm.get("providerSchema") != EXPECTED_SCHEMA
        or arm.get("branchOutputSchema") != "m3.v2"
        for arm in arms.values()
    ):
        raise FullStageAV2Error("control/candidate schemas are not identical")
    bound = package.get("boundDigests")
    if not isinstance(bound, dict) or not bound:
        raise FullStageAV2Error("bound digests are missing")
    for relative_path, expected_digest in bound.items():
        path = ROOT / relative_path
        if not path.is_file() or _digest(path) != expected_digest:
            raise FullStageAV2Error(f"bound digest mismatch: {relative_path}")
    if output_path is not None and output_path.exists():
        raise FullStageAV2Error("refusing to overwrite final report")
    return package


def _configure_legacy() -> None:
    v1.FULL_PACKAGE = FULL_PACKAGE
    v1.FULL_FREEZE = FULL_FREEZE
    v1.FULL_PREREGISTRATION = FULL_PREREGISTRATION
    v1.FULL_RUNTIME = FULL_RUNTIME
    v1.AUTHORIZATION_CONTRACT = AUTHORIZATION_CONTRACT
    v1._configure_legacy_runner()


def validate_authorization(
    package: Mapping[str, Any],
    *,
    authorization_path: Path | None,
    package_path: Path,
    output_path: Path,
    adapter_digest: str,
    runtime_digest: str,
) -> dict[str, Any]:
    if authorization_path is None:
        raise FullStageAV2Error(
            "full Stage A authorization is required before provider capture"
        )
    authorization = _load(authorization_path)
    exact = {
        "status": "APPROVED_FOR_DEVELOPMENT_STAGE_A",
        "experimentId": "s12-f-11",
        "providerExecutionAuthorized": True,
        "providerCalls": 48,
        "branchOutputs": 96,
        "requiredSchemaValidResponses": 48,
        "requiredUsageValidResponses": 48,
        "expectedPricedCalls": 48,
        "retryPolicy": "none",
        "heldOutInspected": False,
        "stageBAuthorized": False,
        "candidateSelectionAuthorized": False,
        "promotionAuthorized": False,
    }
    for key, expected in exact.items():
        if authorization.get(key) != expected:
            raise FullStageAV2Error(f"authorization field is not exact: {key}")
    if authorization.get("executionPackage", {}).get("digest") != _digest(package_path):
        raise FullStageAV2Error("authorization package digest mismatch")
    freeze = _load(FULL_FREEZE)
    if authorization.get("freezeRecord", {}).get("path") != _relative(
        FULL_FREEZE
    ) or authorization.get("freezeRecord", {}).get("digest") != _digest(FULL_FREEZE):
        raise FullStageAV2Error("authorization freeze binding mismatch")
    if authorization.get("commitSha") != freeze.get("commitSha") or not freeze.get(
        "commitSha"
    ):
        raise FullStageAV2Error("authorization commit is not the exact freeze commit")
    if not legacy.commit_is_ancestor(str(freeze["commitSha"])):
        raise FullStageAV2Error("authorization commit is not an ancestor")
    if authorization.get("providerAdapter", {}).get("digest") != adapter_digest:
        raise FullStageAV2Error("authorization adapter digest mismatch")
    if authorization.get("runtimeConfiguration", {}).get("digest") != runtime_digest:
        raise FullStageAV2Error("authorization runtime digest mismatch")
    if authorization.get("outputPath") != _relative(output_path):
        raise FullStageAV2Error("authorization output path mismatch")
    if Decimal(str(authorization.get("costCeilingUsd"))) != Decimal("10.00"):
        raise FullStageAV2Error("authorization cost ceiling must equal $10.00")
    return authorization


def build_adapter(
    environment: Mapping[str, str] | None = None, *, transport: Any = None
) -> DeepSeekProviderAdapter:
    configuration = DeepSeekRuntimeConfiguration.from_environment(
        environment, prompt_path=PROMPT, schema_path=SCHEMA
    )
    configuration = replace(
        configuration,
        prompt_version=EXPECTED_PROMPT,
        prompt_path=_relative(PROMPT),
        schema_path=_relative(SCHEMA),
        expected_provider_calls=48,
    )
    return DeepSeekProviderAdapter(
        configuration, transport=transport, prompt_path=PROMPT, schema_path=SCHEMA
    )


def run_full_stage_a(
    *,
    provider_adapter: ProviderAdapter,
    authorization_path: Path | None,
    output_path: Path = OUTPUT,
    package_path: Path = FULL_PACKAGE,
) -> dict[str, Any]:
    _configure_legacy()
    package = validate_full_package(package_path, output_path=output_path)
    if not isinstance(provider_adapter, DeepSeekProviderAdapter):
        raise FullStageAV2Error("full Stage A requires DeepSeekProviderAdapter")
    validate_authorization(
        package,
        authorization_path=authorization_path,
        package_path=package_path,
        output_path=output_path,
        adapter_digest=provider_adapter.adapter_digest,
        runtime_digest=provider_adapter.runtime_configuration_digest,
    )
    if output_path.exists():
        raise FullStageAV2Error("refusing to overwrite final report")
    with tempfile.TemporaryDirectory(
        prefix="s12-f-11-stage-a-", dir=output_path.parent
    ) as staging_directory:
        staging_path = Path(staging_directory) / "report.staging.json"
        legacy.validate_final_execution_package = (
            lambda package_path, output_path=None: package
        )
        legacy.validate_stage_a_authorization = lambda *args, **kwargs: {
            "costCeilingUsd": "10.00"
        }
        result = legacy.run_offline_stage_a(
            provider_adapter=provider_adapter,
            package_path=package_path,
            authorization_path=authorization_path,
            output_path=staging_path,
            require_concrete_provider_binding=False,
        )
        staged = _load(staging_path)
        staged.update(
            {
                "artifactVersion": "s12.s12-f-11.full-stage-a-report.v3",
                "experimentId": "s12-f-11",
                "executionPackagePath": _relative(package_path),
                "freezePath": _relative(FULL_FREEZE),
                "authorizationPath": _relative(authorization_path)
                if authorization_path
                else None,
            }
        )
        if (
            result.get("providerCallCount") != 48
            or result.get("branchOutputCount") != 96
        ):
            raise FullStageAV2Error(
                "executor did not produce exactly 48 calls and 96 branches"
            )
        output_path.write_text(
            json.dumps(staged, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return staged


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Guarded S12-f-11 full Stage A runner v2"
    )
    parser.add_argument("--authorization", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--package", default=FULL_PACKAGE, type=Path)
    args = parser.parse_args(argv)
    run_full_stage_a(
        provider_adapter=build_adapter(merged_environment()),
        authorization_path=args.authorization.resolve(),
        output_path=args.output.resolve(),
        package_path=args.package.resolve(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
