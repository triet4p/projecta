#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["jsonschema>=4.23,<5"]
# ///
"""Guarded, versioned Stage A runner with RM-40 runtime diagnostics.

This module is the first v9 execution boundary.  It reuses the frozen metric
mechanics, but owns v9 custody, authorization, and diagnostic persistence.
Only finite, sanitized reason codes cross the report boundary.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections import deque
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_sprint12_f12_stage_a_v2 as v2
import run_sprint12_f12_stage_a_v3 as v3
import run_sprint12_f12_stage_a_v4 as v4
import s12_f12_rm40_offline_runtime as rm40
from s12_f12_rm30_diagnostic_remediation import (
    EVIDENCE_REASON_CODES,
    SCHEMA_REASON_CODES,
    SanitizedReason,
    classify_schema_failure,
)
from sprint12_f12_two_step_contracts_v5 import validate_stage1_response, validate_stage2_response

PACKAGE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm32-execution-package.v9.json"
PREREG = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm32-preregistration.v9.json"
FREEZE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm32-technical-freeze.v9.json"
REPORT_SCHEMA = ROOT / "evaluation/sprint-12/harness/s12-f-12-stage-a-report.schema.v9.json"
AUTHORIZATION_SCHEMA = ROOT / "evaluation/sprint-12/harness/s12-f-12-authorization.schema.v9.json"
OUTPUT = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v9.json"


class F12StageAV9Error(RuntimeError):
    """Raised when the v9 execution boundary is unsafe."""


_PENDING_SCHEMA_REASONS: deque[tuple[str, SanitizedReason]] = deque()


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _zero_counts(codes: Sequence[str]) -> dict[str, int]:
    return {code: 0 for code in codes}


def _schema_reason(stage: str, detail: str | None) -> SanitizedReason:
    reason = classify_schema_failure(stage, detail)
    _PENDING_SCHEMA_REASONS.append((stage, reason))
    return reason


def _safe_stage1_v9(capture: Any, source_length: int) -> tuple[tuple[Any, ...], bool, str | None]:
    if capture is None:
        return (), True, "missing_output"
    try:
        candidates, abstention = validate_stage1_response(
            capture.payload, source_length=source_length
        )
        return candidates, abstention, None
    except Exception as error:  # noqa: BLE001 - every malformed response fails closed
        _schema_reason("stage1", str(error))
        return (), True, "schema_invalid"


def _safe_stage2_v9(
    capture: Any, table: Sequence[Any], source_length: int
) -> tuple[tuple[Any, ...], bool, str | None]:
    if capture is None:
        return (), True, "missing_output"
    try:
        relations, abstention = validate_stage2_response(
            capture.payload, candidate_table=table, source_length=source_length
        )
        return relations, abstention, None
    except Exception as error:  # noqa: BLE001 - every malformed response fails closed
        _schema_reason("stage2", str(error))
        return (), True, "schema_invalid"


def _take_schema_reasons(stage: str, count: int) -> dict[str, int]:
    result = _zero_counts(SCHEMA_REASON_CODES)
    for _ in range(count):
        if not _PENDING_SCHEMA_REASONS:
            reason = SanitizedReason("validation_detail_unavailable", False)
        else:
            pending_stage, reason = _PENDING_SCHEMA_REASONS.popleft()
            if pending_stage != stage:
                reason = SanitizedReason("validation_detail_unavailable", False)
        result[reason.code] += 1
    return result


def _merge_counts(left: Mapping[str, int], right: Mapping[str, int]) -> dict[str, int]:
    keys = set(left) | set(right)
    return {key: int(left.get(key, 0)) + int(right.get(key, 0)) for key in sorted(keys)}


def _arm_record_v9(*args: Any, **kwargs: Any) -> dict[str, Any]:
    result = v4._arm_record(*args, **kwargs)
    case = args[0] if args else kwargs["case"]
    predicted_entities = kwargs["predicted_entities"]
    relations = kwargs["relations"]
    gold_candidates = kwargs["gold_candidates"]
    is_gold = bool(kwargs["is_gold_arm"])
    schema_counts = _zero_counts(SCHEMA_REASON_CODES)
    if not is_gold:
        stage1_failure = kwargs.get("stage1_failure")
        stage2_failure = kwargs.get("stage2_failure")
        schema_counts = _merge_counts(
            _take_schema_reasons("stage1", int(stage1_failure == "schema_invalid")),
            _take_schema_reasons("stage2", int(stage2_failure == "schema_invalid")),
        )
    elif kwargs.get("stage2_failure") == "schema_invalid":
        schema_counts = _take_schema_reasons("stage2", 1)
    evidence_counts = _zero_counts(EVIDENCE_REASON_CODES)
    # The gold-relations arm is a deterministic control, not a provider
    # response. Its source-proof metadata is outside the materializer-failure
    # denominator and must not create diagnostic failures.
    if not is_gold or kwargs.get("stage2") is not None:
        evidence_counts = rm40.diagnose_arm(
            case,
            relations=relations,
            predicted_entities=predicted_entities,
            gold_candidates=gold_candidates,
            is_gold_arm=is_gold,
            score_result=result,
        )["evidenceReasonCounts"]
    expected_schema_failures = sum(
        int(value == "schema_invalid")
        for value in (kwargs.get("stage1_failure"), kwargs.get("stage2_failure"))
    )
    if sum(schema_counts.values()) != expected_schema_failures:
        raise F12StageAV9Error("schema reason counts do not reconcile with arm failures")
    if sum(evidence_counts.values()) != int(result["relation"]["invalidEvidenceCount"]):
        raise F12StageAV9Error(
            "evidence reason counts do not reconcile with arm materializer failures"
        )
    result["diagnostics"] = {
        "schemaReasonCounts": schema_counts,
        "evidenceReasonCounts": evidence_counts,
        "rawDataIncluded": False,
    }
    return result


def _aggregate_arm_v9(records: Sequence[Mapping[str, Any]], thresholds: Mapping[str, float]) -> dict[str, Any]:
    result = v4._aggregate_arm(records, thresholds)
    schema = _zero_counts(SCHEMA_REASON_CODES)
    evidence = _zero_counts(EVIDENCE_REASON_CODES)
    for record in records:
        diagnostics = record.get("diagnostics", {})
        schema = _merge_counts(schema, diagnostics.get("schemaReasonCounts", {}))
        evidence = _merge_counts(evidence, diagnostics.get("evidenceReasonCounts", {}))
    result["diagnostics"] = {
        "schemaReasonCounts": schema,
        "evidenceReasonCounts": evidence,
        "rawDataIncluded": False,
    }
    return result


def _top_level_diagnostics(report: Mapping[str, Any]) -> dict[str, Any]:
    schema = {
        arm: _zero_counts(SCHEMA_REASON_CODES)
        for arm in ("predicted-entities", "gold-entities", "gold-relations")
    }
    evidence = {
        arm: _zero_counts(EVIDENCE_REASON_CODES)
        for arm in ("predicted-entities", "gold-entities", "gold-relations")
    }
    for record in report["caseRecords"]:
        for arm in schema:
            diagnostics = record["arms"][arm].get("diagnostics", {})
            schema[arm] = _merge_counts(schema[arm], diagnostics.get("schemaReasonCounts", {}))
            evidence[arm] = _merge_counts(evidence[arm], diagnostics.get("evidenceReasonCounts", {}))
    schema_total = sum(sum(values.values()) for values in schema.values())
    evidence_total = sum(sum(values.values()) for values in evidence.values())
    return {
        "schemaReasonCounts": schema,
        "evidenceReasonCounts": evidence,
        "schemaFailureTotal": schema_total,
        "evidenceFailureTotal": evidence_total,
        "reasonCountsReconciled": all(
            set(values) == set(SCHEMA_REASON_CODES) for values in schema.values()
        )
        and all(set(values) == set(EVIDENCE_REASON_CODES) for values in evidence.values()),
        "rawDataPolicy": {
            "rawSourceTextIncluded": False,
            "rawProviderPayloadIncluded": False,
            "rawValidationDetailIncluded": False,
            "rawTriggerQuoteIncluded": False,
        },
    }


def _validate_report_schema_v9(report: dict[str, Any]) -> None:
    report["artifactVersion"] = "s12-f-12.stage-a-report.v9"
    if _PENDING_SCHEMA_REASONS:
        raise F12StageAV9Error("unconsumed schema diagnostic reason")
    diagnostics = _top_level_diagnostics(report)
    hard_gates = report.get("metrics", {}).get("hardGates", {})
    failure_classes = report.get("accounting", {}).get("failureClasses", {})
    if diagnostics["schemaFailureTotal"] != int(hard_gates.get("schemaInvalid", -1)):
        raise F12StageAV9Error(
            "schema diagnostic total does not reconcile with schemaInvalid hard gate"
        )
    if diagnostics["schemaFailureTotal"] != int(
        failure_classes.get("schemaInvalid", -1)
    ):
        raise F12StageAV9Error(
            "schema diagnostic total does not reconcile with accounting schemaInvalid"
        )
    if diagnostics["evidenceFailureTotal"] != int(hard_gates.get("invalidEvidence", -1)):
        raise F12StageAV9Error(
            "evidence diagnostic total does not reconcile with invalidEvidence hard gate"
        )
    report["diagnostics"] = diagnostics
    try:
        from jsonschema import Draft202012Validator
    except ImportError as error:  # pragma: no cover - environment guard
        raise F12StageAV9Error("jsonschema is required; refusing permissive validation") from error
    schema = v3.load(REPORT_SCHEMA)
    errors = sorted(Draft202012Validator(schema).iter_errors(report), key=lambda item: list(item.path))
    if errors:
        location = ".".join(str(item) for item in errors[0].path) or "<root>"
        raise F12StageAV9Error(f"report v9 JSON Schema validation failed at {location}: {errors[0].message}")


def _runtime_bound_digests(package: Mapping[str, Any]) -> Mapping[str, str]:
    values = package.get("runtimeBoundDigests")
    if not isinstance(values, Mapping) or not values:
        raise F12StageAV9Error("runtimeBoundDigests must be a non-empty mapping")
    return {str(path): str(value) for path, value in values.items()}


def validate_preparation_v9(package_path: Path = PACKAGE, *, output_path: Path = OUTPUT) -> dict[str, Any]:
    package = v3.load(package_path)
    prereg = v3.load(PREREG)
    freeze = v3.load(FREEZE)
    commit = package.get("executionCommitSha")
    if not isinstance(commit, str) or len(commit) != 40:
        raise F12StageAV9Error("package must bind a full executionCommitSha")
    if prereg.get("executionCommitSha") != commit or freeze.get("executionCommitSha") != commit:
        raise F12StageAV9Error("package, preregistration and freeze commit mismatch")
    if package.get("status") != "EXECUTION_PACKAGE_PREPARED_PENDING_RM43_OWNER_ISSUANCE_REVIEW":
        raise F12StageAV9Error("package is not pending RM43 owner issuance review")
    runtime = _runtime_bound_digests(package)
    prep = package.get("preparationEvidence", {})
    if not isinstance(prep, Mapping):
        raise F12StageAV9Error("preparationEvidence must be a mapping")
    if set(runtime) & set(prep):
        raise F12StageAV9Error("runtime and preparation evidence paths must be disjoint")
    v3._verify_exact_commit(commit, runtime)
    if freeze.get("executionPackageDigest") != digest(package_path):
        raise F12StageAV9Error("freeze package digest mismatch")
    if freeze.get("preregistrationDigest") != digest(PREREG):
        raise F12StageAV9Error("freeze preregistration digest mismatch")
    for artifact in (package, prereg, freeze):
        if any(artifact.get(key) is not False for key in (
            "preregistrationIssued", "technicalFreezeIssued", "providerExecutionAuthorized",
            "newAuthorizationIssued", "validationAccessAuthorized", "heldOutAccessAuthorized",
            "stageBAuthorized", "candidateSelectionAuthorized", "promotionAuthorized",
        )):
            raise F12StageAV9Error("execution governance is open")
    if output_path.exists():
        raise F12StageAV9Error("refusing to overwrite final v9 report")
    return _legacy_package_view(package, prereg, freeze)


def _legacy_package_view(package: Mapping[str, Any], prereg: Mapping[str, Any], freeze: Mapping[str, Any]) -> dict[str, Any]:
    view = dict(package)
    view.update(
        {
            "status": "EXECUTION_PACKAGE_PREPARED_PENDING_RM43_OWNER_ISSUANCE_REVIEW",
            "commitSha": package["executionCommitSha"],
            "preregistration": {"path": _relative(PREREG), "digest": digest(PREREG)},
            "freezeRecord": _relative(FREEZE),
            "providerCalls": int(prereg["execution"]["plannedProviderCalls"]),
            "relationBranchOutputs": int(prereg["execution"]["relationBranchOutputs"]),
            "currentExecutionPaths": list(package["runtimeBoundDigests"]),
            "exactCommitBoundPaths": list(package["runtimeBoundDigests"]),
        }
    )
    return view


def validate_authorization_v9(
    authorization_path: Path,
    *,
    package_path: Path = PACKAGE,
    freeze_path: Path = FREEZE,
    output_path: Path = OUTPUT,
) -> dict[str, Any]:
    authorization = v3.load(authorization_path)
    package = v3.load(package_path)
    freeze = v3.load(freeze_path)
    try:
        from jsonschema import Draft202012Validator
    except ImportError as error:  # pragma: no cover
        raise F12StageAV9Error("jsonschema is required; refusing authorization validation") from error
    errors = sorted(
        Draft202012Validator(v3.load(AUTHORIZATION_SCHEMA)).iter_errors(authorization),
        key=lambda item: list(item.path),
    )
    if errors:
        raise F12StageAV9Error(f"authorization schema failed: {errors[0].message}")
    if authorization["executionCommitSha"] != package["executionCommitSha"]:
        raise F12StageAV9Error("authorization commit mismatch")
    if authorization["executionPackageDigest"] != digest(package_path) or authorization["technicalFreezeDigest"] != digest(freeze_path):
        raise F12StageAV9Error("authorization lineage digest mismatch")
    v3._verify_exact_commit(package["executionCommitSha"], _runtime_bound_digests(package))
    if authorization["outputPath"] != _relative(output_path) or output_path.exists():
        raise F12StageAV9Error("authorization output path is unsafe")
    return authorization


def _configure() -> None:
    v3.PACKAGE = PACKAGE
    v3.PREREG = PREREG
    v3.FREEZE = FREEZE
    v3.REPORT_SCHEMA = REPORT_SCHEMA
    v3.OUTPUT = OUTPUT
    v3._safe_stage1 = _safe_stage1_v9
    v3._safe_stage2 = _safe_stage2_v9
    v3._gold_relation_candidates = v4._gold_relation_candidates
    v3._slice_groups = v4._slice_groups
    v3._aggregate_arm = _aggregate_arm_v9
    v3._arm_record = _arm_record_v9
    v3._validate_report_schema = _validate_report_schema_v9
    v3.validate_preparation = validate_preparation_v9
    v3.validate_authorization = validate_authorization_v9
    v2._normalize_gold_relations = v4._normalize_gold_relations
    v2._contexts = v4._contexts


def run_stage_a(**kwargs: Any) -> dict[str, Any]:
    _PENDING_SCHEMA_REASONS.clear()
    _configure()
    kwargs.setdefault("package_path", PACKAGE)
    kwargs.setdefault("output_path", OUTPUT)
    return v3.run_stage_a(**kwargs)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Guarded S12-f-12 Stage A runner v9")
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
