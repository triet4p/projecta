"""Deterministic offline evaluator for the frozen dense-hard v2 candidate."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v2"
V1_PACKET = ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v1"
SOURCE_NAME = "dense-hard-source-payload.v2.json"
GOLD_NAME = "dense-hard-gold.v2.json"
MANIFEST_NAME = "dense-hard-evaluator-manifest.v2.json"
PROTOCOL_NAME = "dense-hard-source-only-protocol.v2.json"
CANDIDATE_NAME = "dense-hard-candidate.v2.json"
EVALUATION_NAME = "dense-hard-evaluation.v2.json"
BUILD_NAME = "build_dense_hard_candidate_v2.py"
ERROR_CODES = ("ENTITY_TYPE_MISMATCH", "ENTITY_SPAN_MISMATCH", "ENTITY_LABEL_MISMATCH", "ENTITY_MISSING", "ENTITY_EXTRA", "RELATION_PREDICATE_MISMATCH", "RELATION_ENDPOINT_MISMATCH", "RELATION_EVIDENCE_MISMATCH", "RELATION_MISSING", "RELATION_EXTRA", "ABSTENTION_MISSING", "ABSTENTION_OVER", "ABSTENTION_MODE_MISMATCH", "QUARANTINE_CORRECT", "INCORRECT_QUARANTINE", "QUARANTINE_MISSING", "UNSUPPORTED_FINALIZED_ASSERTION", "HALLUCINATED_FINALIZED_ASSERTION")
MAJOR = {"entity_type", "relation_predicate", "relation_endpoint", "entity_missing", "entity_extra", "relation_missing", "relation_extra"}
MINOR = {"entity_span", "entity_label", "relation_evidence"}


def stable(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(stable(value)).hexdigest()


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_schema(value: dict[str, Any], schema_path: Path) -> None:
    schema = read(schema_path)
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        raise ValueError(f"{schema_path.name}: {list(errors[0].path)}: {errors[0].message}")


def span(item: dict[str, Any]) -> tuple[int, int, str]:
    evidence = item["evidence"]
    return evidence["startOffset"], evidence["endOffset"], evidence["text"]


def endpoint(entity_id: str, entities: list[dict[str, Any]]) -> tuple[int, int, str, str]:
    item = next(entity for entity in entities if entity["entityId"] == entity_id)
    start, end, text = span(item)
    return start, end, text, item["type"]


def relation_key(item: dict[str, Any], entities: list[dict[str, Any]]) -> tuple[Any, ...]:
    return (item["predicate"], endpoint(item["sourceEntityId"], entities), endpoint(item["targetEntityId"], entities))


def f1(gold: set[tuple[Any, ...]], candidate: set[tuple[Any, ...]]) -> dict[str, Any]:
    tp, fp, fn = len(gold & candidate), len(candidate - gold), len(gold - candidate)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def difficulty(case_id: str) -> str:
    number = int(case_id[-3:])
    return "dense-v2-baseline" if number <= 4 else "dense-v2-disambiguation" if number <= 17 else "dense-v2-adversarial-abstention"


def match_by_span(gold: list[dict[str, Any]], candidate: list[dict[str, Any]]) -> tuple[list[tuple[int, int]], set[int], set[int]]:
    matches: list[tuple[int, int]] = []
    used_gold: set[int] = set()
    used_candidate: set[int] = set()
    for candidate_index, current in enumerate(candidate):
        options = [gold_index for gold_index, expected in enumerate(gold) if gold_index not in used_gold and span(expected) == span(current)]
        if options:
            gold_index = options[0]
            matches.append((gold_index, candidate_index))
            used_gold.add(gold_index)
            used_candidate.add(candidate_index)
    return matches, used_gold, used_candidate


def validate_bindings(packet_dir: Path, candidate_path: Path) -> dict[str, Any]:
    source = read(packet_dir / SOURCE_NAME)
    gold = read(packet_dir / GOLD_NAME)
    manifest = read(packet_dir / MANIFEST_NAME)
    protocol = read(packet_dir / PROTOCOL_NAME)
    candidate = read(candidate_path)
    for value, name in ((source, SOURCE_NAME), (gold, GOLD_NAME), (manifest, MANIFEST_NAME), (protocol, PROTOCOL_NAME), (candidate, CANDIDATE_NAME)):
        validate_schema(value, packet_dir / name.replace(".json", ".schema.json"))
    if digest({key: value for key, value in source.items() if key != "payloadDigest"}) != source["payloadDigest"] or digest({key: value for key, value in gold.items() if key != "goldDigest"}) != gold["goldDigest"] or digest({key: value for key, value in manifest.items() if key != "manifestDigest"}) != manifest["manifestDigest"] or digest({key: value for key, value in protocol.items() if key != "protocolDigest"}) != protocol["protocolDigest"]:
        raise ValueError("source/gold/manifest/protocol digest mismatch")
    if candidate["candidateDigest"] != "sha256:" + hashlib.sha256(stable({**candidate, "candidateDigest": None})).hexdigest():
        raise ValueError("candidate digest mismatch")
    if candidate["codeDigest"] != file_digest(packet_dir / BUILD_NAME):
        raise ValueError("candidate build code digest mismatch")
    if candidate["sourcePayloadDigest"] != source["payloadDigest"] or candidate["protocolDigest"] != protocol["protocolDigest"] or gold["sourcePayloadDigest"] != source["payloadDigest"] or manifest["sourcePayloadDigest"] != source["payloadDigest"] or manifest["goldDigest"] != gold["goldDigest"]:
        raise ValueError("cross-artifact digest binding mismatch")
    if candidate["providerCalls"] != 0 or candidate["goldIncluded"] or candidate["priorReviewsIncluded"] or candidate["scoring"] or candidate["review"] or not candidate["sourceOnly"]:
        raise ValueError("candidate source-only or anti-leak flags are not clean")
    source_ids = {record["caseId"] for record in source["records"]}
    if source_ids != {record["caseId"] for record in gold["records"]} or source_ids != {record["caseId"] for record in manifest["records"]} or source_ids != {response["caseId"] for response in candidate["responses"]}:
        raise ValueError("source, gold, manifest, and candidate case sets differ")
    return {"source": source, "gold": gold, "manifest": manifest, "protocol": protocol, "candidate": candidate}


def classify(source: dict[str, Any], expected: dict[str, Any], response: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    gold_entities, candidate_entities = expected["entities"], response["entities"]
    gold_relations, candidate_relations = expected["relations"], response["relations"]
    diffs: Counter[str] = Counter()
    entity_matches, used_gold_entities, used_candidate_entities = match_by_span(gold_entities, candidate_entities)
    for gold_index, candidate_index in entity_matches:
        gold_entity, candidate_entity = gold_entities[gold_index], candidate_entities[candidate_index]
        if span(gold_entity) != span(candidate_entity):
            diffs["entity_span"] += 1
        if gold_entity["label"] != candidate_entity["label"]:
            diffs["entity_label"] += 1
        if gold_entity["type"] != candidate_entity["type"]:
            diffs["entity_type"] += 1
    diffs["entity_missing"] = len(set(range(len(gold_entities))) - used_gold_entities)
    diffs["entity_extra"] = len(set(range(len(candidate_entities))) - used_candidate_entities)
    relation_matches, used_gold_relations, used_candidate_relations = match_by_span(gold_relations, candidate_relations)
    for gold_index, candidate_index in relation_matches:
        gold_relation, candidate_relation = gold_relations[gold_index], candidate_relations[candidate_index]
        if gold_relation["predicate"] != candidate_relation["predicate"]:
            diffs["relation_predicate"] += 1
        if (endpoint(gold_relation["sourceEntityId"], gold_entities), endpoint(gold_relation["targetEntityId"], gold_entities)) != (endpoint(candidate_relation["sourceEntityId"], candidate_entities), endpoint(candidate_relation["targetEntityId"], candidate_entities)):
            diffs["relation_endpoint"] += 1
        if span(gold_relation) != span(candidate_relation) or span(gold_relation["triggerEvidence"]) != span(candidate_relation["triggerEvidence"]):
            diffs["relation_evidence"] += 1
    diffs["relation_missing"] = len(set(range(len(gold_relations))) - used_gold_relations)
    diffs["relation_extra"] = len(set(range(len(candidate_relations))) - used_candidate_relations)
    semantic_edits = sum(diffs[key] for key in ("entity_type", "entity_missing", "entity_extra", "relation_predicate", "relation_endpoint", "relation_missing", "relation_extra"))
    expected_mode = expected["abstentionMode"]
    candidate_mode = response["abstention"]["mode"]
    required = expected_mode != "none"
    mode_correct = candidate_mode == expected_mode if required else candidate_mode == "none"
    if required and candidate_mode == "none":
        classification = "reject"
        diffs["abstention_missing"] += 1
    elif not required and candidate_mode != "none":
        classification = "abstain"
        diffs["abstention_over"] += 1
    elif candidate_mode != "none":
        classification = "abstain"
        if not mode_correct:
            diffs["abstention_mode_mismatch"] += 1
    elif any(diffs[key] for key in MAJOR):
        classification = "major"
    elif any(diffs[key] for key in MINOR):
        classification = "minor"
    else:
        classification = "unchanged"
    gold_entity_set = {(item["evidence"]["startOffset"], item["evidence"]["endOffset"], item["type"]) for item in gold_entities}
    candidate_entity_set = {(item["evidence"]["startOffset"], item["evidence"]["endOffset"], item["type"]) for item in candidate_entities}
    gold_relation_set = {relation_key(item, gold_entities) for item in gold_relations}
    candidate_relation_set = {relation_key(item, candidate_entities) for item in candidate_relations}
    unsupported = len(candidate_entity_set - gold_entity_set) + len(candidate_relation_set - gold_relation_set)
    hallucinated = len({(item["evidence"]["startOffset"], item["evidence"]["endOffset"]) for item in candidate_entities} - {(item["evidence"]["startOffset"], item["evidence"]["endOffset"]) for item in gold_entities}) + len(candidate_relation_set - gold_relation_set)
    gold_evidence = {(item["kind"], item["evidence"]["startOffset"], item["evidence"]["endOffset"], item["evidence"]["text"]) for item in ([{"kind": "entity", **entity} for entity in gold_entities] + [{"kind": "relation", **relation} for relation in gold_relations])}
    quarantine_correct = 0
    quarantine_incorrect = 0
    for item in response["quarantined"]:
        key = ("entity" if item["kind"] == "entity" else "relation", item["evidence"]["startOffset"], item["evidence"]["endOffset"], item["evidence"]["text"])
        if key in gold_evidence:
            quarantine_incorrect += 1
        else:
            quarantine_correct += 1
    error_codes = [key.upper() for key in ()]
    mapping = {"entity_type": "ENTITY_TYPE_MISMATCH", "entity_span": "ENTITY_SPAN_MISMATCH", "entity_label": "ENTITY_LABEL_MISMATCH", "entity_missing": "ENTITY_MISSING", "entity_extra": "ENTITY_EXTRA", "relation_predicate": "RELATION_PREDICATE_MISMATCH", "relation_endpoint": "RELATION_ENDPOINT_MISMATCH", "relation_evidence": "RELATION_EVIDENCE_MISMATCH", "relation_missing": "RELATION_MISSING", "relation_extra": "RELATION_EXTRA", "abstention_missing": "ABSTENTION_MISSING", "abstention_over": "ABSTENTION_OVER", "abstention_mode_mismatch": "ABSTENTION_MODE_MISMATCH"}
    error_codes = [mapping[key] for key in mapping if diffs[key]]
    if quarantine_correct:
        error_codes.append("QUARANTINE_CORRECT")
    if quarantine_incorrect:
        error_codes.append("INCORRECT_QUARANTINE")
    if unsupported:
        error_codes.append("UNSUPPORTED_FINALIZED_ASSERTION")
    if hallucinated:
        error_codes.append("HALLUCINATED_FINALIZED_ASSERTION")
    return {"caseId": manifest["caseId"], "scenarioId": manifest["scenarioId"], "slices": manifest["slices"], "difficultyTier": difficulty(manifest["caseId"]), "classification": classification, "goldAbstentionRequired": required, "expectedAbstentionMode": expected_mode, "candidateAbstentionStatus": candidate_mode, "abstentionCorrect": mode_correct, "semanticEditCount": semantic_edits, "unsupportedFinalizedAssertions": unsupported, "hallucinatedFinalizedAssertions": hallucinated, "quarantinePredicted": len(response["quarantined"]), "quarantineCorrect": quarantine_correct, "quarantineIncorrect": quarantine_incorrect, "errorCodes": error_codes, "entity": {"gold": len(gold_entities), "candidate": len(candidate_entities), **f1(gold_entity_set, candidate_entity_set), "dimensionDiffs": {key: diffs[key] for key in ("entity_span", "entity_type", "entity_label", "entity_missing", "entity_extra")}}, "relation": {"gold": len(gold_relations), "candidate": len(candidate_relations), **f1(gold_relation_set, candidate_relation_set), "dimensionDiffs": {key: diffs[key] for key in ("relation_predicate", "relation_endpoint", "relation_evidence", "relation_missing", "relation_extra")}}}


def aggregate(records: list[dict[str, Any]], field: str | None = None, value: str | None = None) -> dict[str, Any]:
    selected = [record for record in records if field is None or (value in record[field] if isinstance(record[field], list) else record[field] == value)]
    def pooled(name: str) -> dict[str, Any]:
        metric = {key: sum(record[name][key] for record in selected) for key in ("tp", "fp", "fn")}
        metric["precision"] = ratio(metric["tp"], metric["tp"] + metric["fp"])
        metric["recall"] = ratio(metric["tp"], metric["tp"] + metric["fn"])
        metric["f1"] = ratio(2 * metric["precision"] * metric["recall"], metric["precision"] + metric["recall"])
        return metric
    required = sum(record["goldAbstentionRequired"] for record in selected)
    predicted = sum(record["candidateAbstentionStatus"] != "none" for record in selected)
    correct = sum(record["goldAbstentionRequired"] and record["abstentionCorrect"] for record in selected)
    return {"caseCount": len(selected), "classificationCounts": {kind: Counter(record["classification"] for record in selected)[kind] for kind in ("unchanged", "minor", "major", "reject", "abstain")}, "semanticEditCount": sum(record["semanticEditCount"] for record in selected), "unsupportedFinalizedAssertions": sum(record["unsupportedFinalizedAssertions"] for record in selected), "hallucinatedFinalizedAssertions": sum(record["hallucinatedFinalizedAssertions"] for record in selected), "quarantinePredicted": sum(record["quarantinePredicted"] for record in selected), "quarantineCorrect": sum(record["quarantineCorrect"] for record in selected), "quarantineIncorrect": sum(record["quarantineIncorrect"] for record in selected), "abstentionRequired": required, "abstentionPredicted": predicted, "abstentionCorrect": correct, "abstentionPrecision": ratio(correct, predicted), "abstentionRecall": ratio(correct, required), "entityMetrics": pooled("entity"), "relationMetrics": pooled("relation")}


def evaluate(candidate_path: Path = PACKET / CANDIDATE_NAME, packet_dir: Path = PACKET) -> dict[str, Any]:
    bound = validate_bindings(packet_dir, candidate_path)
    source, gold, manifest, candidate = bound["source"], bound["gold"], bound["manifest"], bound["candidate"]
    source_by_id = {record["caseId"]: record for record in source["records"]}
    gold_by_id = {record["caseId"]: record["expected"] for record in gold["records"]}
    manifest_by_id = {record["caseId"]: record for record in manifest["records"]}
    candidate_by_id = {response["caseId"]: response for response in candidate["responses"]}
    per_item = [classify(source_by_id[case_id], gold_by_id[case_id], candidate_by_id[case_id], manifest_by_id[case_id]) for case_id in sorted(source_by_id)]
    entity_gold = {(record["caseId"], item["evidence"]["startOffset"], item["evidence"]["endOffset"], item["type"]) for record in gold["records"] for item in gold_by_id[record["caseId"]]["entities"]}
    entity_candidate = {(record["caseId"], item["evidence"]["startOffset"], item["evidence"]["endOffset"], item["type"]) for record in candidate["responses"] for item in candidate_by_id[record["caseId"]]["entities"]}
    relation_gold = {(record["caseId"], *relation_key(item, gold_by_id[record["caseId"]]["entities"])) for record in gold["records"] for item in gold_by_id[record["caseId"]]["relations"]}
    relation_candidate = {(record["caseId"], *relation_key(item, candidate_by_id[record["caseId"]]["entities"])) for record in candidate["responses"] for item in candidate_by_id[record["caseId"]]["relations"]}
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
    quarantine_predicted = sum(record["quarantinePredicted"] for record in per_item)
    quarantine_correct = sum(record["quarantineCorrect"] for record in per_item)
    quarantine_incorrect = sum(record["quarantineIncorrect"] for record in per_item)
    unsafe_finalized = sum(record["unsupportedFinalizedAssertions"] for record in per_item)
    unsafe_total = quarantine_correct + unsafe_finalized
    q_case_required = len(required)
    q_case_predicted = sum(record["quarantinePredicted"] > 0 for record in per_item)
    q_case_correct = sum(record["goldAbstentionRequired"] and record["quarantinePredicted"] > 0 for record in per_item)
    v1 = read(V1_PACKET / "dense-hard-evaluation.v1.json")
    result: dict[str, Any] = {"artifactVersion": "s12.dense-hard.evaluation.v2", "status": "EVALUATED_FROZEN_CANDIDATE", "datasetKind": "SYNTHETIC_NON_PRODUCTION", "evaluatorVersion": "s12.dense-hard.evaluator.v2", "evaluatorCodeDigest": file_digest(Path(__file__)), "sourcePayloadPath": f"evaluation/sprint-12/internal-poc/dense-hard-v2/{SOURCE_NAME}", "sourcePayloadDigest": source["payloadDigest"], "protocolPath": f"evaluation/sprint-12/internal-poc/dense-hard-v2/{PROTOCOL_NAME}", "protocolDigest": bound["protocol"]["protocolDigest"], "goldPath": f"evaluation/sprint-12/internal-poc/dense-hard-v2/{GOLD_NAME}", "goldDigest": gold["goldDigest"], "manifestPath": f"evaluation/sprint-12/internal-poc/dense-hard-v2/{MANIFEST_NAME}", "manifestDigest": manifest["manifestDigest"], "candidatePath": f"evaluation/sprint-12/internal-poc/dense-hard-v2/{CANDIDATE_NAME}", "candidateDigest": candidate["candidateDigest"], "candidateModel": candidate["candidateModel"], "providerCalls": 0, "antiLeakChecks": {"candidateDigestBound": True, "sourceDigestBound": True, "protocolDigestBound": True, "goldDigestBound": True, "manifestDigestBound": True, "candidateSourceOnlyFlagsClean": True, "goldExcludedFromCandidate": True, "providerCallsZero": True, "heldOutInspectionFalse": True, "fRfStateChanged": False}, "counts": {"caseCount": len(per_item), "entityGold": len(entity_gold), "entityCandidate": len(entity_candidate), "relationGold": len(relation_gold), "relationCandidate": len(relation_candidate), "quarantinePredicted": quarantine_predicted}, "perItemClassificationCounts": {kind: classes[kind] for kind in ("unchanged", "minor", "major", "reject", "abstain")}, "semanticEditCounts": {"total": sum(record["semanticEditCount"] for record in per_item), "meanPerCase": sum(record["semanticEditCount"] for record in per_item) / len(per_item)}, "entityMetrics": f1(entity_gold, entity_candidate), "relationMetrics": f1(relation_gold, relation_candidate), "abstentionMetrics": {"required": len(required), "predicted": len(predicted), "truePositive": len(required_ids & predicted_ids), "precision": ratio(len(required_ids & predicted_ids), len(predicted_ids)), "recall": ratio(len(required_ids & predicted_ids), len(required_ids)), "full": {"required": len(full_required), "predicted": len(full_predicted), "correct": full_tp, "precision": ratio(full_tp, len(full_predicted)), "recall": ratio(full_tp, len(full_required))}, "partial": {"required": len(partial_required), "predicted": len(partial_predicted), "correct": partial_tp, "precision": ratio(partial_tp, len(partial_predicted)), "recall": ratio(partial_tp, len(partial_required))}}, "quarantineMetrics": {"definition": "Assertion-level routing: a quarantine is correct when its exact evidence span is not a gold-finalized entity/relation span; recall is correct quarantines divided by all candidate unsupported proposals routed either to quarantine or finalization.", "predictedAssertions": quarantine_predicted, "correctAssertions": quarantine_correct, "incorrectAssertions": quarantine_incorrect, "precision": ratio(quarantine_correct, quarantine_predicted), "recall": ratio(quarantine_correct, unsafe_total), "caseLevel": {"requiredCases": q_case_required, "predictedCases": q_case_predicted, "correctCases": q_case_correct, "precision": ratio(q_case_correct, q_case_predicted), "recall": ratio(q_case_correct, q_case_required)}}, "unsafeFinalizedAssertionsAvoided": {"avoidedByQuarantine": quarantine_correct, "unsafeFinalized": unsafe_finalized, "totalUnsupportedProposals": unsafe_total, "avoidanceRate": ratio(quarantine_correct, unsafe_total)}, "unsupportedFinalizedAssertions": {"numerator": unsafe_finalized, "denominator": len(entity_candidate) + len(relation_candidate), "status": "ZERO_UNSUPPORTED" if unsafe_finalized == 0 else "UNSUPPORTED_PRESENT"}, "hallucinatedFinalizedAssertions": {"numerator": sum(record["hallucinatedFinalizedAssertions"] for record in per_item), "denominator": len(entity_candidate) + len(relation_candidate), "status": "ZERO_HALLUCINATED" if not sum(record["hallucinatedFinalizedAssertions"] for record in per_item) else "HALLUCINATED_PRESENT"}, "rm67": {"thresholds": {"acceptedWithoutSemanticCorrectionMinimum": 0.70, "acceptedUnchangedOrMinorMinimum": 0.85, "meanSemanticEditsMaximum": 2.0, "unsupportedFinalizedAssertionsMaximum": 0}, "acceptedWithoutSemanticCorrection": classes["unchanged"] / len(per_item), "acceptedUnchangedOrMinor": (classes["unchanged"] + classes["minor"]) / len(per_item), "meanSemanticEditsPerReviewedItem": sum(record["semanticEditCount"] for record in per_item) / len(per_item), "unsupportedFinalizedAssertions": {"numerator": unsafe_finalized, "denominator": len(entity_candidate) + len(relation_candidate), "status": "ZERO_UNSUPPORTED" if unsafe_finalized == 0 else "UNSUPPORTED_PRESENT"}, "editBurdenGate": classes["unchanged"] / len(per_item) >= 0.70 and (classes["unchanged"] + classes["minor"]) / len(per_item) >= 0.85 and sum(record["semanticEditCount"] for record in per_item) / len(per_item) <= 2.0 and unsafe_finalized == 0}, "perItem": per_item, "perSlice": {slice_name: aggregate(per_item, "slices", slice_name) for slice_name in sorted({slice_name for record in manifest["records"] for slice_name in record["slices"]})}, "difficultyTiers": {tier: aggregate(per_item, "difficultyTier", tier) for tier in sorted({record["difficultyTier"] for record in per_item})}, "worstCases": [{"caseId": record["caseId"], "classification": record["classification"], "semanticEditCount": record["semanticEditCount"], "unsupportedFinalizedAssertions": record["unsupportedFinalizedAssertions"], "quarantinePredicted": record["quarantinePredicted"], "errorCodes": record["errorCodes"]} for record in sorted(per_item, key=lambda item: (-item["semanticEditCount"], -item["unsupportedFinalizedAssertions"], item["caseId"]))[:5]], "errorTaxonomy": {"codes": list(ERROR_CODES), "counts": {code: sum(code in record["errorCodes"] for record in per_item) for code in ERROR_CODES}}, "v1Comparison": {"pooled": False, "v1EvaluationPath": "evaluation/sprint-12/internal-poc/dense-hard-v1/dense-hard-evaluation.v1.json", "v1EvaluationDigest": v1["evaluationDigest"], "v1CandidateDigest": v1["candidateDigest"], "v1Metrics": {"cases": v1["counts"]["caseCount"], "semanticEdits": v1["semanticEditCounts"]["total"], "entityF1": v1["entityMetrics"]["f1"], "relationF1": v1["relationMetrics"]["f1"], "unsupportedFinalizedAssertions": v1["unsupportedFinalizedAssertions"]["numerator"]}, "v2Metrics": {"cases": len(per_item), "semanticEdits": sum(record["semanticEditCount"] for record in per_item), "entityF1": f1(entity_gold, entity_candidate)["f1"], "relationF1": f1(relation_gold, relation_candidate)["f1"], "unsupportedFinalizedAssertions": unsafe_finalized}, "interpretation": "Descriptive v1-to-v2 diagnostics only; distinct packets and no evidence pooling."}, "nonClaims": ["This is an offline synthetic diagnostic, not human evidence or a production quality claim.", "No provider call, human review, external tool, held-out inspection, F-RF transition, selection, promotion, or release was performed.", "Quarantine metrics measure protocol routing of candidate unsupported proposals; they do not establish human or business quality."]}
    result["evaluationDigest"] = digest(result)
    return result


def evaluation_schema() -> dict[str, Any]:
    digest_schema = {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}
    metric = {"type": "object", "additionalProperties": False, "required": ["tp", "fp", "fn", "precision", "recall", "f1"], "properties": {"tp": {"type": "integer"}, "fp": {"type": "integer"}, "fn": {"type": "integer"}, "precision": {"type": "number"}, "recall": {"type": "number"}, "f1": {"type": "number"}}}
    anti_leak = {"type": "object", "additionalProperties": False, "required": ["candidateDigestBound", "sourceDigestBound", "protocolDigestBound", "goldDigestBound", "manifestDigestBound", "candidateSourceOnlyFlagsClean", "goldExcludedFromCandidate", "providerCallsZero", "heldOutInspectionFalse", "fRfStateChanged"], "properties": {key: {"const": True} for key in ("candidateDigestBound", "sourceDigestBound", "protocolDigestBound", "goldDigestBound", "manifestDigestBound", "candidateSourceOnlyFlagsClean", "goldExcludedFromCandidate", "providerCallsZero", "heldOutInspectionFalse") } | {"fRfStateChanged": {"const": False}}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "https://projecta.example/schemas/s12-dense-hard-evaluation.v2.json", "title": "Sprint 12 Dense-Hard Offline Evaluation v2", "type": "object", "additionalProperties": False, "required": ["artifactVersion", "status", "datasetKind", "evaluatorVersion", "evaluatorCodeDigest", "sourcePayloadPath", "sourcePayloadDigest", "protocolPath", "protocolDigest", "goldPath", "goldDigest", "manifestPath", "manifestDigest", "candidatePath", "candidateDigest", "candidateModel", "providerCalls", "antiLeakChecks", "counts", "perItemClassificationCounts", "semanticEditCounts", "entityMetrics", "relationMetrics", "abstentionMetrics", "quarantineMetrics", "unsafeFinalizedAssertionsAvoided", "unsupportedFinalizedAssertions", "hallucinatedFinalizedAssertions", "rm67", "perItem", "perSlice", "difficultyTiers", "worstCases", "errorTaxonomy", "v1Comparison", "nonClaims", "evaluationDigest"], "properties": {"artifactVersion": {"const": "s12.dense-hard.evaluation.v2"}, "status": {"const": "EVALUATED_FROZEN_CANDIDATE"}, "datasetKind": {"const": "SYNTHETIC_NON_PRODUCTION"}, "evaluatorVersion": {"const": "s12.dense-hard.evaluator.v2"}, "evaluatorCodeDigest": digest_schema, "sourcePayloadPath": {"type": "string"}, "sourcePayloadDigest": digest_schema, "protocolPath": {"type": "string"}, "protocolDigest": digest_schema, "goldPath": {"type": "string"}, "goldDigest": digest_schema, "manifestPath": {"type": "string"}, "manifestDigest": digest_schema, "candidatePath": {"type": "string"}, "candidateDigest": digest_schema, "candidateModel": {"type": "string"}, "providerCalls": {"const": 0}, "antiLeakChecks": anti_leak, "counts": {"type": "object", "additionalProperties": False, "required": ["caseCount", "entityGold", "entityCandidate", "relationGold", "relationCandidate", "quarantinePredicted"], "properties": {key: {"type": "integer", "minimum": 0} for key in ("caseCount", "entityGold", "entityCandidate", "relationGold", "relationCandidate", "quarantinePredicted")}}, "perItemClassificationCounts": {"type": "object", "additionalProperties": False, "required": ["unchanged", "minor", "major", "reject", "abstain"], "properties": {key: {"type": "integer", "minimum": 0} for key in ("unchanged", "minor", "major", "reject", "abstain")}}, "semanticEditCounts": {"type": "object", "additionalProperties": False, "required": ["total", "meanPerCase"], "properties": {"total": {"type": "integer", "minimum": 0}, "meanPerCase": {"type": "number"}}}, "entityMetrics": metric, "relationMetrics": metric, "abstentionMetrics": {"type": "object"}, "quarantineMetrics": {"type": "object"}, "unsafeFinalizedAssertionsAvoided": {"type": "object"}, "unsupportedFinalizedAssertions": {"type": "object"}, "hallucinatedFinalizedAssertions": {"type": "object"}, "rm67": {"type": "object"}, "perItem": {"type": "array", "minItems": 28, "maxItems": 28, "items": {"type": "object"}}, "perSlice": {"type": "object", "minProperties": 21, "additionalProperties": {"type": "object"}}, "difficultyTiers": {"type": "object", "minProperties": 3, "additionalProperties": {"type": "object"}}, "worstCases": {"type": "array", "minItems": 5, "maxItems": 5, "items": {"type": "object"}}, "errorTaxonomy": {"type": "object"}, "v1Comparison": {"type": "object"}, "nonClaims": {"type": "array", "items": {"type": "string"}}, "evaluationDigest": digest_schema}}


def write_immutable_evaluation(packet_dir: Path = PACKET) -> Path:
    schema_path = packet_dir / "dense-hard-evaluation.v2.schema.json"
    schema = evaluation_schema()
    schema_content = json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if schema_path.exists() and schema_path.read_text(encoding="utf-8") != schema_content:
        raise ValueError(f"immutable evaluation schema differs: {schema_path}")
    if not schema_path.exists():
        schema_path.write_text(schema_content, encoding="utf-8")
    value = evaluate(packet_dir / CANDIDATE_NAME, packet_dir)
    validate_schema(value, schema_path)
    path = packet_dir / EVALUATION_NAME
    content = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise ValueError(f"immutable evaluation differs: {path}")
    if not path.exists():
        path.write_text(content, encoding="utf-8")
    return path


def validate_evaluation_artifact(path: Path = PACKET / EVALUATION_NAME, packet_dir: Path = PACKET) -> dict[str, Any]:
    value = read(path)
    validate_schema(value, packet_dir / "dense-hard-evaluation.v2.schema.json")
    if value["evaluationDigest"] != digest({key: child for key, child in value.items() if key != "evaluationDigest"}):
        raise ValueError("evaluation digest mismatch")
    recomputed = evaluate(packet_dir / CANDIDATE_NAME, packet_dir)
    if value != recomputed:
        raise ValueError("evaluation differs from deterministic recomputation")
    return value


if __name__ == "__main__":
    print(json.dumps({"status": "WRITTEN", "path": str(write_immutable_evaluation())}, sort_keys=True))
