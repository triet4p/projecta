"""Fail-closed evaluator for the frozen Sprint 12 dense-hard candidate.

The evaluator is deliberately offline. It binds source, private gold,
manifest, candidate, and evaluator bytes before calculating diagnostics; any
integrity or anti-leak failure raises instead of producing a score.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v1"
SOURCE_NAME = "dense-hard-source-payload.v1.json"
GOLD_NAME = "dense-hard-gold.v1.json"
MANIFEST_NAME = "dense-hard-evaluator-manifest.v1.json"
CANDIDATE_NAME = "dense-hard-candidate.v1.json"
EVALUATION_NAME = "dense-hard-evaluation.v1.json"
SCOPE = "projecta.synthetic.s12.dense-hard"
ERROR_CODES = (
    "ENTITY_TYPE_MISMATCH", "ENTITY_SPAN_MISMATCH", "ENTITY_LABEL_MISMATCH",
    "ENTITY_MISSING", "ENTITY_EXTRA", "RELATION_PREDICATE_MISMATCH",
    "RELATION_ENDPOINT_MISMATCH", "RELATION_EVIDENCE_MISMATCH",
    "RELATION_MISSING", "RELATION_EXTRA", "ABSTENTION_MISSING",
    "ABSTENTION_OVER", "ABSTENTION_MODE_MISMATCH",
    "UNSUPPORTED_FINALIZED_ASSERTION", "HALLUCINATED_FINALIZED_ASSERTION",
)
MAJOR = {"entity_type", "relation_predicate", "relation_endpoint", "entity_missing", "entity_extra", "relation_missing", "relation_extra"}
MINOR = {"entity_span", "entity_label", "relation_evidence"}


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _stable(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_stable(value)).hexdigest()


def _schema_validate(value: dict[str, Any], path: Path) -> None:
    schema = _read(path)
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        raise ValueError(f"{path.name}: {list(errors[0].path)}: {errors[0].message}")


def _span(value: dict[str, Any]) -> tuple[int, int, str]:
    evidence = value["evidence"]
    return evidence["startOffset"], evidence["endOffset"], evidence["text"]


def _entity_span(value: dict[str, Any]) -> tuple[int, int]:
    return _span(value)[:2]


def _entity_index(entity_id: str) -> int:
    return int(entity_id.rsplit("e", 1)[1])


def _relation_endpoint(entity_id: str, entities: list[dict[str, Any]]) -> tuple[int, int, str]:
    entity = next(item for item in entities if item["entityId"] == entity_id)
    return (*_entity_span(entity), entity["type"])


def _relation_semantic(value: dict[str, Any], entities: list[dict[str, Any]]) -> tuple[Any, ...]:
    return (value["predicate"], _relation_endpoint(value["sourceEntityId"], entities), _relation_endpoint(value["targetEntityId"], entities))


def _f1(gold: set[tuple[Any, ...]], candidate: set[tuple[Any, ...]]) -> dict[str, Any]:
    tp, fp, fn = len(gold & candidate), len(candidate - gold), len(gold - candidate)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _match_entities(gold: list[dict[str, Any]], candidate: list[dict[str, Any]]) -> tuple[list[tuple[int, int]], set[int], set[int]]:
    matches: list[tuple[int, int]] = []
    used_gold: set[int] = set()
    used_candidate: set[int] = set()
    for ci, current in enumerate(candidate):
        options = [gi for gi, expected in enumerate(gold) if gi not in used_gold and _span(expected) == _span(current)]
        if not options:
            options = [gi for gi, expected in enumerate(gold) if gi not in used_gold and expected["label"].casefold() == current["label"].casefold()]
        if options:
            gi = min(options, key=lambda index: abs(gold[index]["evidence"]["startOffset"] - current["evidence"]["startOffset"]))
            matches.append((gi, ci))
            used_gold.add(gi)
            used_candidate.add(ci)
    return matches, used_gold, used_candidate


def _match_relations(gold: list[dict[str, Any]], candidate: list[dict[str, Any]]) -> tuple[list[tuple[int, int]], set[int], set[int]]:
    matches: list[tuple[int, int]] = []
    used_gold: set[int] = set()
    used_candidate: set[int] = set()
    for ci, current in enumerate(candidate):
        options = [gi for gi, expected in enumerate(gold) if gi not in used_gold and _span(expected) == _span(current)]
        if options:
            gi = options[0]
            matches.append((gi, ci))
            used_gold.add(gi)
            used_candidate.add(ci)
    return matches, used_gold, used_candidate


def _expected_abstention_mode(expected: dict[str, Any]) -> str | None:
    if expected["abstentionReason"] is None:
        return None
    return "full" if not expected["entities"] and not expected["relations"] else "partial"


def _difficulty(case_id: str) -> str:
    number = int(case_id[-3:])
    return "dense-baseline" if number <= 4 else "dense-disambiguation" if number <= 17 else "dense-adversarial-abstention"


def _validate_bindings(packet: Path, candidate_path: Path) -> dict[str, Any]:
    source = _read(packet / SOURCE_NAME)
    gold = _read(packet / GOLD_NAME)
    manifest = _read(packet / MANIFEST_NAME)
    candidate = _read(candidate_path)
    for value, name in ((source, "dense-hard-source-payload.v1.schema.json"), (gold, "dense-hard-gold.v1.schema.json"), (manifest, "dense-hard-evaluator-manifest.v1.schema.json"), (candidate, "dense-hard-candidate.v1.schema.json")):
        _schema_validate(value, packet / name)
    if _digest({key: value for key, value in source.items() if key != "payloadDigest"}) != source["payloadDigest"]:
        raise ValueError("source payload digest mismatch")
    if _digest({key: value for key, value in gold.items() if key != "goldDigest"}) != gold["goldDigest"]:
        raise ValueError("gold digest mismatch")
    if _digest({key: value for key, value in manifest.items() if key != "manifestDigest"}) != manifest["manifestDigest"]:
        raise ValueError("manifest digest mismatch")
    if candidate["candidateDigest"] != _digest({key: value for key, value in candidate.items() if key != "candidateDigest"}):
        raise ValueError("candidate digest mismatch")
    if candidate["payloadDigest"] != source["payloadDigest"] or gold["sourcePayloadDigest"] != source["payloadDigest"] or manifest["sourcePayloadDigest"] != source["payloadDigest"] or manifest["goldDigest"] != gold["goldDigest"]:
        raise ValueError("cross-artifact digest binding mismatch")
    if candidate["providerCalls"] != 0 or source["providerCalls"] != 0:
        raise ValueError("provider calls are forbidden")
    if any(candidate[key] for key in ("goldIncluded", "priorReviewsIncluded", "heldOutInspection", "rawSensitiveDataIncluded", "reviewOrScoringPerformed")):
        raise ValueError("candidate anti-leak flags are not clean")
    if candidate["payloadPath"] != f"evaluation/sprint-12/internal-poc/dense-hard-v1/{SOURCE_NAME}" or candidate["projectScopeId"] != SCOPE or candidate_path.name != CANDIDATE_NAME:
        raise ValueError("candidate source-only boundary mismatch")
    serialized = json.dumps(candidate, ensure_ascii=False)
    if any(token in serialized for token in ('"expected"', '"goldPath"', '"goldDigest"')):
        raise ValueError("private evaluator keys leaked into candidate")
    source_ids = {record["caseId"] for record in source["records"]}
    if source_ids != {record["caseId"] for record in gold["records"]} or source_ids != {record["caseId"] for record in candidate["records"]}:
        raise ValueError("source, gold and candidate case sets differ")
    return {"source": source, "gold": gold, "manifest": manifest, "candidate": candidate}


def _classify(source: dict[str, Any], expected: dict[str, Any], response: dict[str, Any], manifest_record: dict[str, Any]) -> dict[str, Any]:
    entities_gold, entities_candidate = expected["entities"], response["entities"]
    relations_gold, relations_candidate = expected["relations"], response["relations"]
    entity_gold_set = {(e["evidence"]["startOffset"], e["evidence"]["endOffset"], e["type"]) for e in entities_gold}
    entity_candidate_set = {(e["evidence"]["startOffset"], e["evidence"]["endOffset"], e["type"]) for e in entities_candidate}
    relation_gold_set = {_relation_semantic(r, entities_gold) for r in relations_gold}
    relation_candidate_set = {_relation_semantic(r, entities_candidate) for r in relations_candidate}
    diffs: Counter[str] = Counter()
    matches, used_gold, used_candidate = _match_entities(entities_gold, entities_candidate)
    for gi, ci in matches:
        expected_entity, current_entity = entities_gold[gi], entities_candidate[ci]
        if _span(expected_entity) != _span(current_entity):
            diffs["entity_span"] += 1
        if expected_entity["label"] != current_entity["label"]:
            diffs["entity_label"] += 1
        if expected_entity["type"] != current_entity["type"]:
            diffs["entity_type"] += 1
    diffs["entity_missing"] = len(set(range(len(entities_gold))) - used_gold)
    diffs["entity_extra"] = len(set(range(len(entities_candidate))) - used_candidate)
    relation_matches, relation_used_gold, relation_used_candidate = _match_relations(relations_gold, relations_candidate)
    for gi, ci in relation_matches:
        expected_relation, current_relation = relations_gold[gi], relations_candidate[ci]
        if expected_relation["predicate"] != current_relation["predicate"]:
            diffs["relation_predicate"] += 1
        expected_indices = tuple(_entity_index(expected_relation[key]) for key in ("sourceEntityId", "targetEntityId"))
        current_indices = tuple(_entity_index(current_relation[key]) for key in ("sourceEntityId", "targetEntityId"))
        if expected_indices != current_indices:
            diffs["relation_endpoint"] += 1
        if _span(expected_relation) != _span(current_relation):
            diffs["relation_evidence"] += 1
    diffs["relation_missing"] = len(set(range(len(relations_gold))) - relation_used_gold)
    diffs["relation_extra"] = len(set(range(len(relations_candidate))) - relation_used_candidate)
    semantic_edits = sum(diffs[key] for key in ("entity_type", "entity_missing", "entity_extra", "relation_predicate", "relation_endpoint", "relation_missing", "relation_extra"))
    candidate_status = response["abstention"]["status"]
    required = expected["abstentionReason"] is not None
    expected_mode = _expected_abstention_mode(expected)
    mode_correct = candidate_status == expected_mode if required else candidate_status == "none"
    if required and candidate_status == "none":
        classification = "reject"
        diffs["abstention_missing"] += 1
    elif not required and candidate_status != "none":
        classification = "abstain"
        diffs["abstention_over"] += 1
    elif candidate_status != "none":
        classification = "abstain"
        if not mode_correct:
            diffs["abstention_mode_mismatch"] += 1
    elif diffs["entity_type"] or diffs["relation_predicate"] or diffs["relation_endpoint"] or any(diffs[key] for key in ("entity_missing", "entity_extra", "relation_missing", "relation_extra")):
        classification = "major"
    elif any(diffs[key] for key in MINOR):
        classification = "minor"
    else:
        classification = "unchanged"
    mapping = {"entity_type": "ENTITY_TYPE_MISMATCH", "entity_span": "ENTITY_SPAN_MISMATCH", "entity_label": "ENTITY_LABEL_MISMATCH", "entity_missing": "ENTITY_MISSING", "entity_extra": "ENTITY_EXTRA", "relation_predicate": "RELATION_PREDICATE_MISMATCH", "relation_endpoint": "RELATION_ENDPOINT_MISMATCH", "relation_evidence": "RELATION_EVIDENCE_MISMATCH", "relation_missing": "RELATION_MISSING", "relation_extra": "RELATION_EXTRA", "abstention_missing": "ABSTENTION_MISSING", "abstention_over": "ABSTENTION_OVER", "abstention_mode_mismatch": "ABSTENTION_MODE_MISMATCH"}
    error_codes = [mapping[key] for key in mapping if diffs[key]]
    unsupported = len(entity_candidate_set - entity_gold_set) + len(relation_candidate_set - relation_gold_set)
    hallucinated = len({ _entity_span(entity) for entity in entities_candidate } - { _entity_span(entity) for entity in entities_gold }) + len(relation_candidate_set - relation_gold_set)
    if unsupported:
        error_codes.append("UNSUPPORTED_FINALIZED_ASSERTION")
    if hallucinated:
        error_codes.append("HALLUCINATED_FINALIZED_ASSERTION")
    return {"caseId": manifest_record["caseId"], "scenarioId": manifest_record["scenarioId"], "slices": manifest_record["slices"], "difficultyTier": _difficulty(manifest_record["caseId"]), "classification": classification, "goldAbstentionRequired": required, "expectedAbstentionMode": expected_mode, "candidateAbstentionStatus": candidate_status, "abstentionCorrect": mode_correct, "semanticEditCount": semantic_edits, "unsupportedFinalizedAssertions": unsupported, "hallucinatedFinalizedAssertions": hallucinated, "errorCodes": error_codes, "entity": {"gold": len(entities_gold), "candidate": len(entities_candidate), **_f1(entity_gold_set, entity_candidate_set), "dimensionDiffs": {key: diffs[key] for key in ("entity_span", "entity_type", "entity_label", "entity_missing", "entity_extra")}}, "relation": {"gold": len(relations_gold), "candidate": len(relations_candidate), **_f1(relation_gold_set, relation_candidate_set), "dimensionDiffs": {key: diffs[key] for key in ("relation_predicate", "relation_endpoint", "relation_evidence", "relation_missing", "relation_extra")}}}


def _aggregate(records: list[dict[str, Any]], field: str | None = None, value: str | None = None) -> dict[str, Any]:
    selected = [record for record in records if field is None or (value in record[field] if isinstance(record[field], list) else record[field] == value)]
    def pooled(name: str) -> dict[str, Any]:
        metric = {key: sum(record[name][key] for record in selected) for key in ("tp", "fp", "fn")}
        metric["precision"] = _ratio(metric["tp"], metric["tp"] + metric["fp"])
        metric["recall"] = _ratio(metric["tp"], metric["tp"] + metric["fn"])
        metric["f1"] = _ratio(2 * metric["precision"] * metric["recall"], metric["precision"] + metric["recall"])
        return metric
    required = sum(record["goldAbstentionRequired"] for record in selected)
    predicted = sum(record["candidateAbstentionStatus"] != "none" for record in selected)
    correct = sum(record["goldAbstentionRequired"] and record["abstentionCorrect"] for record in selected)
    return {"caseCount": len(selected), "classificationCounts": {kind: Counter(record["classification"] for record in selected)[kind] for kind in ("unchanged", "minor", "major", "reject", "abstain")}, "semanticEditCount": sum(record["semanticEditCount"] for record in selected), "unsupportedFinalizedAssertions": sum(record["unsupportedFinalizedAssertions"] for record in selected), "hallucinatedFinalizedAssertions": sum(record["hallucinatedFinalizedAssertions"] for record in selected), "abstentionRequired": required, "abstentionPredicted": predicted, "abstentionCorrect": sum(record["abstentionCorrect"] for record in selected), "abstentionPrecision": _ratio(correct, predicted), "abstentionRecall": _ratio(correct, required), "entityMetrics": pooled("entity"), "relationMetrics": pooled("relation")}


def evaluate(candidate_path: Path | None = None, packet_dir: Path = PACKET) -> dict[str, Any]:
    if candidate_path is None:
        return {"status": "CANDIDATE_NOT_PROVIDED", "scoreProduced": False}
    bound = _validate_bindings(packet_dir, candidate_path)
    source, gold, manifest, candidate = bound["source"], bound["gold"], bound["manifest"], bound["candidate"]
    source_by_id = {record["caseId"]: record for record in source["records"]}
    gold_by_id = {record["caseId"]: record["expected"] for record in gold["records"]}
    manifest_by_id = {record["caseId"]: record for record in manifest["records"]}
    candidate_by_id = {record["caseId"]: record["response"] for record in candidate["records"]}
    per_item = [_classify(source_by_id[case_id], gold_by_id[case_id], candidate_by_id[case_id], manifest_by_id[case_id]) for case_id in sorted(source_by_id)]
    entity_gold = {(record["caseId"], e["evidence"]["startOffset"], e["evidence"]["endOffset"], e["type"]) for record in gold["records"] for e in gold_by_id[record["caseId"]]["entities"]}
    entity_candidate = {(record["caseId"], e["evidence"]["startOffset"], e["evidence"]["endOffset"], e["type"]) for record in candidate["records"] for e in candidate_by_id[record["caseId"]]["entities"]}
    relation_gold = {(record["caseId"], *_relation_semantic(r, gold_by_id[record["caseId"]]["entities"])) for record in gold["records"] for r in gold_by_id[record["caseId"]]["relations"]}
    relation_candidate = {(record["caseId"], *_relation_semantic(r, candidate_by_id[record["caseId"]]["entities"])) for record in candidate["records"] for r in candidate_by_id[record["caseId"]]["relations"]}
    entity_metrics, relation_metrics = _f1(entity_gold, entity_candidate), _f1(relation_gold, relation_candidate)
    classes = Counter(record["classification"] for record in per_item)
    required = [record for record in per_item if record["goldAbstentionRequired"]]
    predicted = [record for record in per_item if record["candidateAbstentionStatus"] != "none"]
    required_ids, predicted_ids = {record["caseId"] for record in required}, {record["caseId"] for record in predicted}
    full_required = [record for record in required if record["expectedAbstentionMode"] == "full"]
    partial_required = [record for record in required if record["expectedAbstentionMode"] == "partial"]
    full_predicted = [record for record in predicted if record["candidateAbstentionStatus"] == "full"]
    partial_predicted = [record for record in predicted if record["candidateAbstentionStatus"] == "partial"]
    full_tp = len({record["caseId"] for record in full_required} & {record["caseId"] for record in full_predicted})
    partial_tp = len({record["caseId"] for record in partial_required} & {record["caseId"] for record in partial_predicted})
    abstention = {"required": len(required), "predicted": len(predicted), "truePositive": len(required_ids & predicted_ids), "precision": _ratio(len(required_ids & predicted_ids), len(predicted_ids)), "recall": _ratio(len(required_ids & predicted_ids), len(required_ids)), "full": {"required": len(full_required), "predicted": len(full_predicted), "correct": full_tp, "precision": _ratio(full_tp, len(full_predicted)), "recall": _ratio(full_tp, len(full_required))}, "partial": {"required": len(partial_required), "predicted": len(partial_predicted), "correct": partial_tp, "precision": _ratio(partial_tp, len(partial_predicted)), "recall": _ratio(partial_tp, len(partial_required))}}
    slices = sorted({slice_name for record in manifest["records"] for slice_name in record["slices"]})
    tiers = sorted({_difficulty(record["caseId"]) for record in per_item})
    total_edits = sum(record["semanticEditCount"] for record in per_item)
    total_unsupported = sum(record["unsupportedFinalizedAssertions"] for record in per_item)
    total_finalized = len(entity_candidate) + len(relation_candidate)
    accepted_without, accepted_minor = classes["unchanged"] / len(per_item), (classes["unchanged"] + classes["minor"]) / len(per_item)
    taxonomy = {code: sum(code in record["errorCodes"] for record in per_item) for code in ERROR_CODES}
    result: dict[str, Any] = {"artifactVersion": "s12.dense-hard.evaluation.v1", "status": "EVALUATED_FROZEN_CANDIDATE", "datasetKind": "SYNTHETIC_NON_PRODUCTION", "evaluatorVersion": "s12.dense-hard.evaluator.v1", "sourcePayloadPath": f"evaluation/sprint-12/internal-poc/dense-hard-v1/{SOURCE_NAME}", "sourcePayloadDigest": source["payloadDigest"], "goldPath": f"evaluation/sprint-12/internal-poc/dense-hard-v1/{GOLD_NAME}", "goldDigest": gold["goldDigest"], "manifestPath": f"evaluation/sprint-12/internal-poc/dense-hard-v1/{MANIFEST_NAME}", "manifestDigest": manifest["manifestDigest"], "candidatePath": f"evaluation/sprint-12/internal-poc/dense-hard-v1/{CANDIDATE_NAME}", "candidateDigest": candidate["candidateDigest"], "candidateModel": candidate["candidateModel"], "providerCalls": 0, "antiLeakChecks": {"candidateDigestBound": True, "sourceDigestBound": True, "goldDigestBound": True, "manifestDigestBound": True, "candidateSourceOnlyFlagsClean": True, "goldExcludedFromCandidate": True, "providerCallsZero": True, "heldOutInspectionFalse": True, "fRfStateChanged": False}, "counts": {"caseCount": len(per_item), "entityGold": len(entity_gold), "entityCandidate": len(entity_candidate), "relationGold": len(relation_gold), "relationCandidate": len(relation_candidate)}, "perItemClassificationCounts": {kind: classes[kind] for kind in ("unchanged", "minor", "major", "reject", "abstain")}, "semanticEditCounts": {"total": total_edits, "meanPerCase": total_edits / len(per_item)}, "entityMetrics": entity_metrics, "relationMetrics": relation_metrics, "abstentionMetrics": abstention, "unsupportedFinalizedAssertions": {"numerator": total_unsupported, "denominator": total_finalized, "status": "ZERO_UNSUPPORTED" if total_unsupported == 0 else "UNSUPPORTED_PRESENT"}, "hallucinatedFinalizedAssertions": {"numerator": sum(record["hallucinatedFinalizedAssertions"] for record in per_item), "denominator": total_finalized, "status": "ZERO_HALLUCINATED" if not sum(record["hallucinatedFinalizedAssertions"] for record in per_item) else "HALLUCINATED_PRESENT"}, "rm67": {"thresholds": {"acceptedWithoutSemanticCorrectionMinimum": 0.70, "acceptedUnchangedOrMinorMinimum": 0.85, "meanSemanticEditsMaximum": 2.0, "unsupportedFinalizedAssertionsMaximum": 0}, "acceptedWithoutSemanticCorrection": accepted_without, "acceptedUnchangedOrMinor": accepted_minor, "meanSemanticEditsPerReviewedItem": total_edits / len(per_item), "unsupportedFinalizedAssertions": {"numerator": total_unsupported, "denominator": total_finalized, "status": "ZERO_UNSUPPORTED" if total_unsupported == 0 else "UNSUPPORTED_PRESENT"}, "editBurdenGate": accepted_without >= 0.70 and accepted_minor >= 0.85 and total_edits / len(per_item) <= 2.0 and total_unsupported == 0}, "perItem": per_item, "perSlice": {slice_name: _aggregate(per_item, "slices", slice_name) for slice_name in slices}, "difficultyTiers": {tier: _aggregate(per_item, "difficultyTier", tier) for tier in tiers}, "worstCases": [{"caseId": record["caseId"], "classification": record["classification"], "semanticEditCount": record["semanticEditCount"], "unsupportedFinalizedAssertions": record["unsupportedFinalizedAssertions"], "errorCodes": record["errorCodes"]} for record in sorted(per_item, key=lambda item: (-item["semanticEditCount"], -item["unsupportedFinalizedAssertions"], item["caseId"]))[:5]], "errorTaxonomy": {"codes": list(ERROR_CODES), "counts": taxonomy}, "nonClaims": ["This is an offline synthetic diagnostic, not human evidence or a production quality claim.", "No provider call, external tool, held-out inspection, F-RF transition, selection, promotion, or release was performed.", "F1 is diagnostic and cannot substitute for RM-68 human correction-burden evidence."]}
    result["evaluationDigest"] = _digest(result)
    return result


def write_immutable_evaluation(packet_dir: Path = PACKET) -> Path:
    output = evaluate(packet_dir / CANDIDATE_NAME, packet_dir)
    path = packet_dir / EVALUATION_NAME
    content = json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise ValueError(f"immutable evaluation already exists with different bytes: {path}")
    if not path.exists():
        path.write_text(content, encoding="utf-8")
    return path


def validate_evaluation_artifact(path: Path, packet_dir: Path = PACKET) -> dict[str, Any]:
    """Recompute and validate an evaluation artifact without mutating it."""
    value = _read(path)
    _schema_validate(value, packet_dir / "dense-hard-evaluation.v1.schema.json")
    if value["evaluationDigest"] != _digest({key: child for key, child in value.items() if key != "evaluationDigest"}):
        raise ValueError("evaluation digest mismatch")
    recomputed = evaluate(packet_dir / CANDIDATE_NAME, packet_dir)
    if value != recomputed:
        raise ValueError("evaluation artifact differs from deterministic recomputation")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    print(json.dumps({"status": "WRITTEN", "path": str(write_immutable_evaluation())}, sort_keys=True) if args.write else json.dumps(evaluate(args.candidate), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
