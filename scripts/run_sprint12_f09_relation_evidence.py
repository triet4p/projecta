#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""Run the single-use, paired S12-f-09 Stage A experiment.

This runner is deliberately separate from the historical f08 runner.  It
binds the frozen v3 development subset, calls the provider exactly once per
case/run, and applies the server-owned relation-evidence materializer only to
the candidate arm.  Reports contain no raw source text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import sprint12_evaluator as evaluator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from projecta_api.extraction.contracts import EvidenceSpan, ExtractionResponse
from projecta_api.extraction.relation_evidence import (
    RelationEvidenceRequest,
    materialize_relation_evidence,
)
from projecta_api.extraction.normalize import normalize_extraction as _normalize_extraction
from run_sprint12_contract_candidate import run_candidate
from sprint12_pricing import bind_pricing, cost_usd, file_digest, merged_environment


OPT = ROOT / "evaluation/sprint-12/optimization"
FROZEN = ROOT / "evaluation/sprint-12/corpus/v3-frozen"
PREREGISTRATION = OPT / "s12-f-09-relation-evidence-preregistration.v1.json"
AUTHORIZATION = OPT / "s12-f-09-authorization.v1.json"
PRICING = OPT / "s12-f-08-pricing-deepseek-v4-flash.v1.json"
ATOMIC = FROZEN / "atomic-v3.frozen.v1.json"
SCENARIO = FROZEN / "scenario-v3.frozen.v1.json"
MANIFEST = FROZEN / "atomic-manifest.v1.json"
OUTPUT_PATH = OPT / "s12-f-09-relation-evidence-stage-a.v1.json"
RUNS_DIR = OPT / "s12-f-09-relation-evidence-stage-a"

EXPECTED_SCHEDULE = (
    {"pairId": "pair-1", "runNumber": 1, "armOrder": ("control", "candidate")},
    {"pairId": "pair-2", "runNumber": 2, "armOrder": ("candidate", "control")},
    {"pairId": "pair-3", "runNumber": 3, "armOrder": ("control", "candidate")},
)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def commit_is_ancestor(commit_sha: str) -> bool:
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


def _load_runtime_environment() -> dict[str, str]:
    environment = merged_environment()
    missing = evaluator.missing_runtime_configuration(environment)
    if missing:
        raise SystemExit("missing provider configuration: " + ", ".join(missing))
    for key, value in environment.items():
        os.environ.setdefault(key, value)
    return environment


def execution_package_digests() -> dict[str, str]:
    return {
        "evaluatorCode": file_digest(ROOT / "scripts/sprint12_evaluator.py"),
        "promptImplementation": file_digest(
            ROOT / "apps/api/src/projecta_api/extraction/prompt.py"
        ),
        "relationEvidenceMaterializer": file_digest(
            ROOT / "apps/api/src/projecta_api/extraction/relation_evidence.py"
        ),
        "pricingArtifact": file_digest(PRICING),
        "datasetManifest": file_digest(MANIFEST),
    }


def _materialize_candidate_relations(
    raw_text: str, response: ExtractionResponse
) -> ExtractionResponse:
    """Replace model-authored relation evidence with server-owned evidence."""

    entity_spans = {
        str(entity.candidate_id): entity.evidence
        for entity in response.entities
        if entity.candidate_id is not None
    }
    materialized = []
    for relation in response.relations:
        source_span = entity_spans.get(relation.source_entity_id)
        target_span = entity_spans.get(relation.target_entity_id)
        if source_span is None or target_span is None:
            continue
        evidence = materialize_relation_evidence(
            raw_text,
            RelationEvidenceRequest(
                predicate=relation.predicate,
                source_entity_id=relation.source_entity_id,
                target_entity_id=relation.target_entity_id,
                source_span=source_span,
                target_span=target_span,
            ),
        )
        if evidence is None:
            continue
        materialized.append(relation.model_copy(update={"evidence": evidence}))
    return response.model_copy(update={"relations": materialized})


def _run_arm(
    *,
    case_ids: tuple[str, ...],
    prompt_variant: str,
    arm: str,
) -> dict[str, Any]:
    """Run one provider-backed arm, with candidate-only evidence materialization."""

    original_normalizer = _normalize_extraction
    import projecta_api.extraction.normalize as normalize_module

    if arm == "candidate":
        def candidate_normalizer(
            raw_text: str,
            response: ExtractionResponse,
            bounded_entities: list[dict[str, str]],
        ) -> ExtractionResponse:
            return original_normalizer(
                raw_text,
                _materialize_candidate_relations(raw_text, response),
                bounded_entities,
            )

        normalize_module.normalize_extraction = candidate_normalizer
    try:
        return run_candidate(
            atomic_path=ATOMIC,
            scenario_path=SCENARIO,
            manifest_path=MANIFEST,
            prompt_variant=prompt_variant,
            case_ids=case_ids,
            sampling_configuration=None,
            candidate_kind=f"s12-f-09-{arm}-relation-evidence",
        )
    finally:
        normalize_module.normalize_extraction = original_normalizer


def _evidence_metrics(case_result: Mapping[str, Any]) -> dict[str, float | int | str]:
    instrumentation = case_result.get("relationInstrumentation")
    if not isinstance(instrumentation, dict) or instrumentation.get("status") != "scored":
        return {
            "relationSemanticF1": 0.0,
            "relationEvidenceSupport": 0.0,
            "relationEvidenceExact": 0.0,
            "semanticGold": 0,
            "semanticPredicted": 0,
            "semanticTruePositive": 0,
            "evidenceSupportTruePositive": 0,
            "evidenceExactTruePositive": 0,
            "status": "not-available",
        }
    totals = instrumentation.get("totals", {})
    gold = int(totals.get("gold", 0))
    predicted = int(totals.get("predicted", 0))
    semantic_tp = int(totals.get("exactMatch", 0)) + int(totals.get("wrongSpan", 0))
    exact_tp = int(totals.get("exactMatch", 0))
    records = instrumentation.get("signatures", {}).get("predicted", [])
    support_tp = 0
    for record in records if isinstance(records, list) else []:
        if record.get("errorClass") not in {"exactMatch", "wrongSpan"}:
            continue
        evidence = record.get("evidenceSpan", {})
        source = record.get("sourceEndpoint", {})
        target = record.get("targetEndpoint", {})
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
    semantic_f1 = 2 * semantic_tp / (gold + predicted) if gold + predicted else 1.0
    return {
        "relationSemanticF1": semantic_f1,
        "relationEvidenceSupport": support_tp / semantic_tp if semantic_tp else "not-applicable",
        "relationEvidenceExact": exact_tp / semantic_tp if semantic_tp else "not-applicable",
        "semanticGold": gold,
        "semanticPredicted": predicted,
        "semanticTruePositive": semantic_tp,
        "evidenceSupportTruePositive": support_tp,
        "evidenceExactTruePositive": exact_tp,
        "status": "scored",
    }


def _case_gate_metrics(result: Mapping[str, Any]) -> dict[str, float | int | str]:
    evidence = _evidence_metrics(result)
    return {
        **evidence,
        "entityMacroF1": float(result.get("entities", {}).get("f1", 0.0)),
        "abstentionAccuracy": float(result.get("abstentionAccuracy", 0.0)),
        "hallucinationRate": float(result.get("hallucinationRate", 0.0)),
        "status": str(result.get("status", "missing-output")),
    }


def _slice_aggregates(
    runs: list[dict[str, Any]], manifest: Mapping[str, Any]
) -> dict[str, dict[str, float | int | str]]:
    slices = {
        str(item["caseId"]): str(item.get("slice", "unknown"))
        for item in manifest.get("atomicCases", [])
        if isinstance(item, dict) and "caseId" in item
    }
    grouped: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        for case_id, result in run["perCase"].items():
            grouped.setdefault(slices.get(case_id, "unknown"), []).append(
                _case_gate_metrics(result)
            )
    output: dict[str, dict[str, float | int | str]] = {}
    for slice_name, records in sorted(grouped.items()):
        output[slice_name] = {
            "caseRuns": len(records),
            "relationSemanticF1": statistics.fmean(
                float(item["relationSemanticF1"]) for item in records
            ),
            "entityMacroF1": statistics.fmean(float(item["entityMacroF1"]) for item in records),
            "abstentionAccuracy": statistics.fmean(float(item["abstentionAccuracy"]) for item in records),
            "hallucinationRate": statistics.fmean(float(item["hallucinationRate"]) for item in records),
            "relationEvidenceSupport": statistics.fmean(
                float(item["relationEvidenceSupport"])
                for item in records
                if isinstance(item["relationEvidenceSupport"], (int, float))
            )
            if any(isinstance(item["relationEvidenceSupport"], (int, float)) for item in records)
            else "not-applicable",
            "relationEvidenceExact": statistics.fmean(
                float(item["relationEvidenceExact"])
                for item in records
                if isinstance(item["relationEvidenceExact"], (int, float))
            )
            if any(isinstance(item["relationEvidenceExact"], (int, float)) for item in records)
            else "not-applicable",
        }
    return output


def _primary_metrics(runs: list[dict[str, Any]]) -> dict[str, Any]:
    records = [
        _case_gate_metrics(case)
        for run in runs
        for case in run["perCase"].values()
    ]
    result: dict[str, Any] = {
        name: statistics.fmean(float(item[name]) for item in records)
        for name in (
            "entityMacroF1",
            "abstentionAccuracy",
            "hallucinationRate",
            "relationSemanticF1",
        )
    }
    for name in ("relationEvidenceSupport", "relationEvidenceExact"):
        values = [float(item[name]) for item in records if isinstance(item[name], (int, float))]
        result[name] = statistics.fmean(values) if values else "not-applicable"
    result["caseRuns"] = len(records)
    result["relationSemanticGold"] = sum(int(item["semanticGold"]) for item in records)
    result["relationSemanticPredicted"] = sum(int(item["semanticPredicted"]) for item in records)
    result["relationSemanticTruePositive"] = sum(int(item["semanticTruePositive"]) for item in records)
    result["relationEvidenceSupportTruePositive"] = sum(
        int(item["evidenceSupportTruePositive"]) for item in records
    )
    result["relationEvidenceExactTruePositive"] = sum(
        int(item["evidenceExactTruePositive"]) for item in records
    )
    gold = int(result["relationSemanticGold"])
    predicted = int(result["relationSemanticPredicted"])
    tp = int(result["relationSemanticTruePositive"])
    result["relationSemanticMicroF1"] = 2 * tp / (gold + predicted) if gold + predicted else 1.0
    return result


def _hard_gate(runs: list[dict[str, Any]]) -> bool:
    return all(not run["failureCounts"] and int(run["missingOutputCount"]) == 0 for run in runs)


def _supersession_false_positives(runs: list[dict[str, Any]], case_ids: tuple[str, ...]) -> int:
    manifest = load(MANIFEST)
    target = {
        str(item["caseId"])
        for item in manifest["atomicCases"]
        if item.get("caseId") in case_ids and item.get("slice") == "contradiction-or-supersession"
    }
    return sum(
        1
        for run in runs
        for case_id in target
        if run["perCase"].get(case_id, {}).get("status") == "scored"
        and float(run["perCase"][case_id].get("abstentionAccuracy", 1.0)) == 0.0
    )


def _bind_authorized_execution() -> tuple[dict[str, Any], tuple[str, ...], dict[str, Any], dict[str, str]]:
    environment = _load_runtime_environment()
    prereg = load(PREREGISTRATION)
    authorization = load(AUTHORIZATION)
    if prereg.get("status") != "PREREGISTERED_NOT_EXECUTED":
        raise SystemExit("f09 preregistration is not immutable/not-executed")
    if authorization.get("status") != "APPROVED_FOR_DEVELOPMENT_STAGE_A":
        raise SystemExit("f09 Stage A authorization is missing")
    if authorization.get("providerExecutionAuthorized") is not True:
        raise SystemExit("f09 provider execution is not authorized")
    if authorization.get("heldOutInspected") is not False:
        raise SystemExit("f09 authorization permits held-out inspection")
    if authorization.get("preregistration", {}).get("digest") != file_digest(PREREGISTRATION):
        raise SystemExit("f09 authorization does not bind preregistration digest")
    package = authorization.get("executionPackage", {})
    if package.get("digests") != execution_package_digests():
        raise SystemExit("f09 execution package digest mismatch")
    runner = authorization.get("runner", {})
    if runner.get("digest") != file_digest(Path(__file__)):
        raise SystemExit("f09 runner digest mismatch")
    commit_sha = str(authorization.get("commitSha", ""))
    if not commit_sha or not commit_is_ancestor(commit_sha):
        raise SystemExit("f09 authorization commit is not an ancestor of HEAD")
    pricing = bind_pricing(PRICING, environment, expected_model="deepseek-v4-flash")
    case_ids = tuple(str(value) for value in prereg["stageA"]["caseIds"])
    if len(case_ids) != 48 or len(set(case_ids)) != 48:
        raise SystemExit("f09 Stage A must contain exactly 48 unique cases")
    loaded = evaluator.load_dataset(
        ATOMIC, SCENARIO, MANIFEST, allowed_splits=("development", "validation")
    )
    selected = {
        str(case["caseId"]): case
        for case in loaded.cases
        if case.get("split") == "development" and case.get("caseId") in case_ids
    }
    if set(case_ids) != set(selected) or len(selected) != 48:
        raise SystemExit("f09 authorization must bind exactly 48 development cases")
    return prereg, case_ids, pricing, environment


def _write_run(path: Path, report: dict[str, Any], pricing: dict[str, Any]) -> dict[str, Any]:
    if path.exists():
        raise SystemExit(f"refusing to overwrite run report: {path}")
    records = report.get("operationalRecords", [])
    for record in records:
        record["costUsd"] = cost_usd(record, pricing)
    report["operational"] = evaluator.score_operational(records)
    report["operational"]["pricing"] = {
        "status": "BOUND",
        "artifactDigest": pricing["artifactDigest"],
        "currency": pricing["currency"],
        "unit": pricing["unit"],
        "sourceUrl": pricing["sourceUrl"],
        "retrievedAt": pricing["retrievedAt"],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "reportPath": path.relative_to(ROOT).as_posix(),
        "reportDigest": file_digest(path),
        "runId": path.stem.removesuffix(".report.v1"),
        "status": report["status"],
        "failureCount": report["failureCount"],
        "missingOutputCount": report["missingOutputCount"],
        "failureCounts": report["operational"]["failureCounts"],
        "usage": report["operational"]["usage"],
        "costUsd": report["operational"]["costUsd"],
        "configuration": report["configuration"],
        "digests": report["digests"],
        "perCase": report["metrics"]["perCase"],
    }


def execute_stage_a(
    prereg: dict[str, Any],
    case_ids: tuple[str, ...],
    pricing: dict[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    variants: dict[str, list[dict[str, Any]]] = {"control": [], "candidate": []}
    trace: list[dict[str, Any]] = []
    prompt_variant = str(prereg["control"]["configuration"]["promptVersion"])
    for pair in EXPECTED_SCHEDULE:
        for arm_position, arm in enumerate(pair["armOrder"], start=1):
            path = RUNS_DIR / f"{pair['pairId']}-{arm_position:02d}-{arm}.report.v1.json"
            raw = _run_arm(case_ids=case_ids, prompt_variant=prompt_variant, arm=arm)
            summary = _write_run(path, raw, pricing)
            summary.update({"pairId": pair["pairId"], "runNumber": pair["runNumber"], "arm": arm, "armPosition": arm_position})
            variants[arm].append(summary)
            trace.append({"sequence": len(trace) + 1, "pairId": pair["pairId"], "runNumber": pair["runNumber"], "arm": arm, "armPosition": arm_position, "reportPath": summary["reportPath"]})
    return variants, trace


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    if OUTPUT_PATH.exists():
        raise SystemExit(f"refusing to overwrite Stage A artifact: {OUTPUT_PATH}")
    prereg, case_ids, pricing, _environment = _bind_authorized_execution()
    variants, trace = execute_stage_a(prereg, case_ids, pricing)
    control = _primary_metrics(variants["control"])
    candidate = _primary_metrics(variants["candidate"])
    manifest = load(MANIFEST)
    supersession_fp = _supersession_false_positives(variants["candidate"], case_ids)
    gates = {
        "candidateHardGate": _hard_gate(variants["candidate"]),
        "controlHardGate": _hard_gate(variants["control"]),
        "candidateRelationSemanticF1": candidate["relationSemanticMicroF1"] >= 0.80,
        "candidateRelationEvidenceSupport": candidate["relationEvidenceSupport"] != "not-applicable" and candidate["relationEvidenceSupport"] >= 0.85,
        "candidateRelationEvidenceExact": candidate["relationEvidenceExact"] != "not-applicable" and candidate["relationEvidenceExact"] >= 0.85,
        "candidateEntityMacroF1": candidate["entityMacroF1"] >= 0.85,
        "candidateAbstentionAccuracy": candidate["abstentionAccuracy"] >= 0.90,
        "candidateHallucinationRate": candidate["hallucinationRate"] <= 0.05,
        "supersessionFalsePositiveZero": supersession_fp == 0,
    }
    output = {
        "artifactVersion": "s12.s12-f-09.relation-evidence-stage-a.v1",
        "experimentId": "s12-f-09",
        "status": "STAGE_A_COMPLETED",
        "decision": "STAGE_A_ELIGIBLE_FOR_STAGE_B" if all(gates.values()) else "STAGE_A_NOT_ELIGIBLE_FOR_STAGE_B",
        "stageATechnicalPass": all(gates.values()),
        "stageBAuthorized": False,
        "caseCount": len(case_ids),
        "executionCount": len(trace) * len(case_ids),
        "caseIds": list(case_ids),
        "invocationTrace": trace,
        "control": {"primaryMetrics": control, "hardGatesPass": _hard_gate(variants["control"]), "sliceMetrics": _slice_aggregates(variants["control"], manifest), "runs": variants["control"]},
        "candidate": {"primaryMetrics": candidate, "hardGatesPass": _hard_gate(variants["candidate"]), "supersessionFalsePositiveCount": supersession_fp, "sliceMetrics": _slice_aggregates(variants["candidate"], manifest), "runs": variants["candidate"]},
        "gates": gates,
        "accounting": {"costAccountingStatus": "BOUND", "pricingArtifactDigest": pricing["artifactDigest"], "totalCostUsd": sum(float(run["costUsd"]) for arm in variants.values() for run in arm), "costCeilingUsd": 10.0, "withinCostCeiling": sum(float(run["costUsd"]) for arm in variants.values() for run in arm) <= 10.0},
        "measurement": {"semanticIdentityExcludesEvidenceSpan": True, "perCaseAndPerSliceDenominatorsPresent": True, "bucketReconciliationPass": all(run["perCase"][case_id].get("relationInstrumentation", {}).get("reconciliation", {}).get("pass", False) for arm in variants.values() for run in arm for case_id in run["perCase"])},
        "digests": execution_package_digests(),
        "authorizationDigest": file_digest(AUTHORIZATION),
        "heldOutInspected": False,
        "rawSensitiveDataIncluded": False,
        "retryCount": 0,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": output["status"], "decision": output["decision"], "executionCount": output["executionCount"], "totalCostUsd": output["accounting"]["totalCostUsd"]}, indent=2))


if __name__ == "__main__":
    main()
