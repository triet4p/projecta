#!/usr/bin/env -S uv run --script
"""Offline root-cause analysis for the rejected S12-f-11 Stage A report."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "evaluation/sprint-12/optimization/s12-f-11-full-stage-a-report.v3.json"
ATOMIC = ROOT / "evaluation/sprint-12/corpus/v3-frozen/atomic-v3.frozen.v1.json"
SELECTION = ROOT / "evaluation/sprint-12/optimization/s12-f-10-case-selection.v2.json"
OUTPUT = (
    ROOT / "evaluation/sprint-12/optimization/s12-f-11-offline-relation-rca.v1.json"
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _digest(path: Path) -> str:
    return (
        "sha256:"
        + hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    )


def _span(item: dict[str, Any]) -> tuple[int, int] | None:
    value = item.get("span", item.get("evidence"))
    if not isinstance(value, dict):
        return None
    start = value.get("start")
    end = value.get("end")
    if not isinstance(start, int) or not isinstance(end, int) or start >= end:
        return None
    return start, end


def _case_profile(case: dict[str, Any]) -> dict[str, Any]:
    gold = case["gold"]
    entities = gold["entities"]
    relations = gold["relations"]
    source_length = len(case["source"]["rawText"])
    entity_ids = {str(item.get("id")) for item in entities}
    valid_entities = sum(
        _span(item) is not None and _span(item)[1] <= source_length  # type: ignore[index]
        for item in entities
    )
    endpoint_resolved = 0
    evidence_valid = 0
    for relation in relations:
        source_id = str(relation.get("sourceEntityId"))
        target_id = str(relation.get("targetEntityId"))
        source_entity = next(
            (item for item in entities if str(item.get("id")) == source_id), None
        )
        target_entity = next(
            (item for item in entities if str(item.get("id")) == target_id), None
        )
        relation_span = _span(relation)
        source_span = _span(source_entity or {})
        target_span = _span(target_entity or {})
        if source_id in entity_ids and target_id in entity_ids:
            endpoint_resolved += 1
        if (
            relation_span is not None
            and source_span is not None
            and target_span is not None
            and relation_span[1] <= source_length
            and relation_span[0] <= source_span[0]
            and relation_span[1] >= source_span[1]
            and relation_span[0] <= target_span[0]
            and relation_span[1] >= target_span[1]
        ):
            evidence_valid += 1
    return {
        "caseId": str(case["caseId"]),
        "journey": str(case["journeyId"]),
        "language": str(case["source"]["language"]),
        "entityCount": len(entities),
        "validEntitySpans": valid_entities,
        "relationCount": len(relations),
        "relationsWithResolvedEndpoints": endpoint_resolved,
        "relationsWithValidEvidenceSpan": evidence_valid,
        "abstentionRequired": bool(gold["abstention"].get("required")),
    }


def _rate(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator if denominator else "not-applicable",
    }


def analyze() -> dict[str, Any]:
    report = _load(REPORT)
    atomic = _load(ATOMIC)
    selection = _load(SELECTION)
    by_id = {str(case["caseId"]): case for case in atomic["cases"]}
    selected = [by_id[str(case_id)] for case_id in selection["caseIds"]]
    profiles = [_case_profile(case) for case in selected]
    runs = 3
    relation_gold_per_run = sum(item["relationCount"] for item in profiles)
    entity_gold_per_run = sum(item["entityCount"] for item in profiles)
    endpoint_total = sum(item["relationsWithResolvedEndpoints"] for item in profiles)
    evidence_total = sum(item["relationsWithValidEvidenceSpan"] for item in profiles)
    relation_total = relation_gold_per_run * runs
    entity_total = entity_gold_per_run * runs
    control = report["metrics"]["control"]["primary"]
    candidate = report["metrics"]["candidate"]["primary"]
    case_labels = Counter(
        "abstention-required" if item["abstentionRequired"] else "non-abstention"
        for item in profiles
    )
    return {
        "artifactVersion": "s12.s12-f-11.offline-relation-rca.v1",
        "status": "OFFLINE_RCA_COMPLETE_WITH_SANITIZED_REPORT_LIMITATION",
        "experimentId": "s12-f-11",
        "inputs": {
            "reportPath": str(REPORT.relative_to(ROOT).as_posix()),
            "reportDigest": _digest(REPORT),
            "atomicCorpusPath": str(ATOMIC.relative_to(ROOT).as_posix()),
            "atomicCorpusDigest": _digest(ATOMIC),
            "caseSelectionPath": str(SELECTION.relative_to(ROOT).as_posix()),
            "caseSelectionDigest": _digest(SELECTION),
            "rawProviderPayloadRead": False,
            "heldOutAccess": False,
        },
        "frozenProfile": {
            "caseCount": len(selected),
            "runs": runs,
            "caseRuns": len(selected) * runs,
            "relationPositiveCases": sum(
                item["relationCount"] > 0 for item in profiles
            ),
            "abstentionRequiredCases": case_labels["abstention-required"],
            "hardNegativeCases": sum(
                item["relationCount"] == 0 and not item["abstentionRequired"]
                for item in profiles
            ),
            "goldEntitiesPerRun": entity_gold_per_run,
            "goldRelationsPerRun": relation_gold_per_run,
            "goldEntityInstancesAcrossRuns": entity_total,
            "goldRelationInstancesAcrossRuns": relation_total,
        },
        "oracleRelationCeiling": {
            "goldEntityEndpointResolution": _rate(
                endpoint_total, relation_gold_per_run
            ),
            "goldEvidenceSpanValidity": _rate(evidence_total, relation_gold_per_run),
            "perfectTwoStepRelationSemanticMicroF1": 1.0,
            "perfectTwoStepRelationSemanticMacroF1": 1.0,
            "interpretation": "With gold entities and a perfect second-stage predicate/endpoint/evidence decoder, the frozen gold labels permit a 1.0 relation ceiling. This is a structural counterfactual, not an observed model score.",
        },
        "observedExecutionSignals": {
            "providerCalls": report["providerCallCount"],
            "branchOutputs": report["branchOutputCount"],
            "retryCount": report["retryCount"],
            "totalCostUsd": report["pricing"]["totalCostUsd"],
            "candidateMaterializerEvidenceFailures": report["failureCounts"].get(
                "invalid_evidence", 0
            ),
            "control": {
                "relationGold": control["denominators"]["relationGold"],
                "relationPredicted": control["denominators"]["relationPredicted"],
                "relationSemanticTruePositive": control["denominators"][
                    "relationSemanticTruePositive"
                ],
                "relationSemanticMicroF1": control["relationSemanticMicroF1"],
                "entityMacroF1": control["entityMacroF1"],
                "abstentionF1": control["abstentionF1"],
                "hallucinationRate": control["hallucinationRate"],
            },
            "candidate": {
                "relationGold": candidate["denominators"]["relationGold"],
                "relationPredicted": candidate["denominators"]["relationPredicted"],
                "relationSemanticTruePositive": candidate["denominators"][
                    "relationSemanticTruePositive"
                ],
                "relationSemanticMicroF1": candidate["relationSemanticMicroF1"],
                "entityMacroF1": candidate["entityMacroF1"],
                "abstentionF1": candidate["abstentionF1"],
                "hallucinationRate": candidate["hallucinationRate"],
            },
        },
        "errorDecomposition": {
            "entityDetection": {
                "signal": "entityMacroF1=0.14791666666666667 in both arms",
                "interpretation": "Entity detection is a strong bottleneck signal, but its exact causal contribution to each relation miss cannot be recovered from this sanitized report.",
            },
            "predicateEndpoint": {
                "signal": "relation semantic true positives are 0 in both arms",
                "interpretation": "Predicate/endpoint correctness cannot be separated into predicate, reversed endpoint, missing endpoint and wrong endpoint buckets without per-relation sanitized instrumentation or predictions.",
            },
            "evidenceMaterialization": {
                "signal": "candidate materializer/evidence failures=53",
                "interpretation": "This is a failure count across branch materialization/evidence handling, not a provider-call count; it is downstream of the response and does not identify the upstream entity or predicate error by itself.",
            },
            "abstention": {
                "signal": "abstentionF1=0 in both arms",
                "interpretation": "Abstention behavior is independently failing and should be measured as its own decision head in a two-step design.",
            },
            "exactBucketDecompositionAvailable": False,
            "limitation": "The committed report stores response digests, aggregate metrics and sanitized materializer counts, but no raw payload, prediction, or per-relation bucket record. Exact entity-vs-predicate-vs-endpoint-vs-evidence attribution is therefore not identifiable retrospectively.",
        },
        "architectureAssessment": {
            "recommendation": "PREPARE_OFFLINE_TWO_STEP_EXTRACTION_DESIGN",
            "stepOne": "Entity detection and typed span normalization, scored independently with entity precision/recall/F1 and abstention behavior.",
            "stepTwo": "Relation predicate and endpoint decoding over frozen entity candidates, followed by server-owned trigger/evidence validation.",
            "requiredOracleAblation": "For any future offline replay, run step two once with gold entities and once with predicted entities; persist only sanitized per-case error buckets and digests.",
            "preregistrationNow": False,
            "providerRerunNow": False,
            "reason": "The current report supports the architecture hypothesis but lacks the per-response predictions needed to preregister thresholds or claim a causal decomposition.",
        },
        "governance": {
            "f11RerunAuthorized": False,
            "stageBAuthorized": False,
            "candidateSelectionAuthorized": False,
            "heldOutAccess": False,
            "promotionAuthorized": False,
            "nextAction": "offline design and oracle-ablation specification only",
        },
        "rawSensitiveDataIncluded": False,
    }


if __name__ == "__main__":
    result = analyze()
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
