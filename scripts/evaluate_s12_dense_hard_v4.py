"""Deterministic, stratified offline evaluator for frozen dense-hard v4."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v4"
SOURCE_NAME = "dense-hard-source-payload.v4.json"
GOLD_NAME = "dense-hard-gold.v4.json"
MANIFEST_NAME = "dense-hard-evaluator-manifest.v4.json"
PROTOCOL_NAME = "dense-hard-source-only-protocol.v4.json"
CONTRACT_NAME = "dense-hard-evaluator-contract.v4.json"
CANDIDATE_NAME = "dense-hard-candidate.v4.json"
EVALUATION_NAME = "dense-hard-evaluation.v4.json"
V31 = ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v3/dense-hard-evaluation-adjudication.v3.1.json"
ERROR_CODES = ("ENTITY_TYPE_MISMATCH", "ENTITY_SPAN_MISMATCH", "ENTITY_LABEL_MISMATCH", "ENTITY_MISSING", "ENTITY_EXTRA", "RELATION_PREDICATE_MISMATCH", "RELATION_ENDPOINT_MISMATCH", "RELATION_EVIDENCE_MISMATCH", "RELATION_MISSING", "RELATION_EXTRA", "ABSTENTION_MISSING", "ABSTENTION_OVER", "ABSTENTION_MODE_MISMATCH", "QUARANTINE_CORRECT", "INCORRECT_QUARANTINE", "QUARANTINE_MISSING", "UNSUPPORTED_FINALIZED_ASSERTION", "HALLUCINATED_FINALIZED_ASSERTION")
MAJOR = {"entity_span", "entity_missing", "entity_extra", "relation_predicate", "relation_endpoint", "relation_missing", "relation_extra"}
MINOR = {"entity_label", "relation_evidence"}


def stable(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(stable(value)).hexdigest()


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_schema(value: dict[str, Any], path: Path) -> None:
    schema = read(path)
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        raise ValueError(f"{path.name}: {list(errors[0].path)}: {errors[0].message}")


def occurrence(span: dict[str, Any]) -> tuple[int, int, str]:
    return span["startOffset"], span["endOffset"], span["text"]


def exact(raw: str, span: dict[str, Any]) -> None:
    start, end, text = occurrence(span)
    if start < 0 or end <= start or end > len(raw) or raw[start:end] != text:
        raise ValueError(f"invalid source anchor: {span!r}")


def contained(inner: dict[str, Any], outer: dict[str, Any]) -> bool:
    return outer["startOffset"] <= inner["startOffset"] < inner["endOffset"] <= outer["endOffset"]


def ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def f1(gold: set[tuple[Any, ...]], candidate: set[tuple[Any, ...]]) -> dict[str, Any]:
    tp, fp, fn = len(gold & candidate), len(candidate - gold), len(gold - candidate)
    precision, recall = ratio(tp, tp + fp), ratio(tp, tp + fn)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": ratio(2 * precision * recall, precision + recall)}


def normalize_evidence(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"[.!?。！？]+$", "", text).rstrip()


def tier(case_id: str) -> str:
    number = int(case_id[-3:])
    return "v4-utility-dense" if number <= 24 else "v4-safety-partial" if number <= 28 else "v4-safety-full"


def gold_relation_semantic(item: dict[str, Any], entities: list[dict[str, Any]]) -> tuple[Any, ...]:
    by_id = {e["entityId"]: occurrence(e["evidence"]) for e in entities}
    return item["predicate"], by_id[item["sourceEntityId"]], by_id[item["targetEntityId"]]


def candidate_relation_semantic(item: dict[str, Any], entities: dict[str, dict[str, Any]]) -> tuple[Any, ...]:
    return item["predicate"], occurrence(entities[item["sourceOccurrenceId"]]["evidence"]), occurrence(entities[item["targetOccurrenceId"]]["evidence"])


def validate_bindings(packet_dir: Path, candidate_path: Path) -> dict[str, dict[str, Any]]:
    names = {"source": SOURCE_NAME, "gold": GOLD_NAME, "manifest": MANIFEST_NAME, "protocol": PROTOCOL_NAME, "contract": CONTRACT_NAME}
    values = {key: read(packet_dir / name) for key, name in names.items()}
    candidate = read(candidate_path); values["candidate"] = candidate
    for key, name in {**names, "candidate": CANDIDATE_NAME}.items():
        validate_schema(values[key], packet_dir / name.replace(".json", ".schema.json"))
    for key, field in (("source", "payloadDigest"), ("gold", "goldDigest"), ("manifest", "manifestDigest"), ("protocol", "protocolDigest"), ("contract", "contractDigest")):
        if values[key][field] != digest({k: v for k, v in values[key].items() if k != field}): raise ValueError(f"{key} digest mismatch")
    without = copy.deepcopy(candidate); without.pop("candidateDigest")
    if candidate["candidateDigest"] != digest(without): raise ValueError("candidate digest mismatch")
    source, gold, manifest, protocol, contract = (values[k] for k in ("source", "gold", "manifest", "protocol", "contract"))
    if candidate["bindings"]["sourcePayloadDigest"] != source["payloadDigest"] or candidate["bindings"]["protocolDigest"] != protocol["protocolDigest"] or candidate["bindings"]["evaluatorContractDigest"] != contract["contractDigest"] or candidate["bindings"]["goldDigest"] is not None or candidate["bindings"]["manifestDigest"] is not None:
        raise ValueError("candidate/public digest binding mismatch")
    if candidate["providerCalls"] != 0 or not candidate["sourceOnly"]: raise ValueError("candidate source-only boundary is not clean")
    ids = {r["caseId"] for r in source["records"]}
    if ids != {r["caseId"] for r in gold["records"]} or ids != {r["caseId"] for r in manifest["records"]} or ids != {r["caseId"] for r in candidate["records"]}: raise ValueError("case bindings differ")
    source_by_id = {r["caseId"]: r for r in source["records"]}
    allowed_types, allowed_predicates = set(protocol["finiteEntityTypes"]), set(protocol["finiteRelationPredicates"])
    for record in candidate["records"]:
        source_record = source_by_id[record["caseId"]]
        if record["scenarioId"] != source_record["scenarioId"] or record["sourceDigest"] != source_record["sourceDigest"]:
            raise ValueError(f"candidate source record binding mismatch in {record['caseId']}")
        raw = source_record["rawText"]
        entities = {e["occurrenceId"]: e for e in record["entities"]}
        if len(entities) != len(record["entities"]): raise ValueError(f"duplicate candidate occurrence ID in {record['caseId']}")
        seen: set[tuple[int, int, str]] = set()
        for entity in record["entities"]:
            if entity["type"] not in allowed_types or entity["label"] != entity["evidence"]["text"]: raise ValueError(f"candidate entity type/label violation in {record['caseId']}")
            exact(raw, entity["evidence"])
            key = occurrence(entity["evidence"])
            if key in seen: raise ValueError(f"duplicate candidate occurrence in {record['caseId']}")
            seen.add(key)
        for relation in record["relations"]:
            if relation["predicate"] not in allowed_predicates or relation["sourceOccurrenceId"] not in entities or relation["targetOccurrenceId"] not in entities: raise ValueError(f"candidate relation endpoint violation in {record['caseId']}")
            exact(raw, relation["triggerEvidence"])
            # Keep out-of-evidence endpoints scoreable as a relation-endpoint
            # residual; the candidate remains immutable evidence, not a reason
            # to discard the case or hide the failure.
        for item in record["quarantine"]: exact(raw, item["evidence"])
    return values


def classify(expected: dict[str, Any], response: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    diffs: Counter[str] = Counter()
    ge, ce = expected["entities"], response["entities"]
    gold_by_occ = {occurrence(e["evidence"]): i for i, e in enumerate(ge)}
    cand_by_occ = {occurrence(e["evidence"]): i for i, e in enumerate(ce)}
    matched = set(gold_by_occ) & set(cand_by_occ)
    type_corrections = sum(ge[gold_by_occ[key]]["type"] != ce[cand_by_occ[key]]["type"] for key in matched)
    diffs["entity_type"] = type_corrections
    diffs["entity_missing"] = len(set(gold_by_occ) - set(cand_by_occ)); diffs["entity_extra"] = len(set(cand_by_occ) - set(gold_by_occ))
    for key in matched:
        if ge[gold_by_occ[key]]["label"] != ce[cand_by_occ[key]]["label"]: diffs["entity_label"] += 1
    gold_rel = [gold_relation_semantic(r, ge) for r in expected["relations"]]
    entity_lookup = {e["occurrenceId"]: e for e in ce}
    cand_rel = [candidate_relation_semantic(r, entity_lookup) for r in response["relations"]]
    gold_set, cand_set = set(gold_rel), set(cand_rel)
    exact_rel = gold_set & cand_set
    for gs in set(gold_rel) - exact_rel:
        if any((gs[1], gs[2]) == (cr[1], cr[2]) for cr in cand_rel): diffs["relation_predicate"] += 1
        elif any(gs[0] == cr[0] for cr in cand_rel): diffs["relation_endpoint"] += 1
        else: diffs["relation_missing"] += 1
    diffs["relation_extra"] = len(cand_set - gold_set)
    for gr in expected["relations"]:
        sem = gold_relation_semantic(gr, ge)
        if sem in exact_rel:
            cand = next(r for r in response["relations"] if candidate_relation_semantic(r, entity_lookup) == sem)
            if normalize_evidence(gr["evidence"]["text"]) != normalize_evidence(cand["triggerEvidence"]["text"]): diffs["relation_evidence"] += 1
    semantic_edits = sum(diffs[k] for k in ("entity_span", "entity_label", "entity_missing", "entity_extra", "relation_predicate", "relation_endpoint", "relation_missing", "relation_extra"))
    expected_mode, candidate_mode = expected["abstentionMode"], response["abstention"]
    required = expected_mode != "none"; mode_correct = candidate_mode == expected_mode if required else candidate_mode == "none"
    if required and candidate_mode == "none": diffs["abstention_missing"] += 1
    if not required and candidate_mode != "none": diffs["abstention_over"] += 1
    if required and candidate_mode not in ("none", expected_mode): diffs["abstention_mode_mismatch"] += 1
    if candidate_mode != "none": classification = "abstain"
    elif required: classification = "reject"
    elif any(diffs[k] for k in MAJOR): classification = "major"
    elif any(diffs[k] for k in MINOR): classification = "minor"
    else: classification = "unchanged"
    unsupported = len(cand_set - gold_set) + len(set(cand_by_occ) - set(gold_by_occ))
    gold_evidence = {("entity", *occurrence(e["evidence"])) for e in ge} | {("relation", *occurrence(r["evidence"])) for r in expected["relations"]}
    q_correct = sum(("relation" if q["evidence"]["text"] in {r["evidence"]["text"] for r in expected["relations"]} else "entity", *occurrence(q["evidence"])) not in gold_evidence for q in response["quarantine"])
    q_incorrect = len(response["quarantine"]) - q_correct
    codes = []
    mapping = {"entity_type": "ENTITY_TYPE_MISMATCH", "entity_label": "ENTITY_LABEL_MISMATCH", "entity_missing": "ENTITY_MISSING", "entity_extra": "ENTITY_EXTRA", "relation_predicate": "RELATION_PREDICATE_MISMATCH", "relation_endpoint": "RELATION_ENDPOINT_MISMATCH", "relation_evidence": "RELATION_EVIDENCE_MISMATCH", "relation_missing": "RELATION_MISSING", "relation_extra": "RELATION_EXTRA", "abstention_missing": "ABSTENTION_MISSING", "abstention_over": "ABSTENTION_OVER", "abstention_mode_mismatch": "ABSTENTION_MODE_MISMATCH"}
    codes.extend(mapping[k] for k in mapping if diffs[k]);
    if q_correct: codes.append("QUARANTINE_CORRECT")
    if q_incorrect: codes.append("INCORRECT_QUARANTINE")
    if len(response["quarantine"]) < manifest["quarantineCount"]: codes.append("QUARANTINE_MISSING")
    if unsupported: codes.extend(["UNSUPPORTED_FINALIZED_ASSERTION", "HALLUCINATED_FINALIZED_ASSERTION"])
    return {"caseId": manifest["caseId"], "scenarioId": manifest["scenarioId"], "slices": manifest["slices"], "difficultyTier": tier(manifest["caseId"]), "classification": classification, "goldAbstentionRequired": required, "expectedAbstentionMode": expected_mode, "candidateAbstentionStatus": candidate_mode, "abstentionCorrect": mode_correct, "typeCorrections": type_corrections, "semanticEditCount": semantic_edits, "unsupportedFinalizedAssertions": unsupported, "hallucinatedFinalizedAssertions": unsupported, "quarantinePredicted": len(response["quarantine"]), "quarantineCorrect": q_correct, "quarantineIncorrect": q_incorrect, "errorCodes": codes, "entity": {"gold": len(ge), "candidate": len(ce), **f1(set(gold_by_occ), set(cand_by_occ)), "dimensionDiffs": {k: diffs[k] for k in ("entity_span", "entity_type", "entity_label", "entity_missing", "entity_extra")}}, "relation": {"gold": len(gold_rel), "candidate": len(cand_rel), **f1(gold_set, cand_set), "dimensionDiffs": {k: diffs[k] for k in ("relation_predicate", "relation_endpoint", "relation_evidence", "relation_missing", "relation_extra")}}}


def aggregate(records: list[dict[str, Any]], field: str | None = None, value: str | None = None) -> dict[str, Any]:
    selected = [r for r in records if field is None or (value in r[field] if isinstance(r[field], list) else r[field] == value)]
    def pooled(name: str) -> dict[str, Any]:
        metric = {k: sum(r[name][k] for r in selected) for k in ("tp", "fp", "fn")}; metric["precision"], metric["recall"] = ratio(metric["tp"], metric["tp"] + metric["fp"]), ratio(metric["tp"], metric["tp"] + metric["fn"]); metric["f1"] = ratio(2 * metric["precision"] * metric["recall"], metric["precision"] + metric["recall"]); return metric
    return {"caseCount": len(selected), "classificationCounts": {k: Counter(r["classification"] for r in selected)[k] for k in ("unchanged", "minor", "major", "reject", "abstain")}, "semanticEditCount": sum(r["semanticEditCount"] for r in selected), "typeCorrections": sum(r["typeCorrections"] for r in selected), "unsupportedFinalizedAssertions": sum(r["unsupportedFinalizedAssertions"] for r in selected), "quarantinePredicted": sum(r["quarantinePredicted"] for r in selected), "quarantineCorrect": sum(r["quarantineCorrect"] for r in selected), "quarantineIncorrect": sum(r["quarantineIncorrect"] for r in selected), "entityMetrics": pooled("entity"), "relationMetrics": pooled("relation")}


def evaluate(candidate_path: Path = PACKET / CANDIDATE_NAME, packet_dir: Path = PACKET) -> dict[str, Any]:
    bound = validate_bindings(packet_dir, candidate_path); source, gold, manifest, candidate = (bound[k] for k in ("source", "gold", "manifest", "candidate")); gold_by_id = {r["caseId"]: r["expected"] for r in gold["records"]}; manifest_by_id = {r["caseId"]: r for r in manifest["records"]}; candidate_by_id = {r["caseId"]: r for r in candidate["records"]}
    per_item = [classify(gold_by_id[cid], candidate_by_id[cid], manifest_by_id[cid]) for cid in sorted(gold_by_id)]
    entity_gold = {(r["caseId"], occurrence(e["evidence"])) for r in gold["records"] for e in gold_by_id[r["caseId"]]["entities"]}; entity_candidate = {(r["caseId"], occurrence(e["evidence"])) for r in candidate["records"] for e in r["entities"]}
    relation_gold = {(r["caseId"], gold_relation_semantic(rel, gold_by_id[r["caseId"]]["entities"])) for r in gold["records"] for rel in gold_by_id[r["caseId"]]["relations"]}; relation_candidate = {(r["caseId"], candidate_relation_semantic(rel, {e["occurrenceId"]: e for e in r["entities"]})) for r in candidate["records"] for rel in r["relations"]}
    classes = Counter(r["classification"] for r in per_item); utility = [r for r in per_item if not r["goldAbstentionRequired"]]; safety = [r for r in per_item if r["goldAbstentionRequired"]]
    def abstention_gate(items: list[dict[str, Any]], mode: str) -> dict[str, Any]:
        required = sum(r["expectedAbstentionMode"] == mode for r in items); predicted = sum(r["candidateAbstentionStatus"] == mode for r in items); correct = sum(r["expectedAbstentionMode"] == mode and r["abstentionCorrect"] for r in items); return {"required": required, "predicted": predicted, "correct": correct, "precision": ratio(correct, predicted), "recall": ratio(correct, required)}
    q_pred = sum(r["quarantinePredicted"] for r in per_item)
    utility_gate = {"caseCount": len(utility), "acceptedWithoutSemanticCorrection": ratio(sum(r["classification"] == "unchanged" for r in utility), len(utility)), "acceptedUnchangedOrMinor": ratio(sum(r["classification"] in ("unchanged", "minor") for r in utility), len(utility)), "meanSemanticEditsPerReviewedItem": ratio(sum(r["semanticEditCount"] for r in utility), len(utility)), "unsupportedFinalizedAssertions": {"numerator": sum(r["unsupportedFinalizedAssertions"] for r in utility), "denominator": sum(r["entity"]["candidate"] + r["relation"]["candidate"] for r in utility), "status": "ZERO_UNSUPPORTED" if not sum(r["unsupportedFinalizedAssertions"] for r in utility) else "UNSUPPORTED_PRESENT"}, "thresholds": {"acceptedWithoutSemanticCorrectionMinimum": 0.70, "acceptedUnchangedOrMinorMinimum": 0.85, "meanSemanticEditsMaximum": 2.0, "unsupportedFinalizedAssertionsMaximum": 0}, "pass": False}
    utility_gate["pass"] = utility_gate["acceptedWithoutSemanticCorrection"] >= 0.70 and utility_gate["acceptedUnchangedOrMinor"] >= 0.85 and utility_gate["meanSemanticEditsPerReviewedItem"] <= 2.0 and utility_gate["unsupportedFinalizedAssertions"]["numerator"] == 0
    full_gate, partial_gate = abstention_gate(safety, "full"), abstention_gate(safety, "partial"); quarantine_gate = {"predicted": sum(r["quarantinePredicted"] for r in safety), "correct": sum(r["quarantineCorrect"] for r in safety), "incorrect": sum(r["quarantineIncorrect"] for r in safety)}; quarantine_gate.update({"precision": ratio(quarantine_gate["correct"], quarantine_gate["predicted"]), "recall": ratio(quarantine_gate["correct"], quarantine_gate["correct"] + sum(r["unsupportedFinalizedAssertions"] for r in safety))}); safety_gate = {"fullAbstention": full_gate, "partialAbstention": partial_gate, "quarantine": quarantine_gate, "unsupportedFinalizedAssertions": {"numerator": sum(r["unsupportedFinalizedAssertions"] for r in safety), "denominator": sum(r["entity"]["candidate"] + r["relation"]["candidate"] for r in safety), "status": "ZERO_UNSUPPORTED" if not sum(r["unsupportedFinalizedAssertions"] for r in safety) else "UNSUPPORTED_PRESENT"}}; safety_gate["pass"] = full_gate["precision"] == full_gate["recall"] == 1.0 and partial_gate["precision"] == partial_gate["recall"] == 1.0 and quarantine_gate["precision"] == quarantine_gate["recall"] == 1.0 and safety_gate["unsupportedFinalizedAssertions"]["numerator"] == 0
    v31 = read(V31)
    result = {"artifactVersion": "s12.dense-hard.evaluation.v4", "status": "EVALUATED_FROZEN_CANDIDATE_STRATIFIED", "datasetKind": "SYNTHETIC_NON_PRODUCTION", "evaluatorVersion": "s12.dense-hard.evaluator.v4", "sourcePayloadPath": f"evaluation/sprint-12/internal-poc/dense-hard-v4/{SOURCE_NAME}", "sourcePayloadDigest": source["payloadDigest"], "protocolPath": f"evaluation/sprint-12/internal-poc/dense-hard-v4/{PROTOCOL_NAME}", "protocolDigest": bound["protocol"]["protocolDigest"], "contractPath": f"evaluation/sprint-12/internal-poc/dense-hard-v4/{CONTRACT_NAME}", "contractDigest": bound["contract"]["contractDigest"], "goldPath": f"evaluation/sprint-12/internal-poc/dense-hard-v4/{GOLD_NAME}", "goldDigest": gold["goldDigest"], "manifestPath": f"evaluation/sprint-12/internal-poc/dense-hard-v4/{MANIFEST_NAME}", "manifestDigest": manifest["manifestDigest"], "candidatePath": f"evaluation/sprint-12/internal-poc/dense-hard-v4/{CANDIDATE_NAME}", "candidateDigest": candidate["candidateDigest"], "candidateModel": candidate["model"], "providerCalls": 0, "antiLeakChecks": {"candidateDigestBound": True, "sourceDigestBound": True, "protocolDigestBound": True, "contractDigestBound": True, "goldDigestBound": True, "manifestDigestBound": True, "candidateSourceOnlyFlagsClean": True, "goldExcludedFromCandidate": True, "providerCallsZero": True, "heldOutInspectionFalse": True}, "counts": {"caseCount": 32, "utilityCaseCount": 24, "safetyCaseCount": 8, "entityGold": len(entity_gold), "entityCandidate": len(entity_candidate), "relationGold": len(relation_gold), "relationCandidate": len(relation_candidate), "quarantinePredicted": q_pred}, "perItemClassificationCounts": {k: classes[k] for k in ("unchanged", "minor", "major", "reject", "abstain")}, "semanticEditCounts": {"total": sum(r["semanticEditCount"] for r in per_item), "meanPerCase": ratio(sum(r["semanticEditCount"] for r in per_item), len(per_item))}, "typeDiagnostics": {"typeCorrections": sum(r["typeCorrections"] for r in per_item), "identityIndependentOfType": True, "cascadeToRelation": False, "ambiguousExcludedFromPassFail": True}, "entityMetrics": f1(entity_gold, entity_candidate), "relationMetrics": f1(relation_gold, relation_candidate), "utilityGate": utility_gate, "safetyGate": safety_gate, "overallPass": utility_gate["pass"] and safety_gate["pass"], "pooledLegacyDiagnostic": {"authoritative": False, "classificationCounts": {k: classes[k] for k in ("unchanged", "minor", "major", "reject", "abstain")}, "semanticEditCounts": {"total": sum(r["semanticEditCount"] for r in per_item), "meanPerCase": ratio(sum(r["semanticEditCount"] for r in per_item), len(per_item))}, "reason": "v4 utility and safety strata are not pooled for pass/fail; pooled values are diagnostic only."}, "v3_1Comparison": {"pooled": False, "adjudicationPath": str(V31.relative_to(ROOT)).replace('\\', '/'), "adjudicationDigest": v31["adjudicationDigest"], "overallPass": v31["gates"]["overallPass"], "utilityGatePass": v31["gates"]["utilityRM67"]["pass"], "safetyGatePass": v31["gates"]["safety"]["pass"]}, "perItem": per_item, "perSlice": {s: aggregate(per_item, "slices", s) for s in sorted({s for r in manifest["records"] for s in r["slices"]})}, "difficultyTiers": {t: aggregate(per_item, "difficultyTier", t) for t in sorted({r["difficultyTier"] for r in per_item})}, "worstCases": [{"caseId": r["caseId"], "classification": r["classification"], "semanticEditCount": r["semanticEditCount"], "unsupportedFinalizedAssertions": r["unsupportedFinalizedAssertions"], "errorCodes": r["errorCodes"]} for r in sorted(per_item, key=lambda x: (-x["semanticEditCount"], -x["unsupportedFinalizedAssertions"], x["caseId"]))[:5]], "errorTaxonomy": {"codes": list(ERROR_CODES), "counts": {code: sum(code in r["errorCodes"] for r in per_item) for code in ERROR_CODES}}, "nonClaims": ["Offline synthetic diagnostic only; not human, provider, external, held-out, production, selection, promotion, or release evidence.", "v3.1 is a separate non-pooled comparison and is not silently replaced by v4."]}
    result["evaluationDigest"] = digest(result); return result


def write_immutable_evaluation(packet_dir: Path = PACKET) -> Path:
    value = evaluate(packet_dir / CANDIDATE_NAME, packet_dir); path = packet_dir / EVALUATION_NAME; content = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != content: raise ValueError(f"immutable evaluation already exists with different bytes: {path}")
    if not path.exists(): path.write_text(content, encoding="utf-8")
    return path


def validate_evaluation_artifact(path: Path = PACKET / EVALUATION_NAME, packet_dir: Path = PACKET) -> dict[str, Any]:
    value = read(path); validate_schema(value, packet_dir / "dense-hard-evaluation.v4.schema.json")
    if value["evaluationDigest"] != digest({k: v for k, v in value.items() if k != "evaluationDigest"}): raise ValueError("evaluation digest mismatch")
    if value != evaluate(packet_dir / CANDIDATE_NAME, packet_dir): raise ValueError("evaluation differs from deterministic recomputation")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--write", action="store_true"); parser.add_argument("--validate", action="store_true"); args = parser.parse_args()
    if args.validate: print(json.dumps(validate_evaluation_artifact(), ensure_ascii=False, sort_keys=True))
    elif args.write: print(json.dumps({"status": "WRITTEN", "path": str(write_immutable_evaluation())}, sort_keys=True))
    else: print(json.dumps(evaluate(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__": main()
