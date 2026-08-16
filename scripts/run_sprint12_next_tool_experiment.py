#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pydantic>=2,<3",
# ]
# ///
"""Offline-complete paired runner for the S12-f-10 tool experiment.

The runner accepts an explicitly injected provider adapter, captures one
versioned envelope per case/run, then scores control and candidate branches
from the same immutable snapshot.  It never retries, persists raw source or
provider payloads, or authorizes a provider call by itself.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import sprint12_evaluator as evaluator

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

from projecta_api.extraction.relation_evidence_envelope import (
    RelationEvidenceEnvelopeV1,
    materialize_relation_evidence_envelope,
)
from pydantic import ValidationError
from shared_response_pairing import (
    CapturedProviderResponse,
    branch_captured_response,
    response_digest,
)
from sprint12_pricing import cost_usd, file_digest, load_pricing_artifact
from sprint12_provider_adapter import ProviderAdapter, ProviderCapture

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGE = (
    ROOT / "evaluation/sprint-12/optimization/s12-next-tool-execution-package-draft.v1.json"
)
FINAL_PACKAGE = ROOT / "evaluation/sprint-12/optimization/s12-f-10-execution-package.v4.json"
FINAL_FREEZE = ROOT / "evaluation/sprint-12/optimization/s12-f-10-execution-package-freeze.v4.json"
FINAL_PREREGISTRATION = ROOT / "evaluation/sprint-12/optimization/s12-f-10-relation-evidence-shared-response-preregistration.v3.json"
AUTHORIZATION_CONTRACT = ROOT / "evaluation/sprint-12/harness/s12-f-10-stage-a-authorization.schema.v2.json"
FINAL_SELECTION = ROOT / "evaluation/sprint-12/optimization/s12-f-10-case-selection.v2.json"
FINAL_ATOMIC = ROOT / "evaluation/sprint-12/corpus/v3-frozen/atomic-v3.frozen.v1.json"
FINAL_SCENARIO = ROOT / "evaluation/sprint-12/corpus/v3-frozen/scenario-v3.frozen.v1.json"
FINAL_MANIFEST = ROOT / "evaluation/sprint-12/corpus/v3-frozen/atomic-manifest.v1.json"
FINAL_PRICING = ROOT / "evaluation/sprint-12/optimization/s12-f-08-pricing-deepseek-v4-flash.v1.json"
FINAL_SLICE_CONTRACT = ROOT / "evaluation/sprint-12/harness/slice-threshold-contract.v1.json"
FINAL_METRIC_CONTRACT = ROOT / "evaluation/sprint-12/harness/metric-contract.v2.json"
FINAL_PROMPT_VERSION = "m3.prompt.v6.relation-trigger-envelope"
FINAL_PROVIDER_SCHEMA = "relation-evidence-envelope.v1"

EXPECTED_SCHEDULE = (
    {"pairId": "pair-1", "runNumber": 1, "armOrder": ("control", "candidate")},
    {"pairId": "pair-2", "runNumber": 2, "armOrder": ("candidate", "control")},
    {"pairId": "pair-3", "runNumber": 3, "armOrder": ("control", "candidate")},
)


class ExecutionPackageError(RuntimeError):
    """Raised when a package is not safe to use for provider execution."""


def _bound_file_digest(path: Path) -> str:
    """Hash the canonical LF blob representation used by Git freeze checks."""

    return "sha256:" + hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def commit_is_ancestor(commit_sha: str) -> bool:
    """Return whether the authorization commit is present in the current tree."""

    if not commit_sha:
        return False
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


def validate_execution_package(
    package_path: Path = DEFAULT_PACKAGE,
    *,
    commit_validator: Callable[[str], bool] = commit_is_ancestor,
) -> dict[str, Any]:
    """Validate authorization, commit and digest bindings before any call."""

    package = _load(package_path)
    if package.get("status") != "EXECUTION_PACKAGE_FROZEN":
        raise ExecutionPackageError("execution package is not frozen")
    if package.get("providerExecutionAuthorized") is not True:
        raise ExecutionPackageError("provider execution is not authorized")
    if package.get("heldOutInspected") is not False:
        raise ExecutionPackageError("package permits held-out inspection")
    if package.get("executionRunnerImplemented") is not True:
        raise ExecutionPackageError("execution runner is not marked implemented")

    commit_sha = str(package.get("commitSha", ""))
    if not commit_sha or not commit_validator(commit_sha):
        raise ExecutionPackageError("execution-package commit is not bound to HEAD")

    runner = package.get("executionRunner")
    if not isinstance(runner, dict):
        raise ExecutionPackageError("execution runner binding is missing")
    runner_path = str(runner.get("path", ""))
    if runner_path != "scripts/run_sprint12_next_tool_experiment.py":
        raise ExecutionPackageError("execution runner path is not allowlisted")
    if runner.get("digest") != file_digest(ROOT / runner_path):
        raise ExecutionPackageError("execution runner digest mismatch")

    mismatches = {
        path: digest
        for path, digest in package.get("boundDigests", {}).items()
        if digest != file_digest(ROOT / path)
    }
    if mismatches:
        raise ExecutionPackageError("bound execution-package digest mismatch")
    return package


def run_paired_schedule(
    case_ids: Sequence[str],
    *,
    provider_call: Callable[[str], Any],
    processors: Mapping[str, Callable[[Any], Any]],
) -> dict[str, Any]:
    """Run the deterministic three-pair schedule against one response per pair.

    The callable is an injected adapter for tests or a future authorized
    provider runner.  This function itself never imports or calls a provider.
    """

    normalized_case_ids = tuple(str(case_id) for case_id in case_ids)
    if len(normalized_case_ids) != 16 or len(set(normalized_case_ids)) != 16:
        raise ValueError("next Stage A requires exactly 16 unique development cases")
    if set(processors) != {"control", "candidate"}:
        raise ValueError("exactly control and candidate processors are required")

    trace: list[dict[str, Any]] = []
    provider_calls = 0
    for pair in EXPECTED_SCHEDULE:
        for case_id in normalized_case_ids:
            captured = CapturedProviderResponse.capture(
                f"{pair['pairId']}:{case_id}", provider_call(case_id)
            )
            provider_calls += 1
            branched = branch_captured_response(captured, {
                arm: processors[arm] for arm in pair["armOrder"]
            })
            trace.append(
                {
                    "sequence": len(trace) + 1,
                    "pairId": pair["pairId"],
                    "runNumber": pair["runNumber"],
                    "caseId": case_id,
                    "armOrder": list(pair["armOrder"]),
                    "providerCallCount": branched["providerCallCount"],
                    "branchCount": branched["branchCount"],
                    "sourceResponseDigest": branched["sourceResponseDigest"],
                    "branchInputDigests": branched["branchInputDigests"],
                    "outputs": branched["outputs"],
                }
            )
    return {
        "status": "MOCK_OR_AUTHORIZED_PAIRED_EXECUTION",
        "caseCount": len(normalized_case_ids),
        "pairCount": len(EXPECTED_SCHEDULE),
        "providerCallCount": provider_calls,
        "branchOutputCount": len(trace) * 2,
        "retryCount": 0,
        "trace": trace,
    }


def run_authorized_stage_a(
    case_ids: Sequence[str],
    *,
    provider_call: Callable[[str], Any],
    processors: Mapping[str, Callable[[Any], Any]],
    package_path: Path = DEFAULT_PACKAGE,
    commit_validator: Callable[[str], bool] = commit_is_ancestor,
) -> dict[str, Any]:
    """Validate the frozen package, then invoke the injected adapter once/case/pair."""

    validate_execution_package(package_path, commit_validator=commit_validator)
    return run_paired_schedule(
        case_ids, provider_call=provider_call, processors=processors
    )


def _read_json(path: Path) -> dict[str, Any]:
    return _load(path)


def _validate_metric_contract(path: Path = FINAL_METRIC_CONTRACT) -> dict[str, Any]:
    contract = _read_json(path)
    if contract.get("version") != "s12.metric-contract.v2":
        raise ExecutionPackageError("metric contract version is not v2")
    relation_metrics = contract.get("relationMetrics")
    if not isinstance(relation_metrics, dict) or not {
        "relationSemanticF1",
        "relationEvidenceSupport",
        "relationEvidenceExact",
    }.issubset(relation_metrics):
        raise ExecutionPackageError("metric contract does not bind semantic/evidence metrics")
    if contract.get("aggregation", {}).get("aggregateFromPerCaseRecordsOnly") is not True:
        raise ExecutionPackageError("metric contract does not require per-case aggregation")
    return contract


def _selection_labels(case: Mapping[str, Any]) -> tuple[str, ...]:
    gold = case.get("gold")
    if not isinstance(gold, dict):
        raise ExecutionPackageError("selected case has no gold object")
    relations = gold.get("relations")
    abstention = gold.get("abstention")
    if not isinstance(relations, list) or not isinstance(abstention, dict):
        raise ExecutionPackageError("selected case has incomplete gold labels")
    labels = ["all-development"]
    labels.append("relation-positive" if relations else "relation-negative")
    labels.append(
        "abstention-required"
        if abstention.get("required") is True
        else "abstention-not-required"
    )
    labels.append(f"journey:{case.get('journeyId', 'unknown')}")
    source = case.get("source")
    language = source.get("language") if isinstance(source, dict) else "unknown"
    labels.append(f"language:{language}")
    return tuple(labels)


def load_bound_development_cases() -> tuple[evaluator.LoadedDataset, tuple[dict[str, Any], ...], dict[str, int]]:
    """Load the frozen visible corpus and recalculate the selected profile."""

    selection = _read_json(FINAL_SELECTION)
    loaded = evaluator.load_dataset(
        FINAL_ATOMIC,
        FINAL_SCENARIO,
        FINAL_MANIFEST,
        allowed_splits=("development", "validation"),
    )
    if selection.get("manifestDigest") != _bound_file_digest(FINAL_MANIFEST):
        raise ExecutionPackageError("case selection does not bind the frozen manifest blob")
    selected_ids = selection.get("caseIds")
    if not isinstance(selected_ids, list) or len(selected_ids) != 16:
        raise ExecutionPackageError("case selection must contain exactly 16 case IDs")
    by_id = {str(case["caseId"]): case for case in loaded.cases}
    if len({str(case_id) for case_id in selected_ids}) != 16:
        raise ExecutionPackageError("case selection contains duplicate IDs")
    selected = tuple(by_id.get(str(case_id), {}) for case_id in selected_ids)
    if any(not case or case.get("split") != "development" for case in selected):
        raise ExecutionPackageError("case selection must remain development-only")
    profile: dict[str, int] = {
        "relation-positive": sum("relation-positive" in _selection_labels(case) for case in selected),
        "abstention-required": sum("abstention-required" in _selection_labels(case) for case in selected),
        "relation-negative": sum("relation-negative" in _selection_labels(case) for case in selected),
    }
    profile["hard-negative"] = sum(
        "relation-negative" in _selection_labels(case)
        and "abstention-not-required" in _selection_labels(case)
        for case in selected
    )
    expected = selection.get("selectionProfile")
    if not isinstance(expected, dict):
        raise ExecutionPackageError("case selection profile is missing")
    if (
        profile["relation-positive"] != int(expected.get("positiveRelationCases", -1))
        or profile["abstention-required"] != int(expected.get("abstentionRequiredCases", -1))
        or profile["hard-negative"] != int(expected.get("hardNegativeCases", -1))
    ):
        raise ExecutionPackageError("recomputed case selection profile does not match the frozen artifact")
    journeys = {label for case in selected for label in _selection_labels(case) if label.startswith("journey:")}
    languages = {label for case in selected for label in _selection_labels(case) if label.startswith("language:")}
    if journeys != {f"journey:J{index}" for index in range(1, 7)}:
        raise ExecutionPackageError("case selection does not cover J1-J6")
    if languages != {"language:en", "language:ja", "language:mixed", "language:vi"}:
        raise ExecutionPackageError("case selection does not cover en/ja/mixed/vi")
    return loaded, selected, profile


def validate_final_execution_package(
    package_path: Path = FINAL_PACKAGE,
    *,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Validate the executable package without issuing authorization."""

    package = _read_json(package_path)
    if package.get("status") != "EXECUTION_PACKAGE_FROZEN_PENDING_AUTHORIZATION":
        raise ExecutionPackageError("final execution package is not frozen")
    if package.get("providerExecutionAuthorized") is not False:
        raise ExecutionPackageError("final package must remain unauthorized")
    if package.get("heldOutInspected") is not False:
        raise ExecutionPackageError("final package permits held-out inspection")
    if package.get("executionRunnerImplemented") is not True:
        raise ExecutionPackageError("final package does not mark the runner implemented")
    if package.get("authorizationContract") != str(AUTHORIZATION_CONTRACT.relative_to(ROOT).as_posix()):
        raise ExecutionPackageError("final package authorization contract is not bound")
    required_paths = (
        "metricContract",
        "caseSelection",
        "sliceContract",
        "pricingArtifact",
        "dataset.atomic",
        "dataset.scenario",
        "dataset.manifest",
    )
    bound_digests = package.get("boundDigests")
    if not isinstance(bound_digests, dict):
        raise ExecutionPackageError("final package bound digests are missing")
    for field in required_paths:
        value: Any = package
        for component in field.split("."):
            value = value.get(component) if isinstance(value, dict) else None
        if not isinstance(value, str) or value not in bound_digests:
            raise ExecutionPackageError(f"final package path is not digest-bound: {field}")
    for binding_name, expected_path in (
        ("executionRunner", "scripts/run_sprint12_next_tool_experiment.py"),
        ("providerAdapter", "scripts/sprint12_provider_adapter.py"),
    ):
        binding = package.get(binding_name)
        if not isinstance(binding, dict) or binding.get("path") != expected_path:
            raise ExecutionPackageError(f"{binding_name} binding is missing or not allowlisted")
        if binding.get("digest") != _bound_file_digest(ROOT / expected_path):
            raise ExecutionPackageError(f"{binding_name} digest mismatch")
    if not bound_digests:
        raise ExecutionPackageError("final package has no bound artifacts")
    mismatches = {
        path: digest
        for path, digest in bound_digests.items()
        if not isinstance(path, str) or digest != _bound_file_digest(ROOT / path)
    }
    if mismatches:
        raise ExecutionPackageError("final package bound digest mismatch")
    provider_schema = package.get("providerResponseSchema")
    arms = package.get("arms")
    if provider_schema != FINAL_PROVIDER_SCHEMA or not isinstance(arms, dict):
        raise ExecutionPackageError("shared provider response schema is not bound")
    if any(
        arm.get("providerSchema") != FINAL_PROVIDER_SCHEMA
        or arm.get("branchOutputSchema") != "m3.v2"
        for arm in arms.values()
        if isinstance(arm, dict)
    ):
        raise ExecutionPackageError("control and candidate schemas are not identical")
    if output_path is not None and output_path.exists():
        raise ExecutionPackageError(f"refusing to overwrite output: {output_path}")
    _validate_metric_contract()
    return package


def _usage_from_capture(capture: ProviderCapture, envelope: RelationEvidenceEnvelopeV1) -> dict[str, int]:
    source = capture.usage
    if source is None and envelope.extraction.usage is not None:
        dumped = envelope.extraction.usage.model_dump(mode="json", by_alias=True)
        source = dumped
    if source is None:
        raise ExecutionPackageError("provider usage is missing")
    required = ("inputTokens", "promptCacheHitTokens", "promptCacheMissTokens", "outputTokens")
    if any(source.get(key) is None for key in required):
        raise ExecutionPackageError("provider usage is incomplete")
    usage = {key: int(source[key]) for key in required}
    if usage["inputTokens"] != usage["promptCacheHitTokens"] + usage["promptCacheMissTokens"]:
        raise ExecutionPackageError("provider usage cache totals do not reconcile")
    return usage


def _usage_from_capture_if_available(
    capture: ProviderCapture | None,
    envelope: RelationEvidenceEnvelopeV1 | None = None,
) -> dict[str, int] | None:
    if capture is None:
        return None
    try:
        if envelope is None:
            envelope = RelationEvidenceEnvelopeV1.model_validate(capture.payload)
        return _usage_from_capture(capture, envelope)
    except (ExecutionPackageError, ValidationError, ValueError, TypeError):
        source = capture.usage
        if source is None:
            return None
        required = ("inputTokens", "promptCacheHitTokens", "promptCacheMissTokens", "outputTokens")
        if any(source.get(key) is None for key in required):
            return None
        usage = {key: int(source[key]) for key in required}
        if usage["inputTokens"] != usage["promptCacheHitTokens"] + usage["promptCacheMissTokens"]:
            return None
        return usage


def _resolve_artifact_path(raw_path: str) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else ROOT / path


def _exact_cost_ceiling(value: Any) -> Decimal:
    try:
        ceiling = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ExecutionPackageError("authorization cost ceiling is invalid") from error
    if ceiling != Decimal("10.00"):
        raise ExecutionPackageError("authorization cost ceiling must equal preregistered $10.00")
    return ceiling


def validate_stage_a_authorization(
    package: Mapping[str, Any],
    *,
    package_path: Path,
    authorization_path: Path | None,
    output_path: Path,
) -> dict[str, Any]:
    """Require an Approval-B artifact before an injected adapter can run."""

    if authorization_path is None:
        raise ExecutionPackageError("Approval-B authorization artifact is required before provider capture")
    authorization = _read_json(authorization_path)
    if authorization.get("status") != "APPROVED_FOR_DEVELOPMENT_STAGE_A":
        raise ExecutionPackageError("stage-A authorization is not approved")
    if authorization.get("providerExecutionAuthorized") is not True:
        raise ExecutionPackageError("stage-A provider execution is not authorized")
    if authorization.get("experimentId") != package.get("experimentId"):
        raise ExecutionPackageError("authorization experiment does not match package")
    if authorization.get("heldOutInspected") is not False:
        raise ExecutionPackageError("authorization permits held-out inspection")
    if authorization.get("retryPolicy") != "none":
        raise ExecutionPackageError("authorization retry policy is not none")
    if authorization.get("executionPackage", {}).get("digest") != file_digest(package_path):
        raise ExecutionPackageError("authorization does not bind the execution package digest")
    freeze = _read_json(FINAL_FREEZE)
    freeze_binding = authorization.get("freezeRecord", {})
    if freeze_binding.get("path") != str(FINAL_FREEZE.relative_to(ROOT).as_posix()):
        raise ExecutionPackageError("authorization does not bind the final freeze record")
    if freeze_binding.get("digest") != file_digest(FINAL_FREEZE):
        raise ExecutionPackageError("authorization does not bind the final freeze digest")
    commit_sha = str(authorization.get("commitSha", ""))
    expected_commit = str(freeze.get("commitSha", ""))
    if not commit_sha or commit_sha != expected_commit:
        raise ExecutionPackageError("authorization commit does not exactly match the frozen commit")
    if not commit_is_ancestor(commit_sha):
        raise ExecutionPackageError("frozen authorization commit is not an ancestor of HEAD")
    approval_a = authorization.get("approvalA")
    if not isinstance(approval_a, dict):
        raise ExecutionPackageError("Approval-A artifact binding is required before provider capture")
    approval_a_path = approval_a.get("path")
    if not isinstance(approval_a_path, str) or not approval_a_path:
        raise ExecutionPackageError("Approval-A artifact path is missing")
    approval_a_file = _resolve_artifact_path(approval_a_path)
    if approval_a.get("digest") != file_digest(approval_a_file):
        raise ExecutionPackageError("Approval-A artifact digest mismatch")
    approval_a_artifact = _read_json(approval_a_file)
    if approval_a_artifact.get("status") != "APPROVED_FOR_ISSUANCE_ONLY":
        raise ExecutionPackageError("Approval-A artifact is not issued for preregistration only")
    if approval_a_artifact.get("providerExecutionAuthorized") is not False:
        raise ExecutionPackageError("Approval-A artifact authorizes provider execution")
    if approval_a_artifact.get("experimentId") != package.get("experimentId"):
        raise ExecutionPackageError("Approval-A experiment does not match package")
    if approval_a_artifact.get("commitSha") != expected_commit:
        raise ExecutionPackageError("Approval-A artifact does not bind the frozen commit")
    if approval_a_artifact.get("freezeDigest") != file_digest(FINAL_FREEZE):
        raise ExecutionPackageError("Approval-A artifact does not bind the final freeze")
    if approval_a_artifact.get("preregistrationDigest") != file_digest(FINAL_PREREGISTRATION):
        raise ExecutionPackageError("Approval-A artifact does not bind the final preregistration")
    try:
        expected_output_binding = str(output_path.resolve().relative_to(ROOT).as_posix())
    except ValueError:
        expected_output_binding = str(output_path.resolve())
    if authorization.get("outputPath") != expected_output_binding:
        raise ExecutionPackageError("authorization output path does not match the run output")
    _exact_cost_ceiling(authorization.get("costCeilingUsd"))
    return authorization


def _branch_payload(raw_text: str, payload: Any, arm: str) -> dict[str, Any]:
    """Return sanitized branch metadata plus an m3.v2 prediction in memory."""

    envelope = RelationEvidenceEnvelopeV1.model_validate(payload)
    if envelope.extraction.schema_version != "m3.v2":
        raise ValueError("provider response extraction schema must be m3.v2")
    if arm == "control":
        response = envelope.extraction
        materializer_failures = 0
    else:
        response = materialize_relation_evidence_envelope(raw_text, envelope)
        materializer_failures = len(envelope.extraction.relations) - len(response.relations) if response is not None else len(envelope.extraction.relations)
        if response is None:
            raise ExecutionPackageError("relation materializer failed")
    prediction = response.model_dump(mode="json", by_alias=True)
    return {
        "status": "ready",
        "branchOutputSchema": "m3.v2",
        "prediction": prediction,
        "predictionDigest": evaluator.digest(prediction),
        "materializerFailureCount": materializer_failures,
    }


def _fail_closed_result(gold: dict[str, Any], failure_class: str) -> dict[str, Any]:
    result = evaluator.score_extraction(gold, None)
    result["failureClass"] = failure_class
    return result


def _binary_f1(records: Sequence[dict[str, Any]]) -> float | str:
    positives = [record for record in records if record.get("goldAbstention") is True]
    if not positives and not any(record.get("predictedAbstention") is True for record in records):
        return "not-applicable"
    tp = sum(record.get("goldAbstention") is True and record.get("predictedAbstention") is True for record in records)
    fp = sum(record.get("goldAbstention") is not True and record.get("predictedAbstention") is True for record in records)
    fn = sum(record.get("goldAbstention") is True and record.get("predictedAbstention") is not True for record in records)
    return 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0


def _evidence_counts(score: Mapping[str, Any]) -> tuple[int, int, int, int]:
    instrumentation = score.get("relationInstrumentation")
    if not isinstance(instrumentation, dict):
        return 0, 0, 0, 0
    totals = instrumentation.get("totals", {})
    semantic_tp = int(totals.get("exactMatch", 0)) + int(totals.get("wrongSpan", 0))
    exact_tp = int(totals.get("exactMatch", 0))
    support_tp = 0
    predicted = instrumentation.get("signatures", {}).get("predicted", [])
    for item in predicted if isinstance(predicted, list) else []:
        if item.get("errorClass") not in {"exactMatch", "wrongSpan"}:
            continue
        evidence = item.get("evidenceSpan", {})
        source = item.get("sourceEndpoint", {})
        target = item.get("targetEndpoint", {})
        if (
            evidence.get("status") != "missing"
            and source.get("status") == "resolved"
            and target.get("status") == "resolved"
            and evidence.get("startOffset", 0) <= source.get("startOffset", -1)
            and evidence.get("startOffset", 0) <= target.get("startOffset", -1)
            and evidence.get("endOffset", 0) >= source.get("endOffset", 0)
            and evidence.get("endOffset", 0) >= target.get("endOffset", 0)
        ):
            support_tp += 1
    return semantic_tp, support_tp, exact_tp, int(totals.get("gold", 0))


def _metric_summary(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    scored = [record for record in records if isinstance(record.get("score"), dict)]
    relation_records = [
        record
        for record in scored
        if int(record["score"]["relationInstrumentation"]["totals"].get("gold", 0))
        or int(record["score"]["relationInstrumentation"]["totals"].get("predicted", 0))
    ]
    if not scored:
        return {"caseRuns": 0, "status": "FAIL_MISSING_OUTPUT"}
    def mean(name: str, source: Sequence[dict[str, Any]] = scored) -> float:
        return sum(float(record["score"].get(name, 0.0)) for record in source) / len(source) if source else 0.0

    def nested_mean(group: str, name: str, source: Sequence[dict[str, Any]]) -> float:
        return (
            sum(float(record["score"][group].get(name, 0.0)) for record in source) / len(source)
            if source
            else 0.0
        )
    gold = sum(int(record["score"]["relationInstrumentation"]["totals"].get("gold", 0)) for record in scored)
    predicted = sum(int(record["score"]["relationInstrumentation"]["totals"].get("predicted", 0)) for record in scored)
    semantic_tp = sum(_evidence_counts(record["score"])[0] for record in scored)
    support_tp = sum(_evidence_counts(record["score"])[1] for record in scored)
    exact_tp = sum(_evidence_counts(record["score"])[2] for record in scored)
    return {
        "status": "SCORED",
        "caseRuns": len(records),
        "relationCaseRuns": len(relation_records),
        "relationSemanticMicroF1": 2 * semantic_tp / (gold + predicted) if gold + predicted else "not-applicable",
        "relationSemanticMacroF1": sum(
            2 * _evidence_counts(record["score"])[0]
            / (_evidence_counts(record["score"])[3] + int(record["score"]["relationInstrumentation"]["totals"].get("predicted", 0)))
            for record in relation_records
            if _evidence_counts(record["score"])[3] + int(record["score"]["relationInstrumentation"]["totals"].get("predicted", 0))
        ) / len(relation_records) if relation_records else "not-applicable",
        "relationEvidenceSupport": support_tp / semantic_tp if semantic_tp else "not-applicable",
        "relationEvidenceExact": exact_tp / semantic_tp if semantic_tp else "not-applicable",
        "entityMacroF1": nested_mean("entities", "f1", scored),
        "abstentionF1": _binary_f1(records),
        "hallucinationRate": mean("hallucinationRate"),
        "denominators": {
            "allAttemptedCaseRuns": len(records),
            "relationGold": gold,
            "relationPredicted": predicted,
            "relationSemanticTruePositive": semantic_tp,
            "relationEvidenceSupportTruePositive": support_tp,
            "relationEvidenceExactTruePositive": exact_tp,
            "abstentionGold": sum(record.get("goldAbstention") is True for record in records),
        },
    }


def _slice_metrics(records: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    labels = sorted({label for record in records for label in record["labels"]})
    return {label: _metric_summary([record for record in records if label in record["labels"]]) for label in labels}


def _slice_gate_decisions(
    metrics: Mapping[str, Mapping[str, Any]],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    thresholds = contract.get("thresholds", {})
    decisions: dict[str, Any] = {}
    for label, summary in metrics.items():
        checks: dict[str, Any] = {}
        if int(summary.get("caseRuns", 0)) == 0:
            decisions[label] = {"status": "FAIL_CLOSED", "checks": {"caseRuns": False}}
            continue
        applicable = {
            "relationSemanticMicroF1": summary.get("relationSemanticMicroF1"),
            "relationSemanticMacroF1": summary.get("relationSemanticMacroF1"),
            "relationEvidenceSupport": summary.get("relationEvidenceSupport"),
            "relationEvidenceExact": summary.get("relationEvidenceExact"),
            "entityMacroF1": summary.get("entityMacroF1"),
            "abstentionF1": summary.get("abstentionF1"),
            "hallucinationRate": summary.get("hallucinationRate"),
        }
        for metric, observed in applicable.items():
            if observed == "not-applicable":
                continue
            if not isinstance(observed, (int, float)):
                checks[metric] = {"observed": observed, "pass": False}
                continue
            threshold_key = {
                "relationSemanticMicroF1": "relationSemanticMicroF1Minimum",
                "relationSemanticMacroF1": "relationSemanticMacroF1Minimum",
                "relationEvidenceSupport": "relationEvidenceSupportMinimum",
                "relationEvidenceExact": "relationEvidenceExactMinimum",
                "entityMacroF1": "entityMacroF1Minimum",
                "abstentionF1": "abstentionF1Minimum",
                "hallucinationRate": "hallucinationRateMaximum",
            }[metric]
            threshold = thresholds.get(threshold_key)
            if threshold is None:
                checks[metric] = {"observed": observed, "pass": False, "reason": "threshold-unbound"}
            elif threshold_key.endswith("Maximum"):
                checks[metric] = {"observed": observed, "threshold": threshold, "pass": observed <= float(threshold)}
            else:
                checks[metric] = {"observed": observed, "threshold": threshold, "pass": observed >= float(threshold)}
        decisions[label] = {
            "status": "PASS" if all(item.get("pass") is True for item in checks.values()) else "FAIL",
            "checks": checks,
        }
    return {
        "status": "PASS" if decisions and all(item["status"] == "PASS" for item in decisions.values()) else "FAIL",
        "slices": decisions,
    }


def _comparison_gate_decisions(
    control: Mapping[str, Mapping[str, Any]],
    candidate: Mapping[str, Mapping[str, Any]],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    minimum_delta = float(contract.get("thresholds", {}).get("nonInferiorityDeltaMinimum", -0.01))
    decisions: dict[str, Any] = {}
    metric_names = (
        "relationSemanticMicroF1",
        "relationSemanticMacroF1",
        "entityMacroF1",
        "abstentionF1",
        "hallucinationRate",
    )
    for label in sorted(set(control) | set(candidate)):
        left = control.get(label, {})
        right = candidate.get(label, {})
        checks: dict[str, Any] = {}
        for metric in metric_names:
            control_value = left.get(metric)
            candidate_value = right.get(metric)
            if not isinstance(control_value, (int, float)) or not isinstance(candidate_value, (int, float)):
                continue
            delta = float(candidate_value) - float(control_value)
            if metric == "hallucinationRate":
                passed = delta <= -minimum_delta
            else:
                passed = delta >= minimum_delta
            checks[metric] = {"control": control_value, "candidate": candidate_value, "delta": delta, "minimumDelta": minimum_delta, "pass": passed}
        decisions[label] = {"status": "PASS" if all(item["pass"] for item in checks.values()) else "FAIL", "checks": checks}
    return {
        "status": "PASS" if decisions and all(item["status"] == "PASS" for item in decisions.values()) else "FAIL",
        "slices": decisions,
    }


def run_offline_stage_a(
    *,
    provider_adapter: ProviderAdapter,
    package_path: Path = FINAL_PACKAGE,
    authorization_path: Path | None = None,
    output_path: Path,
) -> dict[str, Any]:
    """Execute Stage A only after a separate, digest-bound Approval-B artifact."""

    package = validate_final_execution_package(package_path, output_path=output_path)
    authorization = validate_stage_a_authorization(
        package,
        package_path=package_path,
        authorization_path=authorization_path,
        output_path=output_path,
    )
    _loaded, selected, profile = load_bound_development_cases()
    pricing = load_pricing_artifact(FINAL_PRICING)
    slice_contract = _read_json(FINAL_SLICE_CONTRACT)
    metric_contract = _validate_metric_contract()
    preregistration = _read_json(FINAL_PREREGISTRATION)
    cost_ceiling = _exact_cost_ceiling(authorization.get("costCeilingUsd"))
    if preregistration.get("pricingContract", {}).get("costCeilingUsd") != str(cost_ceiling):
        raise ExecutionPackageError("preregistration cost ceiling is not exactly $10.00")
    if preregistration.get("hardGates", {}).get("invalidEvidence") != 0:
        raise ExecutionPackageError("preregistration does not bind the invalid-evidence gate")
    prompt_version = str(package["promptVersion"])
    records: dict[str, list[dict[str, Any]]] = {"control": [], "candidate": []}
    trace: list[dict[str, Any]] = []
    failure_counts: dict[str, int] = {}
    provider_calls = 0
    materializer_failures = 0
    invalid_evidence_failures = 0
    priced_provider_calls = 0
    pricing_failures = 0
    retry_count = 0
    for schedule in EXPECTED_SCHEDULE:
        for case in selected:
            case_id = str(case["caseId"])
            raw_text = str(case["source"]["rawText"])
            provider_calls += 1
            capture: ProviderCapture | None = None
            try:
                capture = provider_adapter.capture(
                    case_id=case_id,
                    raw_text=raw_text,
                    prompt_version=prompt_version,
                    provider_schema=FINAL_PROVIDER_SCHEMA,
                )
                retry_count += int(getattr(capture, "retry_count", 0))
                envelope = RelationEvidenceEnvelopeV1.model_validate(capture.payload)
                usage = _usage_from_capture(capture, envelope)
                branch_outputs = {
                    arm: _branch_payload(raw_text, capture.payload, arm)
                    for arm in ("control", "candidate")
                }
                cost = cost_usd(usage, {"rates": pricing["rates"]})
                priced_provider_calls += 1
            except Exception as error:  # noqa: BLE001 - provider boundary must fail closed.
                failure_class = (
                    "schema_invalid"
                    if isinstance(error, ValidationError) or "schema" in str(error)
                    else "invalid_evidence"
                    if isinstance(error, ExecutionPackageError) and "materializer" in str(error)
                    else "provider_failure"
                )
                failure_counts[failure_class] = failure_counts.get(failure_class, 0) + 2
                invalid_evidence_failures += 1 if failure_class == "invalid_evidence" else 0
                branch_outputs = {
                    arm: {
                        "status": "failed",
                        "branchOutputSchema": "m3.v2",
                        "failureClass": failure_class,
                        "predictionDigest": None,
                        "materializerFailureCount": 0,
                    }
                    for arm in ("control", "candidate")
                }
                usage = _usage_from_capture_if_available(capture)
                if usage is None:
                    usage = {"inputTokens": 0, "promptCacheHitTokens": 0, "promptCacheMissTokens": 0, "outputTokens": 0}
                    cost = 0.0
                    pricing_failures += 1
                else:
                    cost = cost_usd(usage, {"rates": pricing["rates"]})
                    priced_provider_calls += 1
            source_digest = response_digest(capture.payload) if capture is not None else None
            branch_input_digests = (
                {arm: response_digest(capture.payload) for arm in ("control", "candidate")}
                if capture is not None
                else {}
            )
            for arm in ("control", "candidate"):
                branch = branch_outputs[arm]
                prediction = branch.get("prediction")
                gold = case["gold"]
                score = evaluator.score_extraction(gold, prediction) if isinstance(prediction, dict) else _fail_closed_result(gold, str(branch["failureClass"]))
                predicted_abstention = bool(prediction and prediction.get("abstentionReason"))
                record = {
                    "caseId": case_id,
                    "runNumber": schedule["runNumber"],
                    "pairId": schedule["pairId"],
                    "labels": _selection_labels(case),
                    "score": score,
                    "goldAbstention": bool(gold["abstention"].get("required")),
                    "predictedAbstention": predicted_abstention,
                    "failureClass": branch.get("failureClass"),
                    "materializerFailureCount": int(branch.get("materializerFailureCount", 0)),
                }
                branch_materializer_failures = int(branch.get("materializerFailureCount", 0))
                if arm == "candidate":
                    materializer_failures += branch_materializer_failures
                    invalid_evidence_failures += branch_materializer_failures
                    if branch_materializer_failures:
                        failure_counts["invalid_evidence"] = failure_counts.get("invalid_evidence", 0) + branch_materializer_failures
                records[arm].append(record)
            trace.append(
                {
                    "sequence": len(trace) + 1,
                    "pairId": schedule["pairId"],
                    "runNumber": schedule["runNumber"],
                    "caseId": case_id,
                    "armOrder": list(schedule["armOrder"]),
                    "providerCallCount": 1,
                    "branchCount": 2,
                    "sourceResponseDigest": source_digest,
                    "branchInputDigests": branch_input_digests,
                    "branchInputDigestMatch": source_digest is not None
                    and all(digest == source_digest for digest in branch_input_digests.values()),
                    "usage": usage,
                    "costUsd": cost,
                    "branches": {
                        arm: {
                            key: value
                            for key, value in branch_outputs[arm].items()
                            if key != "prediction"
                        }
                        for arm in ("control", "candidate")
                    },
                }
            )
    all_records = records["control"] + records["candidate"]
    arm_metrics = {
        arm: {"primary": _metric_summary(records[arm]), "slices": _slice_metrics(records[arm])}
        for arm in records
    }
    arm_slice_gates = {
        arm: _slice_gate_decisions(arm_metrics[arm]["slices"], slice_contract)
        for arm in records
    }
    comparison_gates = _comparison_gate_decisions(
        arm_metrics["control"]["slices"],
        arm_metrics["candidate"]["slices"],
        slice_contract,
    )
    total_cost = sum(Decimal(str(item["costUsd"])) for item in trace)
    total_cost_usd = float(total_cost)
    report = {
        "artifactVersion": "s12.s12-f-10.offline-stage-a-runner-report.v1",
        "status": "OFFLINE_RUNNER_EXECUTED",
        "experimentId": "s12-f-10",
        "caseCount": len(selected),
        "pairCount": len(EXPECTED_SCHEDULE),
        "providerCallCount": provider_calls,
        "branchOutputCount": len(all_records),
        "retryCount": retry_count,
        "caseSelectionProfile": profile,
        "metrics": arm_metrics,
        "sliceGates": arm_slice_gates,
        "comparisonGates": comparison_gates,
        "metricContract": {
            "path": str(FINAL_METRIC_CONTRACT.relative_to(ROOT).as_posix()),
            "digest": file_digest(FINAL_METRIC_CONTRACT),
            "version": metric_contract["version"],
        },
        "preregistrationDigest": file_digest(FINAL_PREREGISTRATION),
        "pricing": {
            "artifactDigest": file_digest(FINAL_PRICING),
            "totalCostUsd": total_cost_usd,
            "costCeilingUsd": str(cost_ceiling),
            "costCeilingGate": total_cost <= cost_ceiling,
            "providerCallsPriced": priced_provider_calls,
            "pricingFailures": pricing_failures,
            "cacheClasses": ["inputCacheHit", "inputCacheMiss", "output"],
        },
        "hardGates": {
            "providerCalls": provider_calls == 48,
            "branchOutputs": len(all_records) == 96,
            "retryCount": retry_count == 0,
            "sharedResponseDigest": all(item["branchInputDigestMatch"] for item in trace),
            "schemaFailures": not any(item.get("failureClass") == "schema_invalid" for item in all_records),
            "missingOutputs": not any(item["score"].get("status") == "missing-output" for item in all_records),
            "materializerFailures": materializer_failures == 0,
            "invalidEvidence": invalid_evidence_failures == 0,
            "pricing": pricing_failures == 0 and priced_provider_calls == provider_calls,
            "costCeiling": total_cost <= cost_ceiling,
            "semanticSliceGates": all(item["status"] == "PASS" for item in arm_slice_gates.values()),
            "comparisonSliceGates": comparison_gates["status"] == "PASS",
        },
        "failureCounts": failure_counts,
        "trace": trace,
        "boundDigests": package["boundDigests"],
        "rawSensitiveDataIncluded": False,
        "heldOutInspected": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise ExecutionPackageError(f"refusing to overwrite output: {output_path}")
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    raise SystemExit(
        "S12-f-10 runner is implemented but requires an explicitly bound provider adapter; no provider call is made by this CLI."
    )
