"""Protocol-fair v2.1 adjudication of immutable dense-hard v2 evidence."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from evaluate_s12_dense_hard_v2 import PACKET, V1_PACKET, stable
from jsonschema import Draft202012Validator

ADJUDICATION_NAME = "dense-hard-evaluation-adjudication.v2.1.json"
SCHEMA_NAME = "dense-hard-evaluation-adjudication.v2.1.schema.json"
SOURCE_NAME = "dense-hard-source-payload.v2.json"
GOLD_NAME = "dense-hard-gold.v2.json"
MANIFEST_NAME = "dense-hard-evaluator-manifest.v2.json"
CANDIDATE_NAME = "dense-hard-candidate.v2.json"
LEGACY_EVALUATION_NAME = "dense-hard-evaluation.v2.json"
MAJOR = {"relation_predicate", "relation_endpoint", "entity_missing", "entity_extra", "relation_missing", "relation_extra"}
MINOR = {"entity_label", "relation_evidence"}


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(stable(value)).hexdigest()


def span(item: dict[str, Any]) -> tuple[int, int, str]:
    evidence = item["evidence"]
    return evidence["startOffset"], evidence["endOffset"], evidence["text"]


def occurrence(entity_id: str, entities: list[dict[str, Any]]) -> tuple[int, int, str]:
    return span(next(entity for entity in entities if entity["entityId"] == entity_id))


def relation_key(relation: dict[str, Any], entities: list[dict[str, Any]]) -> tuple[Any, ...]:
    return (relation["predicate"], occurrence(relation["sourceEntityId"], entities), occurrence(relation["targetEntityId"], entities))


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


def match_entities(gold: list[dict[str, Any]], candidate: list[dict[str, Any]]) -> tuple[list[tuple[int, int]], set[int], set[int]]:
    matches: list[tuple[int, int]] = []
    used_gold: set[int] = set()
    used_candidate: set[int] = set()
    for candidate_index, item in enumerate(candidate):
        options = [index for index, expected in enumerate(gold) if index not in used_gold and span(expected) == span(item)]
        if options:
            gold_index = options[0]
            matches.append((gold_index, candidate_index))
            used_gold.add(gold_index)
            used_candidate.add(candidate_index)
    return matches, used_gold, used_candidate


def match_relations(gold: list[dict[str, Any]], candidate: list[dict[str, Any]], gold_entities: list[dict[str, Any]], candidate_entities: list[dict[str, Any]]) -> tuple[list[tuple[int, int]], set[int], set[int]]:
    matches: list[tuple[int, int]] = []
    used_gold: set[int] = set()
    used_candidate: set[int] = set()
    for candidate_index, item in enumerate(candidate):
        exact = [index for index, expected in enumerate(gold) if index not in used_gold and relation_key(expected, gold_entities) == relation_key(item, candidate_entities)]
        predicate_only = [index for index, expected in enumerate(gold) if index not in used_gold and expected["predicate"] == item["predicate"]]
        options = exact or predicate_only
        if options:
            gold_index = options[0]
            matches.append((gold_index, candidate_index))
            used_gold.add(gold_index)
            used_candidate.add(candidate_index)
    return matches, used_gold, used_candidate


def classify(expected: dict[str, Any], response: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    gold_entities, candidate_entities = expected["entities"], response["entities"]
    gold_relations, candidate_relations = expected["relations"], response["relations"]
    diffs: Counter[str] = Counter()
    entity_matches, used_gold_entities, used_candidate_entities = match_entities(gold_entities, candidate_entities)
    type_corrections = sum(gold_entities[gold_index]["type"] != candidate_entities[candidate_index]["type"] for gold_index, candidate_index in entity_matches)
    for gold_index, candidate_index in entity_matches:
        if gold_entities[gold_index]["label"] != candidate_entities[candidate_index]["label"]:
            diffs["entity_label"] += 1
    diffs["entity_missing"] = len(set(range(len(gold_entities))) - used_gold_entities)
    diffs["entity_extra"] = len(set(range(len(candidate_entities))) - used_candidate_entities)
    relation_matches, used_gold_relations, used_candidate_relations = match_relations(gold_relations, candidate_relations, gold_entities, candidate_entities)
    endpoint_corrections = 0
    for gold_index, candidate_index in relation_matches:
        expected_relation, current_relation = gold_relations[gold_index], candidate_relations[candidate_index]
        if relation_key(expected_relation, gold_entities)[1:] != relation_key(current_relation, candidate_entities)[1:]:
            diffs["relation_endpoint"] += 1
            endpoint_corrections += 1
        if span(expected_relation) != span(current_relation) or span(expected_relation["triggerEvidence"]) != span(current_relation["triggerEvidence"]):
            diffs["relation_evidence"] += 1
    diffs["relation_missing"] = len(set(range(len(gold_relations))) - used_gold_relations)
    diffs["relation_extra"] = len(set(range(len(candidate_relations))) - used_candidate_relations)
    edits = sum(diffs[key] for key in ("entity_missing", "entity_extra", "relation_endpoint", "relation_missing", "relation_extra"))
    expected_mode = expected["abstentionMode"]
    candidate_mode = response["abstention"]["mode"]
    required = expected_mode != "none"
    abstention_correct = candidate_mode == expected_mode if required else candidate_mode == "none"
    if required and candidate_mode == "none":
        classification = "reject"
        diffs["abstention_missing"] += 1
    elif not required and candidate_mode != "none":
        classification = "abstain"
        diffs["abstention_over"] += 1
    elif candidate_mode != "none":
        classification = "abstain"
        if not abstention_correct:
            diffs["abstention_mode_mismatch"] += 1
    elif any(diffs[key] for key in MAJOR):
        classification = "major"
    elif any(diffs[key] for key in MINOR):
        classification = "minor"
    else:
        classification = "unchanged"
    gold_entity_set = {(item["evidence"]["startOffset"], item["evidence"]["endOffset"], item["evidence"]["text"]) for item in gold_entities}
    candidate_entity_set = {(item["evidence"]["startOffset"], item["evidence"]["endOffset"], item["evidence"]["text"]) for item in candidate_entities}
    gold_relation_set = {relation_key(item, gold_entities) for item in gold_relations}
    candidate_relation_set = {relation_key(item, candidate_entities) for item in candidate_relations}
    unsupported = len(candidate_entity_set - gold_entity_set) + len(candidate_relation_set - gold_relation_set)
    hallucinated = len({(item["evidence"]["startOffset"], item["evidence"]["endOffset"]) for item in candidate_entities} - {(item["evidence"]["startOffset"], item["evidence"]["endOffset"]) for item in gold_entities}) + len(candidate_relation_set - gold_relation_set)
    gold_evidence = {(kind, item["evidence"]["startOffset"], item["evidence"]["endOffset"], item["evidence"]["text"]) for kind, items in (("entity", gold_entities), ("relation", gold_relations)) for item in items}
    q_correct = q_incorrect = 0
    for item in response["quarantined"]:
        kind = "entity" if item["kind"] == "entity" else "relation"
        key = (kind, item["evidence"]["startOffset"], item["evidence"]["endOffset"], item["evidence"]["text"])
        if key in gold_evidence:
            q_incorrect += 1
        else:
            q_correct += 1
    mapping = {"entity_label": "ENTITY_LABEL_MISMATCH", "entity_missing": "ENTITY_MISSING", "entity_extra": "ENTITY_EXTRA", "relation_endpoint": "RELATION_ENDPOINT_MISMATCH", "relation_missing": "RELATION_MISSING", "relation_extra": "RELATION_EXTRA", "relation_evidence": "RELATION_EVIDENCE_MISMATCH", "abstention_missing": "ABSTENTION_MISSING", "abstention_over": "ABSTENTION_OVER", "abstention_mode_mismatch": "ABSTENTION_MODE_MISMATCH"}
    errors = [mapping[key] for key in mapping if diffs[key]]
    if q_correct:
        errors.append("QUARANTINE_CORRECT")
    if q_incorrect:
        errors.append("INCORRECT_QUARANTINE")
    if unsupported:
        errors.append("UNSUPPORTED_FINALIZED_ASSERTION")
    if hallucinated:
        errors.append("HALLUCINATED_FINALIZED_ASSERTION")
    return {"caseId": manifest["caseId"], "scenarioId": manifest["scenarioId"], "slices": manifest["slices"], "difficultyTier": difficulty(manifest["caseId"]), "classification": classification, "goldAbstentionRequired": required, "expectedAbstentionMode": expected_mode, "candidateAbstentionStatus": candidate_mode, "abstentionCorrect": abstention_correct, "semanticEditCount": edits, "typeCorrections": type_corrections, "relationEndpointCorrections": endpoint_corrections, "typeDimension": "UNSCORABLE_PROTOCOL_AMBIGUITY", "unsupportedFinalizedAssertions": unsupported, "hallucinatedFinalizedAssertions": hallucinated, "quarantinePredicted": len(response["quarantined"]), "quarantineCorrect": q_correct, "quarantineIncorrect": q_incorrect, "errorCodes": errors, "entity": {"gold": len(gold_entities), "candidate": len(candidate_entities), **f1(gold_entity_set, candidate_entity_set)}, "relation": {"gold": len(gold_relations), "candidate": len(candidate_relations), **f1(gold_relation_set, candidate_relation_set)}}


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
    return {"caseCount": len(selected), "classificationCounts": {kind: Counter(record["classification"] for record in selected)[kind] for kind in ("unchanged", "minor", "major", "reject", "abstain")}, "semanticEditCount": sum(record["semanticEditCount"] for record in selected), "typeCorrections": sum(record["typeCorrections"] for record in selected), "unsupportedFinalizedAssertions": sum(record["unsupportedFinalizedAssertions"] for record in selected), "hallucinatedFinalizedAssertions": sum(record["hallucinatedFinalizedAssertions"] for record in selected), "quarantinePredicted": sum(record["quarantinePredicted"] for record in selected), "quarantineCorrect": sum(record["quarantineCorrect"] for record in selected), "quarantineIncorrect": sum(record["quarantineIncorrect"] for record in selected), "abstentionRequired": required, "abstentionPredicted": predicted, "abstentionCorrect": correct, "abstentionPrecision": ratio(correct, predicted), "abstentionRecall": ratio(correct, required), "entityMetrics": pooled("entity"), "relationMetrics": pooled("relation")}


def evaluate(packet_dir: Path = PACKET) -> dict[str, Any]:
    source = read(packet_dir / SOURCE_NAME)
    gold = read(packet_dir / GOLD_NAME)
    manifest = read(packet_dir / MANIFEST_NAME)
    candidate = read(packet_dir / CANDIDATE_NAME)
    legacy = read(packet_dir / LEGACY_EVALUATION_NAME)
    source_ids = {record["caseId"] for record in source["records"]}
    if source["payloadDigest"] != candidate["sourcePayloadDigest"] or source_ids != {record["caseId"] for record in gold["records"]} or source_ids != {response["caseId"] for response in candidate["responses"]}:
        raise ValueError("v2 adjudication bindings do not cover the same source cases")
    gold_by_id = {record["caseId"]: record["expected"] for record in gold["records"]}
    manifest_by_id = {record["caseId"]: record for record in manifest["records"]}
    candidate_by_id = {response["caseId"]: response for response in candidate["responses"]}
    per_item = [classify(gold_by_id[case_id], candidate_by_id[case_id], manifest_by_id[case_id]) for case_id in sorted(source_ids)]
    entity_gold = {(case_id, item["evidence"]["startOffset"], item["evidence"]["endOffset"], item["evidence"]["text"]) for case_id, expected in gold_by_id.items() for item in expected["entities"]}
    entity_candidate = {(case_id, item["evidence"]["startOffset"], item["evidence"]["endOffset"], item["evidence"]["text"]) for case_id, response in candidate_by_id.items() for item in response["entities"]}
    relation_gold = {(case_id, *relation_key(item, expected["entities"])) for case_id, expected in gold_by_id.items() for item in expected["relations"]}
    relation_candidate = {(case_id, *relation_key(item, response["entities"])) for case_id, response in candidate_by_id.items() for item in response["relations"]}
    classes = Counter(record["classification"] for record in per_item)
    required = [record for record in per_item if record["goldAbstentionRequired"]]
    predicted = [record for record in per_item if record["candidateAbstentionStatus"] != "none"]
    correct_ids = {record["caseId"] for record in required if record["abstentionCorrect"]}
    full_required = [record for record in required if record["expectedAbstentionMode"] == "full"]
    partial_required = [record for record in required if record["expectedAbstentionMode"] == "partial"]
    full_predicted = [record for record in predicted if record["candidateAbstentionStatus"] == "full"]
    partial_predicted = [record for record in predicted if record["candidateAbstentionStatus"] == "partial"]
    full_correct = sum(record["abstentionCorrect"] and record["expectedAbstentionMode"] == "full" for record in per_item)
    partial_correct = sum(record["abstentionCorrect"] and record["expectedAbstentionMode"] == "partial" for record in per_item)
    q_correct = sum(record["quarantineCorrect"] for record in per_item)
    q_incorrect = sum(record["quarantineIncorrect"] for record in per_item)
    unsafe_finalized = sum(record["unsupportedFinalizedAssertions"] for record in per_item)
    unsafe_total = q_correct + unsafe_finalized
    fair_edits = sum(record["semanticEditCount"] for record in per_item)
    fair_entity = f1(entity_gold, entity_candidate)
    fair_relation = f1(relation_gold, relation_candidate)
    fair_unsupported = {"numerator": unsafe_finalized, "denominator": len(entity_candidate) + len(relation_candidate), "status": "ZERO_UNSUPPORTED" if unsafe_finalized == 0 else "UNSUPPORTED_PRESENT"}
    fair_hallucinated_count = sum(record["hallucinatedFinalizedAssertions"] for record in per_item)
    fair_hallucinated = {"numerator": fair_hallucinated_count, "denominator": len(entity_candidate) + len(relation_candidate), "status": "ZERO_HALLUCINATED" if fair_hallucinated_count == 0 else "HALLUCINATED_PRESENT"}
    fair_rm67 = {"thresholds": {"acceptedWithoutSemanticCorrectionMinimum": 0.70, "acceptedUnchangedOrMinorMinimum": 0.85, "meanSemanticEditsMaximum": 2.0, "unsupportedFinalizedAssertionsMaximum": 0}, "acceptedWithoutSemanticCorrection": ratio(classes["unchanged"], len(per_item)), "acceptedUnchangedOrMinor": ratio(classes["unchanged"] + classes["minor"], len(per_item)), "meanSemanticEditsPerReviewedItem": ratio(fair_edits, len(per_item)), "unsupportedFinalizedAssertions": fair_unsupported, "editBurdenGate": classes["unchanged"] / len(per_item) >= 0.70 and (classes["unchanged"] + classes["minor"]) / len(per_item) >= 0.85 and fair_edits / len(per_item) <= 2.0 and unsafe_finalized == 0}
    legacy_view = {key: legacy[key] for key in ("evaluationDigest", "candidateDigest", "perItemClassificationCounts", "semanticEditCounts", "entityMetrics", "relationMetrics", "abstentionMetrics", "quarantineMetrics", "unsafeFinalizedAssertionsAvoided", "unsupportedFinalizedAssertions", "hallucinatedFinalizedAssertions", "rm67") if key in legacy}
    audit_examples = {}
    for case_id in ("dh2-001", "dh2-002", "dh2-006", "dh2-017", "dh2-022"):
        legacy_item = next(item for item in legacy["perItem"] if item["caseId"] == case_id)
        fair_item = next(item for item in per_item if item["caseId"] == case_id)
        audit_examples[case_id] = {"legacyStrict": legacy_item, "protocolFair": fair_item, "deltas": {"semanticEditCount": fair_item["semanticEditCount"] - legacy_item["semanticEditCount"], "unsupportedFinalizedAssertions": fair_item["unsupportedFinalizedAssertions"] - legacy_item["unsupportedFinalizedAssertions"], "hallucinatedFinalizedAssertions": fair_item["hallucinatedFinalizedAssertions"] - legacy_item["hallucinatedFinalizedAssertions"], "typeCorrectionsExcluded": fair_item["typeCorrections"]}}
    fair_view = {"typeDimension": {"status": "UNSCORABLE_PROTOCOL_AMBIGUITY", "corrections": sum(record["typeCorrections"] for record in per_item), "excludedFromPassFail": True}, "perItemClassificationCounts": {kind: classes[kind] for kind in ("unchanged", "minor", "major", "reject", "abstain")}, "semanticEditCounts": {"total": fair_edits, "meanPerCase": ratio(fair_edits, len(per_item))}, "entityMetrics": fair_entity, "relationMetrics": fair_relation, "abstentionMetrics": {"required": len(required), "predicted": len(predicted), "truePositive": len(correct_ids), "precision": ratio(len(correct_ids), len(predicted)), "recall": ratio(len(correct_ids), len(required)), "full": {"required": len(full_required), "predicted": len(full_predicted), "correct": full_correct, "precision": ratio(full_correct, len(full_predicted)), "recall": ratio(full_correct, len(full_required))}, "partial": {"required": len(partial_required), "predicted": len(partial_predicted), "correct": partial_correct, "precision": ratio(partial_correct, len(partial_predicted)), "recall": ratio(partial_correct, len(partial_required))}}, "quarantineMetrics": {"predictedAssertions": sum(record["quarantinePredicted"] for record in per_item), "correctAssertions": q_correct, "incorrectAssertions": q_incorrect, "precision": ratio(q_correct, q_correct + q_incorrect), "recall": ratio(q_correct, unsafe_total), "caseLevel": {"requiredCases": len(required), "predictedCases": sum(record["quarantinePredicted"] > 0 for record in per_item), "correctCases": sum(record["goldAbstentionRequired"] and record["quarantinePredicted"] > 0 for record in per_item), "precision": ratio(sum(record["goldAbstentionRequired"] and record["quarantinePredicted"] > 0 for record in per_item), sum(record["quarantinePredicted"] > 0 for record in per_item)), "recall": ratio(sum(record["goldAbstentionRequired"] and record["quarantinePredicted"] > 0 for record in per_item), len(required))}}, "unsafeFinalizedAssertionsAvoided": {"avoidedByQuarantine": q_correct, "unsafeFinalized": unsafe_finalized, "totalUnsupportedProposals": unsafe_total, "avoidanceRate": ratio(q_correct, unsafe_total)}, "unsupportedFinalizedAssertions": fair_unsupported, "hallucinatedFinalizedAssertions": fair_hallucinated, "rm67": fair_rm67, "perItem": per_item, "perSlice": {slice_name: aggregate(per_item, "slices", slice_name) for slice_name in sorted({slice_name for record in manifest["records"] for slice_name in record["slices"]})}, "difficultyTiers": {tier: aggregate(per_item, "difficultyTier", tier) for tier in sorted({record["difficultyTier"] for record in per_item})}, "worstCases": [{"caseId": record["caseId"], "classification": record["classification"], "semanticEditCount": record["semanticEditCount"], "typeCorrections": record["typeCorrections"], "unsupportedFinalizedAssertions": record["unsupportedFinalizedAssertions"], "errorCodes": record["errorCodes"]} for record in sorted(per_item, key=lambda item: (-item["semanticEditCount"], -item["unsupportedFinalizedAssertions"], item["caseId"]))[:5]]}
    result = {"artifactVersion": "s12.dense-hard.evaluation-adjudication.v2.1", "status": "ADJUDICATED_IMMUTABLE_V2", "datasetKind": "SYNTHETIC_NON_PRODUCTION", "adjudicatorVersion": "s12.dense-hard.adjudicator.v2.1", "sourcePayloadDigest": source["payloadDigest"], "protocolDigest": candidate["protocolDigest"], "goldDigest": gold["goldDigest"], "manifestDigest": manifest["manifestDigest"], "candidateDigest": candidate["candidateDigest"], "originalEvaluationPath": f"evaluation/sprint-12/internal-poc/dense-hard-v2/{LEGACY_EVALUATION_NAME}", "originalEvaluationDigest": legacy["evaluationDigest"], "protocolFairRule": "Anchored occurrence identity is (start,end,text); relation identity is predicate plus anchored endpoint occurrences; entity type is retained only as UNSCORABLE_PROTOCOL_AMBIGUITY because v2 published no semantic type rubric.", "legacyStrict": legacy_view, "protocolFair": fair_view, "v1Comparison": {"pooled": False, "v1EvaluationPath": "evaluation/sprint-12/internal-poc/dense-hard-v1/dense-hard-evaluation.v1.json", "v1EvaluationDigest": read(V1_PACKET / "dense-hard-evaluation.v1.json")["evaluationDigest"], "legacyStrictEvaluationDigest": legacy["evaluationDigest"], "protocolFairExcludesTypeFromPassFail": True, "comparison": {"legacyStrict": {"semanticEdits": legacy["semanticEditCounts"]["total"], "entityF1": legacy["entityMetrics"]["f1"], "relationF1": legacy["relationMetrics"]["f1"], "unsupportedFinalizedAssertions": legacy["unsupportedFinalizedAssertions"]["numerator"]}, "protocolFair": {"semanticEdits": fair_edits, "entityF1": fair_entity["f1"], "relationF1": fair_relation["f1"], "unsupportedFinalizedAssertions": unsafe_finalized}}}, "auditExamples": audit_examples, "nonClaims": ["This adjudication is an offline synthetic diagnostic, not human or business-quality evidence.", "Protocol-fair type ambiguity is not treated as a correct or incorrect semantic type decision.", "No provider, human, external, held-out, production, selection, promotion, or release claim is made."]}
    result["adjudicationDigest"] = digest(result)
    return result


def schema() -> dict[str, Any]:
    digest_schema = {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "https://projecta.example/schemas/s12-dense-hard-evaluation-adjudication.v2.1.json", "title": "Sprint 12 Dense-Hard v2.1 Protocol-Fair Adjudication", "type": "object", "additionalProperties": False, "required": ["artifactVersion", "status", "datasetKind", "adjudicatorVersion", "sourcePayloadDigest", "protocolDigest", "goldDigest", "manifestDigest", "candidateDigest", "originalEvaluationPath", "originalEvaluationDigest", "protocolFairRule", "legacyStrict", "protocolFair", "v1Comparison", "auditExamples", "nonClaims", "adjudicationDigest"], "properties": {"artifactVersion": {"const": "s12.dense-hard.evaluation-adjudication.v2.1"}, "status": {"const": "ADJUDICATED_IMMUTABLE_V2"}, "datasetKind": {"const": "SYNTHETIC_NON_PRODUCTION"}, "adjudicatorVersion": {"const": "s12.dense-hard.adjudicator.v2.1"}, "sourcePayloadDigest": digest_schema, "protocolDigest": digest_schema, "goldDigest": digest_schema, "manifestDigest": digest_schema, "candidateDigest": digest_schema, "originalEvaluationPath": {"type": "string"}, "originalEvaluationDigest": digest_schema, "protocolFairRule": {"type": "string"}, "legacyStrict": {"type": "object"}, "protocolFair": {"type": "object"}, "v1Comparison": {"type": "object"}, "auditExamples": {"type": "object", "minProperties": 5, "additionalProperties": {"type": "object"}}, "nonClaims": {"type": "array", "items": {"type": "string"}}, "adjudicationDigest": digest_schema}}


def write_immutable(packet_dir: Path = PACKET) -> Path:
    schema_path = packet_dir / SCHEMA_NAME
    schema_value = schema()
    schema_text = json.dumps(schema_value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if schema_path.exists() and schema_path.read_text(encoding="utf-8") != schema_text:
        raise ValueError(f"immutable adjudication schema differs: {schema_path}")
    if not schema_path.exists():
        schema_path.write_text(schema_text, encoding="utf-8")
    value = evaluate(packet_dir)
    Draft202012Validator.check_schema(schema_value)
    Draft202012Validator(schema_value).validate(value)
    path = packet_dir / ADJUDICATION_NAME
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != text:
        raise ValueError(f"immutable adjudication differs: {path}")
    if not path.exists():
        path.write_text(text, encoding="utf-8")
    return path


def validate_artifact(path: Path = PACKET / ADJUDICATION_NAME, packet_dir: Path = PACKET) -> dict[str, Any]:
    value = read(path)
    schema_value = schema()
    Draft202012Validator.check_schema(schema_value)
    Draft202012Validator(schema_value).validate(value)
    if value["adjudicationDigest"] != digest({key: child for key, child in value.items() if key != "adjudicationDigest"}):
        raise ValueError("adjudication digest mismatch")
    recomputed = evaluate(packet_dir)
    if value != recomputed:
        raise ValueError("adjudication differs from deterministic recomputation")
    return value


if __name__ == "__main__":
    print(json.dumps({"status": "WRITTEN", "path": str(write_immutable())}, sort_keys=True))
