#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pydantic>=2,<3",
# ]
# ///
"""Guarded full S12-f-11 Stage A entrypoint; authorization is mandatory."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_sprint12_next_tool_experiment as legacy
from sprint12_pricing import merged_environment
from sprint12_provider_adapter import (
    DeepSeekProviderAdapter,
    DeepSeekRuntimeConfiguration,
    ProviderAdapter,
)

FULL_PACKAGE = (
    ROOT
    / "evaluation/sprint-12/optimization/s12-f-11-full-stage-a-execution-package.v1.json"
)
FULL_FREEZE = (
    ROOT / "evaluation/sprint-12/optimization/s12-f-11-full-stage-a-freeze.v1.json"
)
FULL_PREREGISTRATION = (
    ROOT
    / "evaluation/sprint-12/optimization/s12-f-11-full-stage-a-preregistration.v1.json"
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
OUTPUT = ROOT / "evaluation/sprint-12/optimization/s12-f-11-full-stage-a-report.v1.json"
EXPECTED_PROMPT = "m3.prompt.v7.relation-trigger-envelope-examples"
EXPECTED_SCHEMA = "relation-evidence-envelope.v1"


class FullStageAError(RuntimeError):
    """Raised when the full Stage A contract is not safe to execute."""


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FullStageAError(f"artifact is not an object: {path.name}")
    return value


def _digest(path: Path) -> str:
    return legacy._bound_file_digest(path)


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def validate_full_package(
    package_path: Path = FULL_PACKAGE,
    *,
    output_path: Path | None = None,
) -> dict[str, Any]:
    package = _load(package_path)
    checks = {
        "status": package.get("status")
        == "EXECUTION_PACKAGE_FROZEN_PENDING_AUTHORIZATION",
        "experiment": package.get("experimentId") == "s12-f-11",
        "providerUnauthorized": package.get("providerExecutionAuthorized") is False,
        "heldOutSealed": package.get("heldOutInspected") is False,
        "stageBClosed": package.get("stageBAuthorized") is False,
        "selectionClosed": package.get("candidateSelectionAuthorized") is False,
        "promotionClosed": package.get("promotionAuthorized") is False,
        "caseCount": package.get("caseCount") == 16,
        "providerCalls": package.get("providerCalls") == 48,
        "branchOutputs": package.get("branchOutputs") == 96,
        "requiredSchema": package.get("requiredSchemaValidResponses") == 48,
        "requiredUsage": package.get("expectedUsageValidResponses") == 48,
        "requiredPricing": package.get("expectedPricedCalls") == 48,
        "retryPolicy": package.get("retryPolicy") == "none",
        "authContract": package.get("authorizationContract")
        == _relative(AUTHORIZATION_CONTRACT),
    }
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise FullStageAError(f"full Stage A package checks failed: {failed}")
    runtime = _load(FULL_RUNTIME)
    if (
        runtime.get("expectedProviderCalls") != 48
        or runtime.get("expectedBranchOutputs") != 96
    ):
        raise FullStageAError("runtime call/branch bounds are not 48/96")
    if Decimal(str(runtime.get("worstCaseCostUsd"))) != Decimal("0.39105024"):
        raise FullStageAError("runtime worst-case cost proof is not 48-call bound")
    if Decimal(str(runtime.get("costProof", {}).get("ceilingUsd"))) != Decimal("10.00"):
        raise FullStageAError("runtime cost ceiling is not exact")
    binding = package.get("executionRunner")
    if not isinstance(binding, dict) or binding.get("path") != _relative(
        Path(__file__)
    ):
        raise FullStageAError("full runner path is not bound")
    if binding.get("digest") != _digest(Path(__file__)):
        raise FullStageAError("full runner digest mismatch")
    adapter = package.get("providerAdapter")
    if (
        not isinstance(adapter, dict)
        or adapter.get("path") != "scripts/sprint12_provider_adapter.py"
    ):
        raise FullStageAError("concrete adapter path is not bound")
    if adapter.get("digest") != _digest(ROOT / adapter["path"]):
        raise FullStageAError("concrete adapter digest mismatch")
    runtime_binding = package.get("runtimeConfiguration")
    if not isinstance(runtime_binding, dict) or runtime_binding.get(
        "path"
    ) != _relative(FULL_RUNTIME):
        raise FullStageAError("runtime path is not bound")
    if runtime_binding.get("digest") != _digest(FULL_RUNTIME):
        raise FullStageAError("runtime digest mismatch")
    if package.get("providerResponseSchema") != EXPECTED_SCHEMA:
        raise FullStageAError("provider response schema is not envelope v1")
    arms = package.get("arms")
    if not isinstance(arms, dict) or any(
        not isinstance(arm, dict)
        or arm.get("providerSchema") != EXPECTED_SCHEMA
        or arm.get("branchOutputSchema") != "m3.v2"
        for arm in arms.values()
    ):
        raise FullStageAError("control/candidate schema binding is not identical")
    bound = package.get("boundDigests")
    if not isinstance(bound, dict) or not bound:
        raise FullStageAError("bound digests are missing")
    for relative_path, expected in bound.items():
        path = ROOT / relative_path
        if not path.is_file() or _digest(path) != expected:
            raise FullStageAError(f"bound digest mismatch: {relative_path}")
    if output_path is not None and output_path.exists():
        raise FullStageAError("refusing to overwrite Stage A output")
    return package


def _configure_legacy_runner() -> None:
    """Reuse the reviewed evaluator/materializer schedule under f11 bindings."""

    legacy.FINAL_PACKAGE = FULL_PACKAGE
    legacy.FINAL_FREEZE = FULL_FREEZE
    legacy.FINAL_PREREGISTRATION = FULL_PREREGISTRATION
    legacy.AUTHORIZATION_CONTRACT = AUTHORIZATION_CONTRACT
    legacy.FINAL_RUNTIME_CONFIGURATION = FULL_RUNTIME
    legacy.FINAL_SELECTION = (
        ROOT / "evaluation/sprint-12/optimization/s12-f-10-case-selection.v2.json"
    )
    legacy.FINAL_PROMPT_VERSION = EXPECTED_PROMPT
    legacy.FINAL_PROVIDER_SCHEMA = EXPECTED_SCHEMA
    legacy.FINAL_PRICING = (
        ROOT
        / "evaluation/sprint-12/optimization/s12-f-08-pricing-deepseek-v4-flash.v1.json"
    )
    legacy.FINAL_METRIC_CONTRACT = (
        ROOT / "evaluation/sprint-12/harness/metric-contract.v2.json"
    )
    legacy.FINAL_SLICE_CONTRACT = (
        ROOT / "evaluation/sprint-12/harness/slice-threshold-contract.v1.json"
    )


def _validate_runtime_configuration() -> dict[str, Any]:
    runtime = _load(FULL_RUNTIME)
    required = {
        "providerType": "openai-response",
        "transport": "deepseek-chat-completions",
        "model": "deepseek-v4-flash",
        "promptVersion": EXPECTED_PROMPT,
        "providerSchema": EXPECTED_SCHEMA,
        "retryPolicy": "none",
        "expectedProviderCalls": 48,
        "expectedBranchOutputs": 96,
    }
    if any(runtime.get(key) != value for key, value in required.items()):
        raise FullStageAError("runtime configuration does not match full Stage A")
    return runtime


def validate_full_authorization(
    package: Mapping[str, Any],
    *,
    authorization_path: Path | None,
    package_path: Path,
    output_path: Path,
    adapter_digest: str,
    runtime_digest: str,
) -> dict[str, Any]:
    if authorization_path is None:
        raise FullStageAError(
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
            raise FullStageAError(f"authorization field is not exact: {key}")
    if authorization.get("executionPackage", {}).get("digest") != _digest(package_path):
        raise FullStageAError("authorization package digest mismatch")
    freeze = _load(FULL_FREEZE)
    freeze_binding = authorization.get("freezeRecord", {})
    if freeze_binding.get("path") != _relative(FULL_FREEZE):
        raise FullStageAError("authorization freeze path mismatch")
    if freeze_binding.get("digest") != _digest(FULL_FREEZE):
        raise FullStageAError("authorization freeze digest mismatch")
    if authorization.get("commitSha") != freeze.get("commitSha") or not freeze.get(
        "commitSha"
    ):
        raise FullStageAError("authorization commit is not exact freeze commit")
    if not legacy.commit_is_ancestor(str(freeze["commitSha"])):
        raise FullStageAError("authorization freeze commit is not an ancestor")
    if authorization.get("providerAdapter", {}).get("digest") != adapter_digest:
        raise FullStageAError("authorization adapter digest mismatch")
    if authorization.get("runtimeConfiguration", {}).get("digest") != runtime_digest:
        raise FullStageAError("authorization runtime digest mismatch")
    if authorization.get("outputPath") != _relative(output_path):
        raise FullStageAError("authorization output path mismatch")
    if Decimal(str(authorization.get("costCeilingUsd"))) != Decimal("10.00"):
        raise FullStageAError("authorization cost ceiling must equal $10.00")
    return authorization


def build_adapter(
    environment: Mapping[str, str] | None = None,
) -> DeepSeekProviderAdapter:
    configuration = DeepSeekRuntimeConfiguration.from_environment(
        environment,
        prompt_path=PROMPT,
        schema_path=SCHEMA,
    )
    configuration = replace(
        configuration,
        prompt_version=EXPECTED_PROMPT,
        prompt_path=_relative(PROMPT),
        schema_path=_relative(SCHEMA),
        expected_provider_calls=48,
    )
    return DeepSeekProviderAdapter(
        configuration,
        prompt_path=PROMPT,
        schema_path=SCHEMA,
    )


def run_full_stage_a(
    *,
    provider_adapter: ProviderAdapter,
    authorization_path: Path | None,
    output_path: Path = OUTPUT,
    package_path: Path = FULL_PACKAGE,
) -> dict[str, Any]:
    _configure_legacy_runner()
    package = validate_full_package(package_path, output_path=output_path)
    if not isinstance(provider_adapter, DeepSeekProviderAdapter):
        raise FullStageAError("full Stage A requires DeepSeekProviderAdapter")
    validate_full_authorization(
        package,
        authorization_path=authorization_path,
        package_path=package_path,
        output_path=output_path,
        adapter_digest=provider_adapter.adapter_digest,
        runtime_digest=provider_adapter.runtime_configuration_digest,
    )
    legacy.validate_final_execution_package = lambda package_path, output_path=None: (
        package
    )
    legacy.validate_stage_a_authorization = lambda *args, **kwargs: {
        "costCeilingUsd": "10.00"
    }
    result = legacy.run_offline_stage_a(
        provider_adapter=provider_adapter,
        package_path=package_path,
        authorization_path=authorization_path,
        output_path=output_path,
        require_concrete_provider_binding=False,
    )
    result["artifactVersion"] = "s12.s12-f-11.full-stage-a-report.v1"
    result["experimentId"] = "s12-f-11"
    result["executionPackagePath"] = _relative(package_path)
    result["freezePath"] = _relative(FULL_FREEZE)
    result["authorizationPath"] = (
        _relative(authorization_path) if authorization_path else None
    )
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Guarded S12-f-11 full Stage A runner")
    parser.add_argument("--authorization", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--package", default=FULL_PACKAGE, type=Path)
    args = parser.parse_args(argv)
    run_full_stage_a(
        provider_adapter=build_adapter(merged_environment()),
        authorization_path=args.authorization,
        output_path=args.output,
        package_path=args.package,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
