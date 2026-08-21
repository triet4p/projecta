#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""Executable, guarded S12-f-12 Stage A runner v2.

The runner performs one stage-1 call and two independent stage-2 calls per
case/run. It never retries, never stores raw source/provider payloads, writes
the final report once, and refuses to overwrite an existing report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
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

from sprint12_f12_two_step_contracts_v5 import (
    ContractViolation,
    EntityCandidate,
    RelationCandidate,
    materialize_evidence_context,
    score_abstention_records,
    score_entity_candidates,
    score_relations,
    validate_stage1_response,
    validate_stage2_response,
)
from sprint12_provider_adapter import ProviderAdapterError, ProviderCapture

PACKAGE = (
    ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22a-execution-package.v2.json"
)
PREREG = (
    ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22a-issuance-draft.v2.json"
)
FREEZE = (
    ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22a-technical-freeze.v2.json"
)
ATOMIC = ROOT / "evaluation/sprint-12/corpus/v3-frozen/atomic-v3.frozen.v1.json"
SELECTION = ROOT / "evaluation/sprint-12/optimization/s12-f-10-case-selection.v2.json"
OUTPUT = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v2.json"


class F12StageAV2Error(RuntimeError):
    """Raised when the v2 execution boundary is unsafe."""


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise F12StageAV2Error(f"cannot load artifact: {path}") from error
    if not isinstance(value, dict):
        raise F12StageAV2Error(f"artifact is not an object: {path}")
    return value


def validate_preparation(
    package_path: Path = PACKAGE,
    *,
    preregistration_path: Path = PREREG,
    freeze_path: Path = FREEZE,
    output_path: Path | None = None,
) -> dict[str, Any]:
    package = load(package_path)
    prereg = load(preregistration_path)
    freeze = load(freeze_path)
    if package.get("status") != "EXECUTION_PACKAGE_PREPARED_PENDING_RM23A_OWNER_REVIEW":
        raise F12StageAV2Error("package is not pending RM-23A review")
    if package.get("experimentId") != "s12-f-12":
        raise F12StageAV2Error("package experiment mismatch")
    if package.get("executionRunnerImplemented") is not True:
        raise F12StageAV2Error("package does not bind an implemented runner")
    for key in (
        "providerExecutionAuthorized",
        "heldOutInspected",
        "stageBAuthorized",
        "candidateSelectionAuthorized",
        "promotionAuthorized",
    ):
        if package.get(key) is not False:
            raise F12StageAV2Error(f"package governance is open: {key}")
    if (
        package.get("providerCalls") != 144
        or package.get("stage1ProviderCalls") != 48
        or package.get("stage2ProviderCalls") != 96
    ):
        raise F12StageAV2Error("provider schedule is not 144 calls")
    if (
        package.get("retryPolicy") != "none"
        or package.get("outputOverwrite") is not False
    ):
        raise F12StageAV2Error("retry/overwrite contract is not closed")
    binding = package.get("preregistration")
    if (
        not isinstance(binding, Mapping)
        or binding.get("path") != relative(preregistration_path)
        or binding.get("digest") != digest(preregistration_path)
    ):
        raise F12StageAV2Error("preregistration binding mismatch")
    if package.get("freezeRecord") != relative(freeze_path):
        raise F12StageAV2Error("freeze path mismatch")
    if freeze.get("executionPackageDigest") != digest(package_path) or freeze.get(
        "preregistrationDigest"
    ) != digest(preregistration_path):
        raise F12StageAV2Error("freeze lineage mismatch")
    if (
        freeze.get("commitSha") is not None
        or freeze.get("providerExecutionAuthorized") is not False
    ):
        raise F12StageAV2Error("freeze is not preparation-only")
    if (
        prereg.get("preregistrationIssued") is not False
        or prereg.get("providerExecutionAuthorized") is not False
    ):
        raise F12StageAV2Error("preregistration is not issuance-only")
    bindings = package.get("boundDigests")
    if not isinstance(bindings, Mapping) or not bindings:
        raise F12StageAV2Error("package binding set is empty")
    for path_text, expected in bindings.items():
        path = ROOT / str(path_text)
        if not path.is_file() or digest(path) != expected:
            raise F12StageAV2Error(f"bound digest mismatch: {path_text}")
    if output_path is not None and output_path.exists():
        raise F12StageAV2Error("refusing to overwrite final report")
    return package


def validate_authorization(
    authorization_path: Path,
    *,
    package_path: Path,
    freeze_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    authorization = load(authorization_path)
    if (
        authorization.get("status") != "APPROVED_FOR_DEVELOPMENT_STAGE_A"
        or authorization.get("providerExecutionAuthorized") is not True
    ):
        raise F12StageAV2Error("exact Stage A authorization is required")
    if (
        authorization.get("experimentId") != "s12-f-12"
        or authorization.get("providerCalls") != 144
        or authorization.get("retryPolicy") != "none"
    ):
        raise F12StageAV2Error("authorization schedule is not exact")
    if authorization.get("executionPackage", {}).get("digest") != digest(package_path):
        raise F12StageAV2Error("authorization package digest mismatch")
    if authorization.get("freezeRecord", {}).get("digest") != digest(freeze_path):
        raise F12StageAV2Error("authorization freeze digest mismatch")
    if authorization.get("outputPath") != relative(output_path):
        raise F12StageAV2Error("authorization output path mismatch")
    if Decimal(str(authorization.get("costCeilingUsd"))) != Decimal("10.00"):
        raise F12StageAV2Error("authorization cost ceiling is not $10.00")
    if output_path.exists():
        raise F12StageAV2Error("refusing to overwrite final report")
    return authorization


def _selected_cases() -> list[dict[str, Any]]:
    corpus = load(ATOMIC)
    selection = load(SELECTION)
    ids = list(selection.get("caseIds", []))
    cases = [case for case in corpus.get("cases", []) if case.get("caseId") in ids]
    if len(cases) != 16 or any(case.get("split") != "development" for case in cases):
        raise F12StageAV2Error("selected cases are not the 16 frozen development cases")
    by_id = {str(case["caseId"]): case for case in cases}
    return [by_id[str(case_id)] for case_id in ids]


def _gold_table(case: Mapping[str, Any]) -> list[dict[str, object]]:
    table: list[dict[str, object]] = []
    for entity in case["gold"]["entities"]:
        span = entity["span"]
        table.append(
            {
                "candidateId": f"gold-{entity['id']}",
                "type": entity["type"],
                "startOffset": span["start"],
                "endOffset": span["end"],
                "confidence": 1.0,
            }
        )
    return table


def _entity_map(
    candidates: Sequence[EntityCandidate],
) -> dict[str, tuple[int, int, str]]:
    return {
        item.candidate_id: (item.start, item.end, item.entity_type)
        for item in candidates
    }


def _gold_entity_map(case: Mapping[str, Any]) -> dict[str, tuple[int, int, str]]:
    return {
        str(item["id"]): (
            int(item["span"]["start"]),
            int(item["span"]["end"]),
            str(item["type"]),
        )
        for item in case["gold"]["entities"]
    }


def _normalize_gold_relations(case: Mapping[str, Any]) -> list[dict[str, object]]:
    source = str(case["source"]["rawText"])
    result: list[dict[str, object]] = []
    for relation in case["gold"]["relations"]:
        predicate = str(relation["predicate"])
        item = dict(relation)
        item["triggerDigest"] = (
            "sha256:" + hashlib.sha256(predicate.encode("utf-8")).hexdigest()
        )
        item["startOffset"] = int(relation["span"]["start"])
        item["endOffset"] = int(relation["span"]["end"])
        if predicate not in source:
            item["triggerDigest"] = "sha256:missing"
        result.append(item)
    return result


def _contexts(case: Mapping[str, Any]) -> dict[tuple[str, str, str], Any]:
    source = str(case["source"]["rawText"])
    contexts: dict[tuple[str, str, str], Any] = {}
    for relation in _normalize_gold_relations(case):
        predicate = str(relation["predicate"])
        start = source.find(predicate)
        if start < 0:
            continue
        span = relation["span"]
        context = materialize_evidence_context(
            source,
            [(start, start + len(predicate))],
            sentence=(0, len(source)),
            clause=(int(span["start"]), int(span["end"])),
        )
        key = (
            predicate,
            str(relation["sourceEntityId"]),
            str(relation["targetEntityId"]),
        )
        contexts[key] = context
        contexts[
            (
                predicate,
                f"gold-{relation['sourceEntityId']}",
                f"gold-{relation['targetEntityId']}",
            )
        ] = context
    return contexts


def _gold_relation_candidates(case: Mapping[str, Any]) -> tuple[RelationCandidate, ...]:
    source = str(case["source"]["rawText"])
    candidates: list[RelationCandidate] = []
    for relation in case["gold"]["relations"]:
        predicate = str(relation["predicate"])
        start = source.find(predicate)
        candidates.append(
            RelationCandidate(
                predicate,
                f"gold-{relation['sourceEntityId']}",
                f"gold-{relation['targetEntityId']}",
                Decimal(1),
                int(relation["span"]["start"]),
                int(relation["span"]["end"]),
                predicate if start >= 0 else None,
            )
        )
    return tuple(candidates)


def _price(usage: Mapping[str, int]) -> Decimal:
    return (
        Decimal(usage["promptCacheHitTokens"]) * Decimal("0.0028")
        + Decimal(usage["promptCacheMissTokens"]) * Decimal("0.14")
        + Decimal(usage["outputTokens"]) * Decimal("0.28")
    ) / Decimal(1_000_000)


def _capture(
    adapter: Any,
    *,
    stage: str,
    case_id: str,
    run_id: str,
    raw_text: str,
    arm: str,
    candidate_table: Sequence[Mapping[str, object]] | None,
    accounting: Counter[str],
) -> tuple[ProviderCapture | None, str | None]:
    accounting["attempts"] += 1
    try:
        capture = adapter.capture_stage(
            stage=stage,
            case_id=case_id,
            run_id=run_id,
            raw_text=raw_text,
            arm=arm,
            candidate_table=candidate_table,
        )
    except Exception as error:  # noqa: BLE001 - classify every provider failure fail-closed
        if isinstance(error, ContractViolation):
            return None, "schema_invalid"
        if isinstance(error, ProviderAdapterError):
            return None, "provider_or_usage_failure"
        return None, "runner_failure"
    if capture.retry_count != 0:
        accounting["retryCount"] += capture.retry_count
        return capture, "retry_detected"
    accounting["responses"] += 1
    if capture.usage is None:
        accounting["pricingFailure"] += 1
        return capture, "usage_missing"
    accounting["usageValid"] += 1
    try:
        accounting["totalCostMicros"] += int(
            (_price(capture.usage) * Decimal(1_000_000)).to_integral_value()
        )
        accounting["priced"] += 1
    except (KeyError, ArithmeticError):
        accounting["pricingFailure"] += 1
        return capture, "pricing_failure"
    return capture, None


def _safe_stage1(
    capture: ProviderCapture | None, source_length: int
) -> tuple[tuple[EntityCandidate, ...], bool, str | None]:
    if capture is None:
        return (), True, "missing_output"
    try:
        candidates, abstention = validate_stage1_response(
            capture.payload, source_length=source_length
        )
        return candidates, abstention, None
    except ContractViolation:
        return (), True, "schema_invalid"


def _safe_stage2(
    capture: ProviderCapture | None,
    table: Sequence[EntityCandidate],
    source_length: int,
) -> tuple[tuple[RelationCandidate, ...], bool, str | None]:
    if capture is None:
        return (), True, "missing_output"
    try:
        relations, abstention = validate_stage2_response(
            capture.payload, candidate_table=table, source_length=source_length
        )
        return relations, abstention, None
    except ContractViolation:
        return (), True, "schema_invalid"


def _arm_record(
    case: Mapping[str, Any],
    *,
    stage1: ProviderCapture | None,
    stage1_failure: str | None,
    predicted_entities: Sequence[EntityCandidate],
    stage2: ProviderCapture | None,
    stage2_failure: str | None,
    relations: Sequence[RelationCandidate],
    abstention: bool,
    gold_candidates: Sequence[Mapping[str, object]],
    is_gold_arm: bool,
) -> dict[str, Any]:
    gold_entities = _gold_entity_map(case)
    gold_relations = _normalize_gold_relations(case)
    predicted_map = _entity_map(predicted_entities)
    if is_gold_arm:
        relation_map = {f"gold-{key}": value for key, value in gold_entities.items()}
    else:
        relation_map = predicted_map
    relation_metrics = score_relations(
        gold_relations,
        relations,
        gold_entities=gold_entities,
        predicted_entities=relation_map,
        evidence_contexts=_contexts(case),
    )
    gold_entity_rows = [
        {
            "type": item["type"],
            "startOffset": item["span"]["start"],
            "endOffset": item["span"]["end"],
        }
        for item in case["gold"]["entities"]
    ]
    return {
        "stage1": {
            "responseReceived": stage1 is not None,
            "schemaValid": stage1_failure is None and stage1 is not None,
            "failureClass": stage1_failure,
            "responseDigest": canonical_digest(stage1.payload)
            if stage1 is not None
            else None,
        },
        "stage2": {
            "responseReceived": stage2 is not None,
            "schemaValid": stage2_failure is None and stage2 is not None,
            "failureClass": stage2_failure,
            "responseDigest": canonical_digest(stage2.payload)
            if stage2 is not None
            else None,
            "candidateTableDigest": canonical_digest(
                list(gold_candidates)
                if is_gold_arm
                else [
                    {
                        "candidateId": item.candidate_id,
                        "type": item.entity_type,
                        "startOffset": item.start,
                        "endOffset": item.end,
                        "confidence": float(item.confidence),
                    }
                    for item in predicted_entities
                ]
            ),
        },
        "entity": score_entity_candidates(gold_entity_rows, predicted_entities),
        "abstention": {
            "gold": bool(case["gold"]["abstention"]["required"]),
            "predicted": bool(abstention),
        },
        "relation": relation_metrics,
    }


def _aggregate(
    case_records: Sequence[Mapping[str, Any]],
    *,
    gold_relations: int,
    gold_abstentions: int,
) -> dict[str, Any]:
    arms: dict[str, dict[str, Any]] = {}
    for arm in ("predicted-entities", "gold-entities", "gold-relations"):
        records = [record["arms"][arm] for record in case_records]
        abstention_pairs = [
            (item["abstention"]["gold"], item["abstention"]["predicted"])
            for item in records
        ]
        arms[arm] = {
            "caseRuns": len(records),
            "goldRelationInstances": gold_relations,
            "goldAbstentionInstances": gold_abstentions,
            "entity": {
                "records": len(records),
                "denominatorReconciled": all(
                    item["entity"]["denominatorReconciled"] for item in records
                ),
            },
            "abstention": score_abstention_records(abstention_pairs),
            "relation": {
                "records": len(records),
                "semanticRecordsReconciled": all(
                    item["relation"]["semantic"]["goldReconciled"]
                    and item["relation"]["semantic"]["predictedReconciled"]
                    for item in records
                ),
                "evidenceRecordsReconciled": all(
                    item["relation"]["evidence"]["reconciled"] for item in records
                ),
            },
        }
    return arms


def run_stage_a(
    *,
    provider_adapter: Any,
    authorization_path: Path | None,
    output_path: Path = OUTPUT,
    package_path: Path = PACKAGE,
) -> dict[str, Any]:
    package = validate_preparation(package_path, output_path=output_path)
    if authorization_path is None:
        raise F12StageAV2Error(
            "separate Stage A authorization is required before provider capture"
        )
    validate_authorization(
        authorization_path,
        package_path=package_path,
        freeze_path=FREEZE,
        output_path=output_path,
    )
    if not hasattr(provider_adapter, "capture_stage"):
        raise F12StageAV2Error("concrete f12 v2 provider adapter is required")
    cases = _selected_cases()
    accounting: Counter[str] = Counter()
    accounting["totalCostMicros"] = 0
    accounting["retryCount"] = 0
    accounting["pricingFailure"] = 0
    case_records: list[dict[str, Any]] = []
    schema_invalid = 0
    missing_output = 0
    for run_number in range(1, 4):
        for case in cases:
            case_id = str(case["caseId"])
            run_id = f"run-{run_number}"
            source = str(case["source"]["rawText"])
            predicted_capture, predicted_transport_failure = _capture(
                provider_adapter,
                stage="stage1",
                case_id=case_id,
                run_id=run_id,
                raw_text=source,
                arm="predicted-entities",
                candidate_table=None,
                accounting=accounting,
            )
            predicted_entities, predicted_abstention, predicted_schema_failure = (
                _safe_stage1(predicted_capture, len(source))
            )
            predicted_table = [
                {
                    "candidateId": item.candidate_id,
                    "type": item.entity_type,
                    "startOffset": item.start,
                    "endOffset": item.end,
                    "confidence": float(item.confidence),
                }
                for item in predicted_entities
            ]
            predicted_relation_capture, predicted_relation_transport_failure = _capture(
                provider_adapter,
                stage="stage2",
                case_id=case_id,
                run_id=run_id,
                raw_text=source,
                arm="predicted-entities",
                candidate_table=predicted_table,
                accounting=accounting,
            )
            (
                predicted_relations,
                predicted_relation_abstention,
                predicted_relation_schema_failure,
            ) = _safe_stage2(
                predicted_relation_capture, predicted_entities, len(source)
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
            gold_relation_capture, gold_relation_transport_failure = _capture(
                provider_adapter,
                stage="stage2",
                case_id=case_id,
                run_id=run_id,
                raw_text=source,
                arm="gold-entities",
                candidate_table=gold_table,
                accounting=accounting,
            )
            (
                gold_relations_predicted,
                gold_relation_abstention,
                gold_relation_schema_failure,
            ) = _safe_stage2(gold_relation_capture, gold_candidates, len(source))
            if (
                predicted_schema_failure
                or predicted_relation_schema_failure
                or gold_relation_schema_failure
                or predicted_transport_failure
                or predicted_relation_transport_failure
                or gold_relation_transport_failure
            ):
                schema_invalid += sum(
                    bool(value)
                    for value in (
                        predicted_schema_failure,
                        predicted_relation_schema_failure,
                        gold_relation_schema_failure,
                    )
                )
            if (
                predicted_capture is None
                or predicted_relation_capture is None
                or gold_relation_capture is None
            ):
                missing_output += 1
            gold_relation_candidates = _gold_relation_candidates(case)
            gold_arm_record = _arm_record(
                case,
                stage1=None,
                stage1_failure=None,
                predicted_entities=gold_candidates,
                stage2=None,
                stage2_failure=None,
                relations=gold_relation_candidates,
                abstention=bool(case["gold"]["abstention"]["required"]),
                gold_candidates=gold_table,
                is_gold_arm=True,
            )
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
                    "arms": {
                        "predicted-entities": _arm_record(
                            case,
                            stage1=predicted_capture,
                            stage1_failure=predicted_schema_failure
                            or predicted_transport_failure,
                            predicted_entities=predicted_entities,
                            stage2=predicted_relation_capture,
                            stage2_failure=predicted_relation_schema_failure
                            or predicted_relation_transport_failure,
                            relations=predicted_relations,
                            abstention=predicted_abstention
                            or predicted_relation_abstention,
                            gold_candidates=gold_table,
                            is_gold_arm=False,
                        ),
                        "gold-entities": _arm_record(
                            case,
                            stage1=None,
                            stage1_failure=None,
                            predicted_entities=gold_candidates,
                            stage2=gold_relation_capture,
                            stage2_failure=gold_relation_schema_failure
                            or gold_relation_transport_failure,
                            relations=gold_relations_predicted,
                            abstention=gold_relation_abstention,
                            gold_candidates=gold_table,
                            is_gold_arm=True,
                        ),
                        "gold-relations": gold_arm_record,
                    },
                }
            )
    if accounting["attempts"] != 144:
        raise F12StageAV2Error(
            f"runner attempted {accounting['attempts']} calls instead of 144"
        )
    total_cost = Decimal(accounting["totalCostMicros"]) / Decimal(1_000_000)
    gold_relation_instances = (
        sum(int(record["goldRelationCount"]) for record in case_records) * 3
    )
    gold_abstention_instances = (
        sum(int(record["goldAbstentionRequired"]) for record in case_records) * 3
    )
    report: dict[str, Any] = {
        "artifactVersion": "s12-f-12.stage-a-report.v2",
        "experimentId": "s12-f-12",
        "custody": {
            "rawSourceTextStored": False,
            "rawProviderPayloadStored": False,
            "heldOutAccess": False,
            "overwrite": False,
            "retryPolicy": "none",
        },
        "configuration": {
            "runtimeDigest": package["runtimeConfiguration"]["digest"],
            "promptDigest": package["prompt"]["digest"],
            "stage1SchemaDigest": package["stageSchemas"]["stage1"]["digest"],
            "stage2SchemaDigest": package["stageSchemas"]["stage2"]["digest"],
            "model": "deepseek-v4-flash",
            "sampling": {"temperature": 0.0, "topP": 1.0},
            "timeoutSeconds": 60.0,
            "maxOutputTokens": 4096,
        },
        "accounting": {
            "providerCallsAttempted": accounting["attempts"],
            "responsesReceived": accounting["responses"],
            "schemaValidResponses": accounting["responses"] - schema_invalid,
            "usageValidResponses": accounting["usageValid"],
            "pricedCalls": accounting["priced"],
            "retryCount": accounting["retryCount"],
            "pricingFailureCount": accounting["pricingFailure"],
            "totalCostUsd": f"{total_cost:.8f}",
            "costCeilingUsd": "10.00",
            "callSchedule": {
                "stage1PredictedEntities": 48,
                "stage2PredictedEntities": 48,
                "stage2GoldEntities": 48,
            },
        },
        "metrics": {
            "arms": _aggregate(
                case_records,
                gold_relations=gold_relation_instances,
                gold_abstentions=gold_abstention_instances,
            ),
            "hardGates": {
                "schemaInvalid": schema_invalid,
                "invalidEvidence": 0,
                "missingOutput": missing_output,
                "retryCount": accounting["retryCount"],
                "pricingFailure": accounting["pricingFailure"],
                "rawSensitiveDataIncluded": False,
                "heldOutInspected": False,
            },
        },
        "caseRecords": case_records,
        "sliceRecords": [
            {
                "dimension": "all-development",
                "label": "all-development",
                "denominator": 48,
                "metrics": {"caseRuns": 48},
            },
            {
                "dimension": "relation-positive",
                "label": "relation-positive",
                "denominator": sum(
                    record["goldRelationCount"] > 0 for record in case_records
                ),
                "metrics": {"goldRelationInstances": gold_relation_instances},
            },
            {
                "dimension": "abstention-required",
                "label": "abstention-required",
                "denominator": sum(
                    record["goldAbstentionRequired"] for record in case_records
                ),
                "metrics": {"goldAbstentionInstances": gold_abstention_instances},
            },
        ],
        "decision": {
            "status": "COMPLETED"
            if schema_invalid == 0
            and missing_output == 0
            and accounting["retryCount"] == 0
            and accounting["pricingFailure"] == 0
            else "COMPLETED_REJECTED_HARD_GATE",
            "hardGatesPass": schema_invalid == 0
            and missing_output == 0
            and accounting["retryCount"] == 0
            and accounting["pricingFailure"] == 0
            and total_cost <= Decimal("10.00"),
            "outputPath": relative(output_path),
        },
    }
    with tempfile.TemporaryDirectory(
        prefix="s12-f-12-stage-a-", dir=output_path.parent
    ) as staging:
        staging_path = Path(staging) / "report.staging.json"
        staging_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if output_path.exists():
            raise F12StageAV2Error("refusing to overwrite final report")
        output_path.write_bytes(staging_path.read_bytes())
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Guarded S12-f-12 Stage A runner v2")
    parser.add_argument("--authorization", required=True, type=Path)
    parser.add_argument("--output", default=OUTPUT, type=Path)
    parser.add_argument("--package", default=PACKAGE, type=Path)
    args = parser.parse_args(argv)
    from sprint12_f12_provider_adapter_v2 import F12ProviderAdapterV2

    output = args.output.resolve()
    package = args.package.resolve()
    validate_preparation(package, output_path=output)
    adapter = F12ProviderAdapterV2.from_environment()
    run_stage_a(
        provider_adapter=adapter,
        authorization_path=args.authorization.resolve(),
        output_path=output,
        package_path=package,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
