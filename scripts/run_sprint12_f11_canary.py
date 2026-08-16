#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pydantic>=2,<3",
# ]
# ///
"""Guarded four-case schema canary for the superseding S12-f-11 experiment.

This module is prepared offline only. The live entrypoint requires a separate
S12-f-11 canary authorization and never accepts the S12-f-10 Approval B.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from projecta_api.extraction.relation_evidence_envelope import (
    RelationEvidenceEnvelopeV1,
)
from run_sprint12_next_tool_experiment import (
    _selection_labels,
    load_bound_development_cases,
)
from sprint12_pricing import (
    cost_usd,
    file_digest,
    load_pricing_artifact,
    merged_environment,
)
from sprint12_provider_adapter import (
    DeepSeekProviderAdapter,
    DeepSeekRuntimeConfiguration,
    ProviderAdapter,
    ProviderCapture,
)

CANARY_PACKAGE = (
    ROOT / "evaluation/sprint-12/optimization/s12-f-11-canary-execution-package.v1.json"
)
CANARY_FREEZE = (
    ROOT / "evaluation/sprint-12/optimization/s12-f-11-canary-freeze.v1.json"
)
CANARY_CASE_SELECTION = (
    ROOT / "evaluation/sprint-12/optimization/s12-f-11-canary-case-selection.v1.json"
)
CANARY_RUNTIME = (
    ROOT / "evaluation/sprint-12/harness/s12-f-11-runtime-configuration.v1.json"
)
CANARY_AUTHORIZATION_CONTRACT = (
    ROOT / "evaluation/sprint-12/harness/s12-f-11-canary-authorization.schema.v1.json"
)
CANARY_PROMPT = (
    ROOT
    / "evaluation/sprint-12/optimization/s12-f-11-m3-prompt-v7-relation-trigger-envelope-examples.v1.txt"
)
CANARY_SCHEMA = (
    ROOT / "evaluation/sprint-12/harness/relation-evidence-envelope.schema.v2.json"
)
CANARY_OUTPUT = (
    ROOT / "evaluation/sprint-12/optimization/s12-f-11-canary-report.v1.json"
)
CANARY_PRICING = (
    ROOT
    / "evaluation/sprint-12/optimization/s12-f-08-pricing-deepseek-v4-flash.v1.json"
)
CANARY_CASE_IDS = ("s12-a-4003", "s12-a-4008", "s12-a-4002", "s12-a-4013")
EXPECTED_SCHEMA = "relation-evidence-envelope.v1"
EXPECTED_PROMPT_VERSION = "m3.prompt.v7.relation-trigger-envelope-examples"


class CanaryExecutionError(RuntimeError):
    """Raised when the canary cannot be executed under its frozen contract."""


def _bound_digest(path: Path) -> str:
    return (
        "sha256:"
        + hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    )


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CanaryExecutionError(f"artifact is not an object: {path.name}")
    return value


def build_canary_adapter(
    environment: Mapping[str, str] | None = None,
    *,
    transport: Any = None,
) -> DeepSeekProviderAdapter:
    """Build the f11 adapter against the v7 prompt and v2 schema artifact."""

    configuration = DeepSeekRuntimeConfiguration.from_environment(
        environment,
        prompt_path=CANARY_PROMPT,
        schema_path=CANARY_SCHEMA,
    )
    configuration = replace(
        configuration,
        prompt_version=EXPECTED_PROMPT_VERSION,
        prompt_path=CANARY_PROMPT.relative_to(ROOT).as_posix(),
        schema_path=CANARY_SCHEMA.relative_to(ROOT).as_posix(),
    )
    return DeepSeekProviderAdapter(
        configuration,
        transport=transport,
        prompt_path=CANARY_PROMPT,
        schema_path=CANARY_SCHEMA,
    )


def validate_canary_package(
    package_path: Path = CANARY_PACKAGE,
    *,
    output_path: Path | None = None,
) -> dict[str, Any]:
    package = _load(package_path)
    if package.get("status") != "CANARY_PACKAGE_FROZEN_PENDING_AUTHORIZATION":
        raise CanaryExecutionError("canary package is not pending authorization")
    if package.get("providerExecutionAuthorized") is not False:
        raise CanaryExecutionError("canary package authorizes provider execution")
    if package.get("heldOutInspected") is not False:
        raise CanaryExecutionError("canary package permits held-out access")
    if package.get("experimentId") != "s12-f-11":
        raise CanaryExecutionError("canary package experiment id is incorrect")
    if package.get("caseCount") != 4 or package.get("providerCalls") != 4:
        raise CanaryExecutionError("canary package is not four calls")
    if package.get("requiredSchemaValidResponses") != 4:
        raise CanaryExecutionError("canary package does not require 4/4 schema-valid")
    if (
        package.get("authorizationContract")
        != CANARY_AUTHORIZATION_CONTRACT.relative_to(ROOT).as_posix()
    ):
        raise CanaryExecutionError("canary authorization contract is not bound")
    provider_adapter = package.get("providerAdapter")
    if not isinstance(provider_adapter, dict):
        raise CanaryExecutionError("canary provider adapter binding is missing")
    if provider_adapter.get("path") != "scripts/sprint12_provider_adapter.py":
        raise CanaryExecutionError("canary adapter path is not allowlisted")
    if provider_adapter.get("digest") != _bound_digest(ROOT / provider_adapter["path"]):
        raise CanaryExecutionError("canary provider adapter digest mismatch")
    runtime = package.get("runtimeConfiguration")
    if not isinstance(runtime, dict):
        raise CanaryExecutionError("canary runtime binding is missing")
    if runtime.get("path") != CANARY_RUNTIME.relative_to(ROOT).as_posix():
        raise CanaryExecutionError("canary runtime path is not allowlisted")
    if runtime.get("digest") != _bound_digest(CANARY_RUNTIME):
        raise CanaryExecutionError("canary runtime digest mismatch")
    bound = package.get("boundDigests")
    if not isinstance(bound, dict) or not bound:
        raise CanaryExecutionError("canary bound digests are missing")
    for relative_path, digest in bound.items():
        path = ROOT / relative_path
        if not path.is_file() or digest != _bound_digest(path):
            raise CanaryExecutionError(f"canary bound digest mismatch: {relative_path}")
    _load(CANARY_SCHEMA)
    _load(CANARY_CASE_SELECTION)
    if output_path is not None and output_path.exists():
        raise CanaryExecutionError("refusing to overwrite canary output")
    return package


def _resolve_output(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def validate_canary_authorization(
    package: Mapping[str, Any],
    *,
    authorization_path: Path | None,
    package_path: Path,
    output_path: Path,
    adapter: DeepSeekProviderAdapter,
) -> dict[str, Any]:
    if authorization_path is None:
        raise CanaryExecutionError("a separate f11 canary authorization is required")
    authorization = _load(authorization_path)
    if authorization.get("status") != "APPROVED_FOR_DEVELOPMENT_CANARY":
        raise CanaryExecutionError("f11 canary authorization is not approved")
    if authorization.get("providerExecutionAuthorized") is not True:
        raise CanaryExecutionError("f11 canary provider execution is not authorized")
    if authorization.get("experimentId") != "s12-f-11":
        raise CanaryExecutionError("f11 canary authorization experiment mismatch")
    if authorization.get("heldOutInspected") is not False:
        raise CanaryExecutionError("f11 canary authorization permits held-out access")
    if authorization.get("retryPolicy") != "none":
        raise CanaryExecutionError("f11 canary retry policy is not none")
    if authorization.get("executionPackage", {}).get("digest") != file_digest(
        package_path
    ):
        raise CanaryExecutionError("f11 canary authorization package digest mismatch")
    freeze_binding = authorization.get("freezeRecord", {})
    if freeze_binding.get("path") != CANARY_FREEZE.relative_to(ROOT).as_posix():
        raise CanaryExecutionError("f11 canary freeze path mismatch")
    if freeze_binding.get("digest") != file_digest(CANARY_FREEZE):
        raise CanaryExecutionError("f11 canary freeze digest mismatch")
    commit_sha = str(authorization.get("commitSha", ""))
    freeze = _load(CANARY_FREEZE)
    if commit_sha != freeze.get("commitSha") or not commit_sha:
        raise CanaryExecutionError("f11 canary authorization commit mismatch")
    if not _commit_is_ancestor(commit_sha):
        raise CanaryExecutionError("f11 canary authorization commit is not in HEAD")
    adapter_binding = authorization.get("providerAdapter", {})
    if adapter_binding.get("digest") != adapter.adapter_digest:
        raise CanaryExecutionError("f11 canary adapter digest mismatch")
    runtime_binding = authorization.get("runtimeConfiguration", {})
    if runtime_binding.get("digest") != adapter.runtime_configuration_digest:
        raise CanaryExecutionError("f11 canary runtime digest mismatch")
    if authorization.get("outputPath") != _resolve_output(output_path):
        raise CanaryExecutionError("f11 canary output path mismatch")
    try:
        ceiling = Decimal(str(authorization.get("costCeilingUsd")))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise CanaryExecutionError("f11 canary cost ceiling is invalid") from error
    if ceiling != Decimal("10.00"):
        raise CanaryExecutionError("f11 canary cost ceiling must equal $10.00")
    return authorization


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


def schema_failure_diagnostic(payload: object, error: Exception) -> dict[str, object]:
    """Return structural diagnostics only; never persist provider/source values."""

    top_level_keys = (
        sorted(str(key) for key in payload) if isinstance(payload, dict) else []
    )
    array_counts: dict[str, int] = {}
    if isinstance(payload, dict):
        for key in ("entities", "relations", "links", "relationTriggers"):
            value = payload.get(key)
            if isinstance(value, list):
                array_counts[key] = len(value)
        extraction = payload.get("extraction")
        if isinstance(extraction, dict):
            for key in ("entities", "relations", "links"):
                value = extraction.get(key)
                if isinstance(value, list):
                    array_counts[f"extraction.{key}"] = len(value)
    errors_method = getattr(error, "errors", None)
    errors: list[dict[str, object]] = []
    if callable(errors_method):
        for item in errors_method()[:20]:
            if isinstance(item, dict):
                errors.append(
                    {
                        "type": str(item.get("type", "unknown")),
                        "path": [str(part) for part in item.get("loc", ())],
                    }
                )
    return {
        "errorType": type(error).__name__,
        "errorCount": len(errors),
        "errors": errors,
        "topLevelKeySignature": top_level_keys,
        "arrayCounts": array_counts,
    }


def _selected_cases() -> list[dict[str, Any]]:
    _, selected, _ = load_bound_development_cases()
    by_id = {str(case["caseId"]): case for case in selected}
    if set(by_id) < set(CANARY_CASE_IDS):
        raise CanaryExecutionError(
            "canary case selection is not contained in frozen development cases"
        )
    return [by_id[case_id] for case_id in CANARY_CASE_IDS]


def run_canary(
    *,
    provider_adapter: ProviderAdapter,
    package_path: Path = CANARY_PACKAGE,
    authorization_path: Path | None,
    output_path: Path,
) -> dict[str, Any]:
    package = validate_canary_package(package_path, output_path=output_path)
    adapter = provider_adapter
    if not isinstance(adapter, DeepSeekProviderAdapter):
        raise CanaryExecutionError(
            "live canary requires the concrete DeepSeekProviderAdapter"
        )
    authorization = validate_canary_authorization(
        package,
        authorization_path=authorization_path,
        package_path=package_path,
        output_path=output_path,
        adapter=adapter,
    )
    pricing = load_pricing_artifact(CANARY_PRICING)
    records: list[dict[str, Any]] = []
    failure_counts: dict[str, int] = {}
    total_cost = 0.0
    retry_count = 0
    schema_valid = 0
    for case in _selected_cases():
        case_id = str(case["caseId"])
        capture: ProviderCapture | None = None
        usage: dict[str, int] | None = None
        try:
            capture = adapter.capture(
                case_id=case_id,
                raw_text=str(case["source"]["rawText"]),
                prompt_version=EXPECTED_PROMPT_VERSION,
                provider_schema=EXPECTED_SCHEMA,
            )
            retry_count += capture.retry_count
            RelationEvidenceEnvelopeV1.model_validate(capture.payload)
            schema_valid += 1
            usage = _usage(capture)
            total_cost += cost_usd(usage, {"rates": pricing["rates"]})
            records.append(
                {
                    "caseId": case_id,
                    "labels": list(_selection_labels(case)),
                    "status": "schema_valid",
                    "usage": usage,
                    "diagnostic": None,
                }
            )
        except Exception as error:  # noqa: BLE001 - canary records fail-closed diagnostics.
            failure_counts["schema_invalid"] = (
                failure_counts.get("schema_invalid", 0) + 1
            )
            if capture is not None:
                usage = _usage(capture)
                total_cost += cost_usd(usage, {"rates": pricing["rates"]})
            records.append(
                {
                    "caseId": case_id,
                    "labels": list(_selection_labels(case)),
                    "status": "schema_invalid",
                    "usage": usage,
                    "diagnostic": schema_failure_diagnostic(
                        capture.payload if capture is not None else {}, error
                    ),
                }
            )
    report = {
        "artifactVersion": "s12.s12-f-11.canary-report.v1",
        "status": "CANARY_EXECUTED",
        "experimentId": "s12-f-11",
        "providerCalls": len(records),
        "schemaValidResponses": schema_valid,
        "requiredSchemaValidResponses": 4,
        "schemaGate": schema_valid == 4,
        "retryCount": retry_count,
        "failureCounts": failure_counts,
        "pricing": {
            "providerCallsPriced": len(records),
            "totalCostUsd": total_cost,
            "costCeilingUsd": authorization["costCeilingUsd"],
            "costCeilingGate": total_cost <= float(authorization["costCeilingUsd"]),
        },
        "records": records,
        "rawSensitiveDataIncluded": False,
        "heldOutInspected": False,
        "stageBAuthorized": False,
        "candidateSelectionAuthorized": False,
        "promotionAuthorized": False,
    }
    if output_path.exists():
        raise CanaryExecutionError("refusing to overwrite canary output")
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def _usage(capture: ProviderCapture) -> dict[str, int]:
    if capture.usage is None:
        raise CanaryExecutionError("canary provider usage is missing")
    required = (
        "inputTokens",
        "promptCacheHitTokens",
        "promptCacheMissTokens",
        "outputTokens",
    )
    if any(capture.usage.get(key) is None for key in required):
        raise CanaryExecutionError("canary provider usage is incomplete")
    usage = {key: int(capture.usage[key]) for key in required}
    if (
        usage["inputTokens"]
        != usage["promptCacheHitTokens"] + usage["promptCacheMissTokens"]
    ):
        raise CanaryExecutionError("canary provider cache counters do not reconcile")
    return usage


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Guarded S12-f-11 four-case schema canary"
    )
    parser.add_argument("--authorization", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--package", default=CANARY_PACKAGE, type=Path)
    args = parser.parse_args(argv)
    adapter = build_canary_adapter(merged_environment())
    run_canary(
        provider_adapter=adapter,
        package_path=args.package,
        authorization_path=args.authorization,
        output_path=args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
