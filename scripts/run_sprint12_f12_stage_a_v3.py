#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["jsonschema>=4.23,<5"]
# ///
"""Guarded S12-f-12 runner v3 for the RM-22B measurement/lineage remediation."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from run_sprint12_f12_stage_a_v2 import (
    _arm_record,
    _capture,
    _gold_relation_candidates,
    _gold_table,
    _safe_stage1,
    _safe_stage2,
    canonical_digest,
    load,
    relative,
)
from sprint12_f12_two_step_contracts_v5 import (
    score_abstention_records,
    validate_stage1_response,
)

PACKAGE = (
    ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22b-execution-package.v3.json"
)
PREREG = (
    ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22b-issuance-draft.v3.json"
)
FREEZE = (
    ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22b-technical-freeze.v3.json"
)
REPORT_SCHEMA = (
    ROOT / "evaluation/sprint-12/harness/s12-f-12-stage-a-report.schema.v3.json"
)
OUTPUT = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v3.json"


class F12StageAV3Error(RuntimeError):
    """Raised when the v3 execution boundary is unsafe."""


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str, binary: bool = False) -> bytes | str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=not binary,
    )
    return result.stdout if binary else str(result.stdout).strip()


def _verify_exact_commit(commit_sha: object, bindings: Mapping[str, object]) -> str:
    commit = str(commit_sha or "")
    if len(commit) != 40 or any(
        character not in "0123456789abcdef" for character in commit.lower()
    ):
        raise F12StageAV3Error("freeze must bind a full exact commit SHA")
    try:
        _git("cat-file", "-e", f"{commit}^{{commit}}")
        _git("merge-base", "--is-ancestor", commit, "HEAD")
    except subprocess.CalledProcessError as error:
        raise F12StageAV3Error(
            "freeze commit is missing or is not an ancestor"
        ) from error
    for path_text, expected in bindings.items():
        try:
            blob = _git("show", f"{commit}:{path_text}", binary=True)
        except subprocess.CalledProcessError as error:
            raise F12StageAV3Error(
                f"bound path is absent at exact commit: {path_text}"
            ) from error
        actual = "sha256:" + hashlib.sha256(bytes(blob)).hexdigest()
        if actual != expected:
            raise F12StageAV3Error(f"exact-commit blob mismatch: {path_text}")
    return commit


def _verify_current_bindings(bindings: Mapping[str, object]) -> None:
    for path_text, expected in bindings.items():
        path = ROOT / str(path_text)
        if not path.is_file() or digest(path) != expected:
            raise F12StageAV3Error(f"current bound digest mismatch: {path_text}")


def _json_at_commit(commit_sha: str, path_text: str) -> dict[str, Any]:
    try:
        value = json.loads(
            bytes(_git("show", f"{commit_sha}:{path_text}", binary=True)).decode(
                "utf-8"
            )
        )
    except (subprocess.CalledProcessError, json.JSONDecodeError) as error:
        raise F12StageAV3Error(
            f"cannot load frozen blob at exact commit: {path_text}"
        ) from error
    if not isinstance(value, dict):
        raise F12StageAV3Error(f"frozen blob is not an object: {path_text}")
    return value


def _selected_cases_at_commit(commit_sha: str) -> list[dict[str, Any]]:
    corpus = _json_at_commit(
        commit_sha, "evaluation/sprint-12/corpus/v3-frozen/atomic-v3.frozen.v1.json"
    )
    selection = _json_at_commit(
        commit_sha, "evaluation/sprint-12/optimization/s12-f-10-case-selection.v2.json"
    )
    ids = list(selection.get("caseIds", []))
    cases = [case for case in corpus.get("cases", []) if case.get("caseId") in ids]
    if len(cases) != 16 or any(case.get("split") != "development" for case in cases):
        raise F12StageAV3Error(
            "exact-commit frozen selection is not the 16 development cases"
        )
    by_id = {str(case["caseId"]): case for case in cases}
    return [by_id[str(case_id)] for case_id in ids]


def _number(value: object) -> float | None:
    return (
        float(value)
        if isinstance(value, (int, float)) and not isinstance(value, bool)
        else None
    )


def _f1(true_positive: int, predicted: int, gold: int) -> float | str:
    return (
        2 * true_positive / (predicted + gold) if predicted + gold else "not-applicable"
    )


def _aggregate_arm(
    records: Sequence[Mapping[str, Any]], thresholds: Mapping[str, float]
) -> dict[str, Any]:
    entity_gold = sum(int(item["entity"]["gold"]) for item in records)
    entity_predicted = sum(int(item["entity"]["predicted"]) for item in records)
    entity_tp = sum(int(item["entity"]["truePositive"]) for item in records)
    entity_span_exact = sum(
        round(float(item["entity"]["spanExact"]) * int(item["entity"]["gold"]))
        for item in records
        if _number(item["entity"]["spanExact"]) is not None
    )
    by_type: dict[str, dict[str, int]] = {}
    for record in records:
        for entity_type, values in record["entity"]["byType"].items():
            target = by_type.setdefault(
                entity_type, {"gold": 0, "predicted": 0, "truePositive": 0}
            )
            for key in target:
                target[key] += int(values[key])
    for values in by_type.values():
        values["f1"] = _f1(values["truePositive"], values["predicted"], values["gold"])
    entity_macro = (
        sum(float(values["f1"]) for values in by_type.values()) / len(by_type)
        if by_type
        else "not-applicable"
    )
    entity = {
        "gold": entity_gold,
        "predicted": entity_predicted,
        "truePositive": entity_tp,
        "entityF1": _f1(entity_tp, entity_predicted, entity_gold),
        "entityMacroF1": entity_macro,
        "byType": by_type,
        "spanExact": entity_span_exact / entity_gold
        if entity_gold
        else "not-applicable",
        "hallucinationRate": (entity_predicted - entity_tp) / entity_predicted
        if entity_predicted
        else 0.0,
        "denominatorReconciled": entity_tp <= entity_gold
        and entity_tp <= entity_predicted,
    }
    abstention = score_abstention_records(
        [
            (bool(item["abstention"]["gold"]), bool(item["abstention"]["predicted"]))
            for item in records
        ]
    )
    semantic_counts: Counter[str] = Counter()
    evidence_counts: Counter[str] = Counter()
    predicate_counts: dict[str, dict[str, int]] = {}
    endpoint = Counter()
    semantic_gold = semantic_predicted = semantic_tp = 0
    predicate_correct = direction_correct = pair_count = 0
    for record in records:
        relation = record["relation"]
        semantic = relation["semantic"]
        semantic_counts.update(
            {key: int(value) for key, value in semantic["counts"].items()}
        )
        evidence_counts.update(
            {key: int(value) for key, value in relation["evidence"]["counts"].items()}
        )
        semantic_gold += int(semantic["gold"])
        semantic_predicted += int(semantic["predicted"])
        semantic_tp += int(semantic["truePositive"])
        pairs = sum(
            int(semantic["counts"][key])
            for key in (
                "exactMatch",
                "wrongPredicate",
                "reversedEndpoint",
                "wrongEndpoint",
            )
        )
        pair_count += pairs
        predicate_correct += (
            round(float(semantic["predicateAccuracy"]) * pairs)
            if _number(semantic["predicateAccuracy"]) is not None
            else 0
        )
        direction_correct += int(semantic["counts"]["exactMatch"])
        endpoint.update(
            {
                key: int(value)
                for key, value in relation["endpointResolution"].items()
                if key in {"resolved", "wrong", "missing", "denominator"}
            }
        )
        for predicate, values in semantic["byPredicate"].items():
            target = predicate_counts.setdefault(
                predicate, {"gold": 0, "predicted": 0, "truePositive": 0}
            )
            for key in target:
                target[key] += int(values[key])
    for values in predicate_counts.values():
        values["f1"] = _f1(values["truePositive"], values["predicted"], values["gold"])
    relation_semantic = {
        "counts": dict(semantic_counts),
        "gold": semantic_gold,
        "predicted": semantic_predicted,
        "truePositive": semantic_tp,
        "microF1": _f1(semantic_tp, semantic_predicted, semantic_gold),
        "macroF1": sum(float(values["f1"]) for values in predicate_counts.values())
        / len(predicate_counts)
        if predicate_counts
        else "not-applicable",
        "byPredicate": predicate_counts,
        "predicateAccuracy": predicate_correct / pair_count
        if pair_count
        else "not-applicable",
        "endpointDirectionAccuracy": direction_correct / predicate_correct
        if predicate_correct
        else "not-applicable",
        "missingEndpointRate": endpoint["missing"] / endpoint["denominator"]
        if endpoint["denominator"]
        else "not-applicable",
        "reversedEndpointRate": semantic_counts["reversedEndpoint"] / semantic_gold
        if semantic_gold
        else "not-applicable",
        "hallucinationRate": (semantic_predicted - semantic_tp) / semantic_predicted
        if semantic_predicted
        else 0.0,
        "goldReconciled": semantic_counts["exactMatch"]
        + semantic_counts["wrongPredicate"]
        + semantic_counts["reversedEndpoint"]
        + semantic_counts["wrongEndpoint"]
        + semantic_counts["missingRelation"]
        == semantic_gold,
        "predictedReconciled": semantic_counts["exactMatch"]
        + semantic_counts["wrongPredicate"]
        + semantic_counts["reversedEndpoint"]
        + semantic_counts["wrongEndpoint"]
        + semantic_counts["extraRelation"]
        == semantic_predicted,
    }
    evidence_applicable = sum(
        evidence_counts[key]
        for key in ("exact", "supportedNonExact", "unsupported", "missing")
    )
    relation_evidence = {
        "counts": dict(evidence_counts),
        "semanticTruePositiveDenominator": semantic_tp,
        "applicable": evidence_applicable,
        "reconciled": evidence_applicable == semantic_tp,
        "supportRate": (evidence_counts["exact"] + evidence_counts["supportedNonExact"])
        / semantic_tp
        if semantic_tp
        else "not-applicable",
        "exactRate": evidence_counts["exact"] / semantic_tp
        if semantic_tp
        else "not-applicable",
    }
    relation = {
        "semantic": relation_semantic,
        "endpointResolution": {
            **dict(endpoint),
            "reconciled": all(
                bool(item["relation"]["endpointResolution"]["reconciled"])
                for item in records
            ),
        },
        "evidence": relation_evidence,
        "invalidEvidenceCount": sum(
            int(item.get("invalidEvidenceCount", 0)) for item in records
        ),
        "endpointContractFailure": sum(
            int(item.get("endpointContractFailure", 0)) for item in records
        ),
        "configurationMismatch": sum(
            int(item.get("configurationMismatch", 0)) for item in records
        ),
    }
    failures: list[str] = []
    checks = {
        "entityMacroF1": (
            entity["entityMacroF1"],
            thresholds["entityMacroF1Min"],
            "min",
        ),
        "entitySpanExact": (
            entity["spanExact"],
            thresholds["entitySpanExactMin"],
            "min",
        ),
        "entityHallucinationRate": (
            entity["hallucinationRate"],
            thresholds["entityHallucinationRateMax"],
            "max",
        ),
        "abstentionPrecision": (
            abstention["precision"],
            thresholds["abstentionPrecisionMin"],
            "min",
        ),
        "abstentionRecall": (
            abstention["recall"],
            thresholds["abstentionRecallMin"],
            "min",
        ),
        "abstentionF1": (abstention["f1"], thresholds["abstentionF1Min"], "min"),
        "relationSemanticMicroF1": (
            relation_semantic["microF1"],
            thresholds["relationSemanticMicroF1Min"],
            "min",
        ),
        "relationSemanticMacroF1": (
            relation_semantic["macroF1"],
            thresholds["relationSemanticMacroF1Min"],
            "min",
        ),
        "predicateAccuracy": (
            relation_semantic["predicateAccuracy"],
            thresholds["predicateAccuracyMin"],
            "min",
        ),
        "endpointDirectionAccuracy": (
            relation_semantic["endpointDirectionAccuracy"],
            thresholds["endpointDirectionAccuracyMin"],
            "min",
        ),
        "missingEndpointRate": (
            relation_semantic["missingEndpointRate"],
            thresholds["missingEndpointRateMax"],
            "max",
        ),
        "reversedEndpointRate": (
            relation_semantic["reversedEndpointRate"],
            thresholds["reversedEndpointRateMax"],
            "max",
        ),
        "relationEvidenceSupport": (
            relation_evidence["supportRate"],
            thresholds["relationEvidenceSupportMin"],
            "min",
        ),
        "relationEvidenceExact": (
            relation_evidence["exactRate"],
            thresholds["relationEvidenceExactMin"],
            "min",
        ),
        "relationHallucinationRate": (
            relation_semantic["hallucinationRate"],
            thresholds["relationHallucinationRateMax"],
            "max",
        ),
    }
    for name, (value, bound, mode) in checks.items():
        numeric = _number(value)
        if (
            numeric is None
            or (mode == "min" and numeric < bound)
            or (mode == "max" and numeric > bound)
        ):
            failures.append(name)
    return {
        "caseRuns": len(records),
        "goldRelationInstances": semantic_gold,
        "goldAbstentionInstances": sum(
            int(item["abstention"]["gold"]) for item in records
        ),
        "entity": entity,
        "abstention": abstention,
        "relation": relation,
        "thresholdsPass": not failures,
        "thresholdFailures": failures,
    }


def _fingerprint(package: Mapping[str, Any]) -> str:
    return canonical_digest(
        {
            "runtime": package["runtimeConfiguration"]["digest"],
            "prompt": package["prompt"]["digest"],
            "stage1": package["stageSchemas"]["stage1"]["digest"],
            "stage2": package["stageSchemas"]["stage2"]["digest"],
            "model": package["runtimeConfiguration"].get("model", "deepseek-v4-flash"),
        }
    )


def _slice_groups(
    records: Sequence[Mapping[str, Any]],
) -> list[tuple[str, str, list[Mapping[str, Any]], str]]:
    groups: list[tuple[str, str, list[Mapping[str, Any]], str]] = [
        ("all-development", "all-development", list(records), "cases")
    ]
    groups.append(
        (
            "relation-positive",
            "relation-positive",
            [r for r in records if int(r["goldRelationCount"]) > 0],
            "relations",
        )
    )
    groups.append(
        (
            "relation-negative",
            "relation-negative",
            [r for r in records if int(r["goldRelationCount"]) == 0],
            "relations",
        )
    )
    groups.append(
        (
            "abstention-required",
            "abstention-required",
            [r for r in records if bool(r["goldAbstentionRequired"])],
            "cases",
        )
    )
    groups.append(
        (
            "abstention-not-required",
            "abstention-not-required",
            [r for r in records if not bool(r["goldAbstentionRequired"])],
            "cases",
        )
    )
    for journey in ("J1", "J2", "J3", "J4", "J5", "J6"):
        groups.append(
            (
                "journey",
                journey,
                [r for r in records if r["journeyId"] == journey],
                "cases",
            )
        )
    for language in ("en", "ja", "mixed", "vi"):
        groups.append(
            (
                "language",
                language,
                [r for r in records if r["language"] == language],
                "cases",
            )
        )
    return groups


def _slice_denominator(records: Sequence[Mapping[str, Any]], kind: str) -> int:
    return (
        sum(int(item["goldRelationCount"]) for item in records)
        if kind == "relations"
        else len(records)
    )


def _validate_report_schema(report: Mapping[str, Any]) -> None:
    schema = load(REPORT_SCHEMA)
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        required = set(schema["required"])
        if set(report) != required:
            raise F12StageAV3Error(
                "JSON Schema validator unavailable and report top-level shape is not closed"
            )
        labels = [item.get("label") for item in report["sliceRecords"]]
        required_labels = [
            "all-development",
            "relation-positive",
            "relation-negative",
            "abstention-required",
            "abstention-not-required",
            "J1",
            "J2",
            "J3",
            "J4",
            "J5",
            "J6",
            "en",
            "ja",
            "mixed",
            "vi",
        ]
        if len(report["caseRecords"]) != 48 or labels != required_labels:
            raise F12StageAV3Error("report cardinalities violate the bound JSON Schema")
        return
    errors = sorted(
        Draft202012Validator(schema).iter_errors(report),
        key=lambda error: list(error.path),
    )
    if errors:
        location = ".".join(str(item) for item in errors[0].path) or "<root>"
        raise F12StageAV3Error(
            f"report JSON Schema validation failed at {location}: {errors[0].message}"
        )


def validate_preparation(
    package_path: Path = PACKAGE, *, output_path: Path | None = None
) -> dict[str, Any]:
    package = load(package_path)
    prereg = load(PREREG)
    freeze = load(FREEZE)
    if package.get("status") != "EXECUTION_PACKAGE_PREPARED_PENDING_RM23B_OWNER_REVIEW":
        raise F12StageAV3Error("package is not pending RM-23B review")
    if package.get("commitSha") != freeze.get("commitSha") or not package.get(
        "commitSha"
    ):
        raise F12StageAV3Error("package and freeze must bind the same exact commit")
    bindings = package.get("boundDigests")
    if not isinstance(bindings, Mapping) or not bindings:
        raise F12StageAV3Error("package binding set is empty")
    current_paths = package.get("currentExecutionPaths")
    if not isinstance(current_paths, list) or set(current_paths) - set(bindings):
        raise F12StageAV3Error("current execution path set is incomplete")
    _verify_current_bindings({str(path): bindings[path] for path in current_paths})
    preregistration = package.get("preregistration")
    if (
        not isinstance(preregistration, Mapping)
        or preregistration.get("path") != relative(PREREG)
        or preregistration.get("digest") != digest(PREREG)
    ):
        raise F12StageAV3Error("package preregistration binding mismatch")
    if package.get("freezeRecord") != relative(FREEZE):
        raise F12StageAV3Error("package freeze path mismatch")
    exact_paths = package.get("exactCommitBoundPaths")
    if not isinstance(exact_paths, list) or set(exact_paths) - set(bindings):
        raise F12StageAV3Error("exact commit path set is incomplete")
    _verify_exact_commit(
        package["commitSha"], {str(path): bindings[path] for path in exact_paths}
    )
    if (
        package.get("providerCalls") != 144
        or package.get("relationBranchOutputs") != 96
    ):
        raise F12StageAV3Error("provider schedule is not exact")
    for artifact in (package, prereg, freeze):
        if artifact.get("providerExecutionAuthorized") is not False:
            raise F12StageAV3Error("execution governance is open")
    if freeze.get("executionPackageDigest") != digest(package_path) or freeze.get(
        "preregistrationDigest"
    ) != digest(PREREG):
        raise F12StageAV3Error("v3 lineage digest mismatch")
    if output_path is not None and output_path.exists():
        raise F12StageAV3Error("refusing to overwrite final report")
    return package


def validate_authorization(
    authorization_path: Path,
    *,
    package_path: Path = PACKAGE,
    freeze_path: Path = FREEZE,
    output_path: Path = OUTPUT,
) -> dict[str, Any]:
    authorization = load(authorization_path)
    package = load(package_path)
    freeze = load(freeze_path)
    if (
        authorization.get("status") != "APPROVED_FOR_DEVELOPMENT_STAGE_A"
        or authorization.get("providerExecutionAuthorized") is not True
    ):
        raise F12StageAV3Error("exact Stage A authorization is required")
    expected_commit = package.get("commitSha")
    if (
        authorization.get("commitSha") != expected_commit
        or freeze.get("commitSha") != expected_commit
    ):
        raise F12StageAV3Error("authorization does not bind the exact freeze commit")
    if authorization.get("executionPackage", {}).get("digest") != digest(
        package_path
    ) or authorization.get("freezeRecord", {}).get("digest") != digest(freeze_path):
        raise F12StageAV3Error("authorization lineage digest mismatch")
    bindings = package.get("boundDigests", {})
    exact_paths = package.get("exactCommitBoundPaths", [])
    _verify_exact_commit(
        expected_commit, {str(path): bindings[path] for path in exact_paths}
    )
    if (
        authorization.get("providerCalls") != 144
        or authorization.get("retryPolicy") != "none"
        or Decimal(str(authorization.get("costCeilingUsd"))) != Decimal("10.00")
    ):
        raise F12StageAV3Error("authorization schedule or ceiling is not exact")
    if authorization.get("outputPath") != relative(output_path) or output_path.exists():
        raise F12StageAV3Error("authorization output path is unsafe")
    return authorization


def run_stage_a(
    *,
    provider_adapter: Any,
    authorization_path: Path | None,
    output_path: Path = OUTPUT,
    package_path: Path = PACKAGE,
) -> dict[str, Any]:
    package = validate_preparation(package_path, output_path=output_path)
    if authorization_path is None:
        raise F12StageAV3Error(
            "separate exact-commit authorization is required before provider capture"
        )
    validate_authorization(
        authorization_path,
        package_path=package_path,
        freeze_path=FREEZE,
        output_path=output_path,
    )
    if not hasattr(provider_adapter, "capture_stage"):
        raise F12StageAV3Error("concrete f12 provider adapter is required")
    prereg = load(PREREG)
    thresholds = {
        key: float(value)
        for key, value in prereg["approvedThresholds"].items()
        if isinstance(value, (int, float))
    }
    config_fingerprint = _fingerprint(package)
    cases = _selected_cases_at_commit(str(package["commitSha"]))
    accounting: Counter[str] = Counter(
        {"totalCostMicros": 0, "retryCount": 0, "pricingFailure": 0}
    )
    case_records: list[dict[str, Any]] = []
    schema_invalid = missing_output = 0
    for run_number in range(1, 4):
        for case in cases:
            case_id = str(case["caseId"])
            run_id = f"run-{run_number}"
            source = str(case["source"]["rawText"])
            stage1, transport1 = _capture(
                provider_adapter,
                stage="stage1",
                case_id=case_id,
                run_id=run_id,
                raw_text=source,
                arm="predicted-entities",
                candidate_table=None,
                accounting=accounting,
            )
            predicted_entities, predicted_abstention, failure1 = _safe_stage1(
                stage1, len(source)
            )
            table = [
                {
                    "candidateId": item.candidate_id,
                    "type": item.entity_type,
                    "startOffset": item.start,
                    "endOffset": item.end,
                    "confidence": float(item.confidence),
                }
                for item in predicted_entities
            ]
            stage2_predicted, transport2 = _capture(
                provider_adapter,
                stage="stage2",
                case_id=case_id,
                run_id=run_id,
                raw_text=source,
                arm="predicted-entities",
                candidate_table=table,
                accounting=accounting,
            )
            predicted_relations, predicted_relation_abstention, failure2 = _safe_stage2(
                stage2_predicted, predicted_entities, len(source)
            )
            gold_table = _gold_table(case)
            gold_abstention = {
                "required": not bool(gold_table),
                "reason": "gold-empty-control" if not gold_table else None,
            }
            gold_candidates, _ = validate_stage1_response(
                {
                    "schemaVersion": "s12-f-12.stage1.entity-envelope.v2",
                    "entities": gold_table,
                    "abstention": gold_abstention,
                },
                source_length=len(source),
            )
            stage2_gold, transport3 = _capture(
                provider_adapter,
                stage="stage2",
                case_id=case_id,
                run_id=run_id,
                raw_text=source,
                arm="gold-entities",
                candidate_table=gold_table,
                accounting=accounting,
            )
            gold_relations_predicted, gold_relation_abstention, failure3 = _safe_stage2(
                stage2_gold, gold_candidates, len(source)
            )
            failures = (
                failure1,
                failure2,
                failure3,
                transport1,
                transport2,
                transport3,
            )
            schema_invalid += sum(item == "schema_invalid" for item in failures)
            missing_output += sum(item == "missing_output" for item in failures)
            gold_control = _arm_record(
                case,
                stage1=None,
                stage1_failure=None,
                predicted_entities=gold_candidates,
                stage2=None,
                stage2_failure=None,
                relations=_gold_relation_candidates(case),
                abstention=bool(case["gold"]["abstention"]["required"]),
                gold_candidates=gold_table,
                is_gold_arm=True,
            )
            arms = {
                "predicted-entities": _arm_record(
                    case,
                    stage1=stage1,
                    stage1_failure=failure1 or transport1,
                    predicted_entities=predicted_entities,
                    stage2=stage2_predicted,
                    stage2_failure=failure2 or transport2,
                    relations=predicted_relations,
                    abstention=predicted_abstention or predicted_relation_abstention,
                    gold_candidates=gold_table,
                    is_gold_arm=False,
                ),
                "gold-entities": _arm_record(
                    case,
                    stage1=None,
                    stage1_failure=None,
                    predicted_entities=gold_candidates,
                    stage2=stage2_gold,
                    stage2_failure=failure3 or transport3,
                    relations=gold_relations_predicted,
                    abstention=gold_relation_abstention,
                    gold_candidates=gold_table,
                    is_gold_arm=True,
                ),
                "gold-relations": gold_control,
            }
            for arm in arms.values():
                arm["configurationFingerprint"] = config_fingerprint
                relation = arm["relation"]
                arm["invalidEvidenceCount"] = (
                    int(relation["evidence"]["counts"].get("unsupported", 0))
                    + int(relation["evidence"]["counts"].get("missing", 0))
                )
                arm["endpointContractFailure"] = (
                    0 if relation["endpointResolution"]["reconciled"] else 1
                )
                arm["configurationMismatch"] = 0
            case_records.append(
                {
                    "caseId": case_id,
                    "runId": run_number,
                    "journeyId": str(case["journeyId"]),
                    "language": str(case["source"]["language"]),
                    "goldRelationCount": len(case["gold"]["relations"]),
                    "goldAbstentionRequired": bool(
                        case["gold"]["abstention"]["required"]
                    ),
                    "arms": arms,
                }
            )
    if accounting["attempts"] != 144:
        raise F12StageAV3Error("runner did not attempt exactly 144 calls")
    gold_relation_instances = sum(
        int(record["goldRelationCount"]) for record in case_records
    )
    gold_abstention_instances = sum(
        int(record["goldAbstentionRequired"]) for record in case_records
    )
    aggregate_arms = {
        arm: _aggregate_arm(
            [record["arms"][arm] for record in case_records], thresholds
        )
        for arm in ("predicted-entities", "gold-entities", "gold-relations")
    }
    slice_records: list[dict[str, Any]] = []
    for dimension, label, selected, kind in _slice_groups(case_records):
        slice_arms = {
            arm: _aggregate_arm(
                [record["arms"][arm] for record in selected], thresholds
            )
            for arm in ("predicted-entities", "gold-entities", "gold-relations")
        }
        slice_records.append(
            {
                "dimension": dimension,
                "label": label,
                "denominator": _slice_denominator(selected, kind),
                "metrics": {
                    "arms": slice_arms,
                    "gate": {
                        arm: slice_arms[arm]["thresholdsPass"]
                        for arm in ("predicted-entities", "gold-entities")
                    },
                },
            }
        )
    hard_gates = {
        "schemaInvalid": schema_invalid,
        "invalidEvidence": sum(
            aggregate_arms[arm]["relation"]["invalidEvidenceCount"]
            for arm in ("predicted-entities", "gold-entities")
        ),
        "missingOutput": missing_output,
        "endpointContractFailure": sum(
            aggregate_arms[arm]["relation"]["endpointContractFailure"]
            for arm in ("predicted-entities", "gold-entities")
        ),
        "sharedConfigurationMismatch": len(
            {
                record["arms"][arm]["configurationFingerprint"]
                for record in case_records
                for arm in ("predicted-entities", "gold-entities")
            }
        )
        - 1,
        "retryCount": accounting["retryCount"],
        "pricingFailure": accounting["pricingFailure"],
        "rawSensitiveDataIncluded": False,
        "heldOutInspected": False,
    }
    integrity = (
        aggregate_arms["gold-relations"]["relation"]["semantic"]["microF1"] == 1.0
        and aggregate_arms["gold-relations"]["relation"]["invalidEvidenceCount"] == 0
    )
    slice_pass = all(
        all(record["metrics"]["gate"].values()) for record in slice_records
    )
    cost = Decimal(accounting["totalCostMicros"]) / Decimal(1_000_000)
    thresholds_pass = all(
        aggregate_arms[arm]["thresholdsPass"]
        for arm in ("predicted-entities", "gold-entities")
    )
    hard_pass = (
        all(
            value == 0
            for key, value in hard_gates.items()
            if key not in {"rawSensitiveDataIncluded", "heldOutInspected"}
        )
        and not hard_gates["rawSensitiveDataIncluded"]
        and not hard_gates["heldOutInspected"]
    )
    decision_pass = (
        hard_pass
        and cost <= Decimal("10.00")
        and thresholds_pass
        and integrity
        and slice_pass
    )
    report: dict[str, Any] = {
        "artifactVersion": "s12-f-12.stage-a-report.v3",
        "experimentId": "s12-f-12",
        "custody": {
            "rawSourceTextStored": False,
            "rawProviderPayloadStored": False,
            "heldOutAccess": False,
            "overwrite": False,
            "retryPolicy": "none",
        },
        "configuration": {
            "commitSha": package["commitSha"],
            "runtimeDigest": package["runtimeConfiguration"]["digest"],
            "promptDigest": package["prompt"]["digest"],
            "stage1SchemaDigest": package["stageSchemas"]["stage1"]["digest"],
            "stage2SchemaDigest": package["stageSchemas"]["stage2"]["digest"],
            "model": "deepseek-v4-flash",
            "sampling": {"temperature": 0.0, "topP": 1.0},
            "timeoutSeconds": 60.0,
            "maxOutputTokens": 4096,
            "thresholds": thresholds,
        },
        "accounting": {
            "providerCallsAttempted": accounting["attempts"],
            "responsesReceived": accounting["responses"],
            "schemaValidResponses": accounting["responses"] - schema_invalid,
            "usageValidResponses": accounting["usageValid"],
            "pricedCalls": accounting["priced"],
            "retryCount": accounting["retryCount"],
            "pricingFailureCount": accounting["pricingFailure"],
            "totalCostUsd": f"{cost:.8f}",
            "costCeilingUsd": "10.00",
            "denominators": {
                "caseRuns": len(case_records),
                "relationInstances": gold_relation_instances,
                "abstentionInstances": gold_abstention_instances,
            },
            "failureClasses": {
                "schemaInvalid": schema_invalid,
                "missingOutput": missing_output,
                "endpointContractFailure": hard_gates["endpointContractFailure"],
                "sharedConfigurationMismatch": hard_gates[
                    "sharedConfigurationMismatch"
                ],
            },
            "callSchedule": {
                "stage1PredictedEntities": 48,
                "stage2PredictedEntities": 48,
                "stage2GoldEntities": 48,
            },
        },
        "metrics": {
            "arms": aggregate_arms,
            "hardGates": hard_gates,
            "thresholds": thresholds,
            "goldRelationsIntegrityScore": 1.0 if integrity else 0.0,
            "goldRelationsMaterializerFailures": aggregate_arms["gold-relations"][
                "relation"
            ]["invalidEvidenceCount"],
            "sliceGatesPass": slice_pass,
        },
        "caseRecords": case_records,
        "sliceRecords": slice_records,
        "decision": {
            "status": "COMPLETED" if decision_pass else "COMPLETED_REJECTED_HARD_GATE",
            "hardGatesPass": hard_pass,
            "thresholdsPass": thresholds_pass,
            "sliceGatesPass": slice_pass,
            "goldRelationsIntegrityPass": integrity,
            "costCeilingPass": cost <= Decimal("10.00"),
            "failedGates": [
                key for key, value in hard_gates.items() if value not in (0, False)
            ]
            + (["thresholds"] if not thresholds_pass else [])
            + (["sliceGates"] if not slice_pass else [])
            + (["goldRelationsIntegrity"] if not integrity else [])
            + (["costCeiling"] if cost > Decimal("10.00") else []),
            "outputPath": relative(output_path),
        },
    }
    _validate_report_schema(report)
    with tempfile.TemporaryDirectory(
        prefix="s12-f-12-stage-a-", dir=output_path.parent
    ) as staging:
        staging_path = Path(staging) / "report.staging.json"
        staging_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if output_path.exists():
            raise F12StageAV3Error("refusing to overwrite final report")
        output_path.write_bytes(staging_path.read_bytes())
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Guarded S12-f-12 Stage A runner v3")
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
