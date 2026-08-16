#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pydantic>=2,<3",
# ]
# ///
"""Guarded four-call S12-f-11 schema canary, superseding the v1 scaffold."""

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
    ROOT / "evaluation/sprint-12/optimization/s12-f-11-canary-execution-package.v2.json"
)
CANARY_FREEZE = (
    ROOT / "evaluation/sprint-12/optimization/s12-f-11-canary-freeze.v2.json"
)
CANARY_CASE_SELECTION = (
    ROOT / "evaluation/sprint-12/optimization/s12-f-11-canary-case-selection.v1.json"
)
CANARY_RUNTIME = (
    ROOT / "evaluation/sprint-12/harness/s12-f-11-runtime-configuration.v2.json"
)
CANARY_AUTHORIZATION_CONTRACT = (
    ROOT / "evaluation/sprint-12/harness/s12-f-11-canary-authorization.schema.v2.json"
)
CANARY_PROMPT = (
    ROOT
    / "evaluation/sprint-12/optimization/s12-f-11-m3-prompt-v7-relation-trigger-envelope-examples.v2.txt"
)
CANARY_SCHEMA = (
    ROOT / "evaluation/sprint-12/harness/relation-evidence-envelope.schema.v2.json"
)
CANARY_OUTPUT = (
    ROOT / "evaluation/sprint-12/optimization/s12-f-11-canary-report.v2.json"
)
CANARY_PRICING = (
    ROOT
    / "evaluation/sprint-12/optimization/s12-f-08-pricing-deepseek-v4-flash.v1.json"
)
CANARY_CASE_IDS = ("s12-a-4003", "s12-a-4008", "s12-a-4002", "s12-a-4013")
EXPECTED_CALLS = 4
EXPECTED_BRANCHES = 8
EXPECTED_SCHEMA_VALID = 4
EXPECTED_SCHEMA = "relation-evidence-envelope.v1"
EXPECTED_PROMPT_VERSION = "m3.prompt.v7.relation-trigger-envelope-examples"
EXPECTED_COST_CEILING = Decimal("10.00")

_SAFE_TOP_LEVEL_KEYS = frozenset({"schemaVersion", "extraction", "relationTriggers"})
_SAFE_ERROR_TYPES = frozenset(
    {
        "ValidationError",
        "CanaryExecutionError",
        "ProviderAdapterError",
        "ValueError",
        "TypeError",
        "KeyError",
    }
)
_SAFE_PATH_COMPONENTS = frozenset(
    {
        "schemaVersion",
        "extraction",
        "relationTriggers",
        "modelId",
        "modelVersion",
        "entities",
        "relations",
        "links",
        "abstentionReason",
        "candidateId",
        "type",
        "label",
        "evidence",
        "startOffset",
        "endOffset",
        "text",
        "confidence",
        "predicate",
        "sourceEntityId",
        "targetEntityId",
        "triggerQuote",
    }
)


class CanaryExecutionError(RuntimeError):
    """Raised when the canary cannot execute under its frozen contract."""


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
    """Build an adapter whose runtime contract is explicitly four calls."""

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
        expected_provider_calls=EXPECTED_CALLS,
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
    if (
        package.get("status")
        != "CANARY_PACKAGE_SUPERSEDING_FROZEN_PENDING_AUTHORIZATION"
    ):
        raise CanaryExecutionError(
            "superseding canary package is not pending authorization"
        )
    if package.get("providerExecutionAuthorized") is not False:
        raise CanaryExecutionError("canary package authorizes provider execution")
    if package.get("heldOutInspected") is not False:
        raise CanaryExecutionError("canary package permits held-out access")
    if package.get("experimentId") != "s12-f-11":
        raise CanaryExecutionError("canary package experiment id is incorrect")
    if (
        package.get("caseCount") != EXPECTED_CALLS
        or package.get("providerCalls") != EXPECTED_CALLS
    ):
        raise CanaryExecutionError("canary package is not four calls")
    if package.get("branchOutputs") != EXPECTED_BRANCHES:
        raise CanaryExecutionError("canary package is not eight branches")
    if package.get("requiredSchemaValidResponses") != EXPECTED_SCHEMA_VALID:
        raise CanaryExecutionError("canary package does not require 4/4 schema-valid")
    if (
        package.get("authorizationContract")
        != CANARY_AUTHORIZATION_CONTRACT.relative_to(ROOT).as_posix()
    ):
        raise CanaryExecutionError("canary authorization contract is not v2")
    runtime = _load(CANARY_RUNTIME)
    if runtime.get("expectedProviderCalls") != EXPECTED_CALLS:
        raise CanaryExecutionError("runtime is not explicitly four-call")
    if Decimal(str(runtime.get("worstCaseCostUsd"))) != Decimal("0.03258752"):
        raise CanaryExecutionError("runtime worst-case cost is not the four-call proof")
    runtime_binding = package.get("runtimeConfiguration")
    if not isinstance(runtime_binding, dict) or runtime_binding.get(
        "digest"
    ) != _bound_digest(CANARY_RUNTIME):
        raise CanaryExecutionError("runtime configuration digest mismatch")
    provider_adapter = package.get("providerAdapter")
    if (
        not isinstance(provider_adapter, dict)
        or provider_adapter.get("path") != "scripts/sprint12_provider_adapter.py"
    ):
        raise CanaryExecutionError("concrete provider adapter binding is missing")
    if provider_adapter.get("digest") != _bound_digest(ROOT / provider_adapter["path"]):
        raise CanaryExecutionError("provider adapter digest mismatch")
    bound = package.get("boundDigests")
    if not isinstance(bound, dict) or not bound:
        raise CanaryExecutionError("canary bound digests are missing")
    for relative_path, digest in bound.items():
        path = ROOT / relative_path
        if not path.is_file() or digest != _bound_digest(path):
            raise CanaryExecutionError(f"canary bound digest mismatch: {relative_path}")
    _load(CANARY_SCHEMA)
    selection = _load(CANARY_CASE_SELECTION)
    if selection.get("caseIds") != list(CANARY_CASE_IDS):
        raise CanaryExecutionError("canary case selection is not exact")
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
    exact_flags = {
        "providerExecutionAuthorized": True,
        "providerCalls": EXPECTED_CALLS,
        "requiredSchemaValidResponses": EXPECTED_SCHEMA_VALID,
        "retryPolicy": "none",
        "heldOutInspected": False,
        "stageBAuthorized": False,
        "candidateSelectionAuthorized": False,
        "promotionAuthorized": False,
    }
    for field, expected in exact_flags.items():
        if authorization.get(field) != expected:
            raise CanaryExecutionError(f"authorization field is not exact: {field}")
    if authorization.get("experimentId") != "s12-f-11":
        raise CanaryExecutionError("f11 canary authorization experiment mismatch")
    if authorization.get("executionPackage", {}).get("digest") != file_digest(
        package_path
    ):
        raise CanaryExecutionError("f11 canary authorization package digest mismatch")
    freeze_binding = authorization.get("freezeRecord", {})
    if freeze_binding.get("path") != CANARY_FREEZE.relative_to(ROOT).as_posix():
        raise CanaryExecutionError("f11 canary freeze path mismatch")
    if freeze_binding.get("digest") != file_digest(CANARY_FREEZE):
        raise CanaryExecutionError("f11 canary freeze digest mismatch")
    freeze = _load(CANARY_FREEZE)
    commit_sha = str(authorization.get("commitSha", ""))
    if commit_sha != freeze.get("commitSha") or not commit_sha:
        raise CanaryExecutionError("f11 canary authorization commit mismatch")
    if not _commit_is_ancestor(commit_sha):
        raise CanaryExecutionError("f11 canary authorization commit is not in HEAD")
    if authorization.get("providerAdapter", {}).get("digest") != adapter.adapter_digest:
        raise CanaryExecutionError("f11 canary adapter digest mismatch")
    if (
        authorization.get("runtimeConfiguration", {}).get("digest")
        != adapter.runtime_configuration_digest
    ):
        raise CanaryExecutionError("f11 canary runtime digest mismatch")
    if authorization.get("outputPath") != _resolve_output(output_path):
        raise CanaryExecutionError("f11 canary output path mismatch")
    try:
        ceiling = Decimal(str(authorization.get("costCeilingUsd")))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise CanaryExecutionError("f11 canary cost ceiling is invalid") from error
    if ceiling != EXPECTED_COST_CEILING:
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


def _safe_token(value: object, allowed: frozenset[str], kind: str) -> str | int:
    if isinstance(value, int) and 0 <= value <= 100000:
        return value
    text = str(value)
    if text in allowed:
        return text
    digest = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]
    return f"{kind}:sha256:{digest}"


def _safe_error_type(error: Exception) -> str:
    return str(_safe_token(type(error).__name__, _SAFE_ERROR_TYPES, "error"))


def schema_failure_diagnostic(payload: object, error: Exception) -> dict[str, object]:
    """Return allowlisted structural diagnostics; never persist provider key text."""

    top_level_keys = (
        sorted(_safe_token(key, _SAFE_TOP_LEVEL_KEYS, "key") for key in payload)
        if isinstance(payload, dict)
        else []
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
    errors: list[dict[str, object]] = []
    errors_method = getattr(error, "errors", None)
    if callable(errors_method):
        for item in errors_method()[:20]:
            if isinstance(item, dict):
                errors.append(
                    {
                        "type": _safe_token(
                            item.get("type", "unknown"), _SAFE_ERROR_TYPES, "error"
                        ),
                        "path": [
                            _safe_token(part, _SAFE_PATH_COMPONENTS, "path")
                            for part in item.get("loc", ())
                        ],
                    }
                )
    return {
        "errorType": _safe_error_type(error),
        "errorCount": len(errors),
        "errors": errors,
        "topLevelKeySignature": top_level_keys,
        "arrayCounts": array_counts,
    }


def _selected_cases() -> list[dict[str, Any]]:
    _, selected, _ = load_bound_development_cases()
    by_id = {str(case["caseId"]): case for case in selected}
    if not set(CANARY_CASE_IDS).issubset(by_id):
        raise CanaryExecutionError(
            "canary selection is not contained in frozen development cases"
        )
    return [by_id[case_id] for case_id in CANARY_CASE_IDS]


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


def _capture_error_class(error: Exception) -> str:
    return (
        "usage_invalid"
        if "usage" in str(error).lower() or "token" in str(error).lower()
        else "provider_transport_failure"
    )


def run_canary(
    *,
    provider_adapter: ProviderAdapter,
    package_path: Path = CANARY_PACKAGE,
    authorization_path: Path | None,
    output_path: Path,
) -> dict[str, Any]:
    package = validate_canary_package(package_path, output_path=output_path)
    if not isinstance(provider_adapter, DeepSeekProviderAdapter):
        raise CanaryExecutionError(
            "live canary requires the concrete DeepSeekProviderAdapter"
        )
    authorization = validate_canary_authorization(
        package,
        authorization_path=authorization_path,
        package_path=package_path,
        output_path=output_path,
        adapter=provider_adapter,
    )
    pricing = load_pricing_artifact(CANARY_PRICING)
    records: list[dict[str, Any]] = []
    failure_counts: dict[str, int] = {}
    total_cost = Decimal(0)
    retry_count = 0
    attempts = responses = schema_valid = usage_valid = priced_calls = (
        pricing_failures
    ) = 0
    for case in _selected_cases():
        attempts += 1
        case_id = str(case["caseId"])
        capture: ProviderCapture | None = None
        usage: dict[str, int] | None = None
        failures: list[str] = []
        schema_error: Exception | None = None
        try:
            capture = provider_adapter.capture(
                case_id=case_id,
                raw_text=str(case["source"]["rawText"]),
                prompt_version=EXPECTED_PROMPT_VERSION,
                provider_schema=EXPECTED_SCHEMA,
            )
            responses += 1
            retry_count += capture.retry_count
        except Exception as error:  # noqa: BLE001 - classify without persisting the message.
            failure_class = _capture_error_class(error)
            failures.append(failure_class)
            failure_counts[failure_class] = failure_counts.get(failure_class, 0) + 1
        if capture is not None:
            try:
                RelationEvidenceEnvelopeV1.model_validate(capture.payload)
                schema_valid += 1
            except Exception as error:  # noqa: BLE001 - sanitized below.
                schema_error = error
                failures.append("schema_invalid")
                failure_counts["schema_invalid"] = (
                    failure_counts.get("schema_invalid", 0) + 1
                )
            try:
                usage = _usage(capture)
                usage_valid += 1
            except Exception:  # noqa: BLE001 - classify without persisting the message.
                failures.append("usage_invalid")
                failure_counts["usage_invalid"] = (
                    failure_counts.get("usage_invalid", 0) + 1
                )
            if usage is not None:
                try:
                    total_cost += Decimal(
                        str(cost_usd(usage, {"rates": pricing["rates"]}))
                    )
                    priced_calls += 1
                except Exception:  # noqa: BLE001 - pricing is an independent gate.
                    failures.append("pricing_failure")
                    pricing_failures += 1
                    failure_counts["pricing_failure"] = (
                        failure_counts.get("pricing_failure", 0) + 1
                    )
        status = "schema_valid" if not failures else failures[0]
        records.append(
            {
                "caseId": case_id,
                "labels": list(_selection_labels(case)),
                "status": status,
                "failureClasses": failures,
                "responseReceived": capture is not None,
                "schemaValid": schema_error is None and capture is not None,
                "usageValid": usage is not None,
                "priced": usage is not None and "pricing_failure" not in failures,
                "usage": usage,
                "diagnostic": schema_failure_diagnostic(capture.payload, schema_error)
                if schema_error and capture is not None
                else None,
            }
        )
    cost_ceiling = Decimal(str(authorization["costCeilingUsd"]))
    report = {
        "artifactVersion": "s12.s12-f-11.canary-report.v2",
        "status": "CANARY_EXECUTED",
        "experimentId": "s12-f-11",
        "providerCallsAttempted": attempts,
        "responsesReceived": responses,
        "schemaValidResponses": schema_valid,
        "requiredSchemaValidResponses": EXPECTED_SCHEMA_VALID,
        "usageValidResponses": usage_valid,
        "providerCallsPriced": priced_calls,
        "branchOutputs": responses * 2,
        "retryCount": retry_count,
        "failureCounts": failure_counts,
        "schemaGate": schema_valid == EXPECTED_SCHEMA_VALID,
        "pricing": {
            "providerCallsPriced": priced_calls,
            "pricingFailures": pricing_failures,
            "totalCostUsd": float(total_cost),
            "costCeilingUsd": str(cost_ceiling),
            "costCeilingGate": total_cost <= cost_ceiling,
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Guarded S12-f-11 four-call schema canary v2"
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
