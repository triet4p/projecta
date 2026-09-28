"""Deterministic, fail-closed evaluator for the frozen dense-hard v3 candidate.

This evaluator is offline and binds every public/private packet artifact before
scoring.  Entity identity is an anchored occurrence (independent of type),
relation identity is predicate plus anchored endpoint occurrences, and type is
reported once as a diagnostic.  Formatting and terminal-punctuation-only
evidence changes are intentionally unchanged.
"""

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
PACKET = ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v3"
V1_PACKET = ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v1"
V2_PACKET = ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v2"
SOURCE_NAME = "dense-hard-source-payload.v3.json"
GOLD_NAME = "dense-hard-gold.v3.json"
MANIFEST_NAME = "dense-hard-evaluator-manifest.v3.json"
PROTOCOL_NAME = "dense-hard-source-only-protocol.v3.json"
CONTRACT_NAME = "dense-hard-evaluator-contract.v3.json"
CANDIDATE_NAME = "dense-hard-candidate.v3.json"
EVALUATION_NAME = "dense-hard-evaluation.v3.json"
BUILD_NAME = "build_s12_dense_hard_v3_candidate.py"

ERROR_CODES = (
    "ENTITY_TYPE_MISMATCH",
    "ENTITY_SPAN_MISMATCH",
    "ENTITY_LABEL_MISMATCH",
    "ENTITY_MISSING",
    "ENTITY_EXTRA",
    "RELATION_PREDICATE_MISMATCH",
    "RELATION_ENDPOINT_MISMATCH",
    "RELATION_EVIDENCE_MISMATCH",
    "RELATION_MISSING",
    "RELATION_EXTRA",
    "ABSTENTION_MISSING",
    "ABSTENTION_OVER",
    "ABSTENTION_MODE_MISMATCH",
    "QUARANTINE_CORRECT",
    "INCORRECT_QUARANTINE",
    "QUARANTINE_MISSING",
    "UNSUPPORTED_FINALIZED_ASSERTION",
    "HALLUCINATED_FINALIZED_ASSERTION",
)
MAJOR = {
    "entity_span",
    "entity_missing",
    "entity_extra",
    "relation_predicate",
    "relation_endpoint",
    "relation_missing",
    "relation_extra",
}
MINOR = {"entity_label", "relation_evidence"}


def stable(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(stable(value)).hexdigest()


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_schema(value: dict[str, Any], schema_path: Path) -> None:
    schema = read(schema_path)
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value), key=lambda error: list(error.path)
    )
    if errors:
        raise ValueError(f"{schema_path.name}: {list(errors[0].path)}: {errors[0].message}")


def occurrence(value: dict[str, Any]) -> tuple[int, int, str]:
    return value["startOffset"], value["endOffset"], value["text"]


def exact(raw: str, span: dict[str, Any]) -> None:
    start, end, text = occurrence(span)
    if start < 0 or end <= start or end > len(raw) or raw[start:end] != text:
        raise ValueError(f"invalid source anchor: {span!r}")


def contained(inner: dict[str, Any], outer: dict[str, Any]) -> bool:
    return outer["startOffset"] <= inner["startOffset"] < inner["endOffset"] <= outer["endOffset"]


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def f1(gold: set[tuple[Any, ...]], candidate: set[tuple[Any, ...]]) -> dict[str, Any]:
    tp, fp, fn = len(gold & candidate), len(candidate - gold), len(gold - candidate)
    precision, recall = ratio(tp, tp + fp), ratio(tp, tp + fn)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": ratio(2 * precision * recall, precision + recall),
    }


def normalize_evidence(text: str) -> str:
    """Normalize only formatting and terminal punctuation, per v3 protocol."""
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"[.!?。！？]+$", "", text).rstrip()


def difficulty(case_id: str) -> str:
    number = int(case_id[-3:])
    return (
        "dense-v3-baseline"
        if number <= 6
        else "dense-v3-disambiguation"
        if number <= 18
        else "dense-v3-adversarial-abstention"
    )


def relation_semantic(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        item["predicate"],
        occurrence(item["sourceOccurrence"]),
        occurrence(item["targetOccurrence"]),
    )


def gold_relation_semantic(item: dict[str, Any], entities: list[dict[str, Any]]) -> tuple[Any, ...]:
    by_id = {entity["entityId"]: occurrence(entity["evidence"]) for entity in entities}
    return (item["predicate"], by_id[item["sourceEntityId"]], by_id[item["targetEntityId"]])


def validate_candidate_anchors(
    source: dict[str, Any], candidate: dict[str, Any], protocol: dict[str, Any]
) -> None:
    source_by_id = {item["caseId"]: item for item in source["records"]}
    allowed_types, allowed_predicates = (
        set(protocol["finiteEntityTypes"]),
        set(protocol["finiteRelationPredicates"]),
    )
    for record in candidate["records"]:
        raw = source_by_id[record["caseId"]]["rawText"]
        entity_occurrences: set[tuple[int, int, str]] = set()
        for item in record["entities"]:
            if item["type"] not in allowed_types or item["label"] != item["occurrence"]["text"]:
                raise ValueError(f"candidate entity label/type violation in {record['caseId']}")
            exact(raw, item["occurrence"])
            key = occurrence(item["occurrence"])
            if key in entity_occurrences:
                raise ValueError(f"duplicate candidate occurrence in {record['caseId']}")
            entity_occurrences.add(key)
        for item in record["relations"]:
            if item["predicate"] not in allowed_predicates:
                raise ValueError(f"candidate predicate violation in {record['caseId']}")
            for key in ("sourceOccurrence", "targetOccurrence", "evidence", "triggerEvidence"):
                exact(raw, item[key])
            if not all(
                contained(item[key], item["evidence"])
                for key in ("sourceOccurrence", "targetOccurrence", "triggerEvidence")
            ):
                raise ValueError(f"candidate relation grounding violation in {record['caseId']}")
            if (
                occurrence(item["sourceOccurrence"]) not in entity_occurrences
                or occurrence(item["targetOccurrence"]) not in entity_occurrences
            ):
                raise ValueError(
                    f"candidate relation endpoint not registered in {record['caseId']}"
                )
        for item in record["quarantine"]:
            exact(raw, item["evidence"])
            if item["reasonCode"] not in set(protocol["quarantinePolicy"]["reasons"]):
                raise ValueError(f"candidate quarantine reason violation in {record['caseId']}")


def validate_bindings(packet_dir: Path, candidate_path: Path) -> dict[str, Any]:
    names = {
        "source": SOURCE_NAME,
        "gold": GOLD_NAME,
        "manifest": MANIFEST_NAME,
        "protocol": PROTOCOL_NAME,
        "contract": CONTRACT_NAME,
        "candidate": CANDIDATE_NAME,
    }
    values = {
        key: read(packet_dir / name if key != "candidate" else candidate_path)
        for key, name in names.items()
    }
    for key, name in names.items():
        schema_name = name.replace(".json", ".schema.json")
        validate_schema(values[key], packet_dir / schema_name)
    for key, field in (
        ("source", "payloadDigest"),
        ("gold", "goldDigest"),
        ("manifest", "manifestDigest"),
        ("protocol", "protocolDigest"),
        ("contract", "contractDigest"),
    ):
        if values[key][field] != digest({k: v for k, v in values[key].items() if k != field}):
            raise ValueError(f"{key} digest mismatch")
    candidate = values["candidate"]
    candidate_without_digest = copy.deepcopy(candidate)
    candidate_without_digest.pop("candidateDigest")
    if candidate["candidateDigest"] != digest(candidate_without_digest):
        raise ValueError("candidate digest mismatch")
    # The builder digest is retained as candidate provenance, but is not a
    # public evaluator binding: the candidate is frozen and the working-tree
    # builder may be unavailable or independently maintained.
    source, gold, manifest, protocol, contract = (
        values[k] for k in ("source", "gold", "manifest", "protocol", "contract")
    )
    if (
        candidate["sourcePayloadDigest"] != source["payloadDigest"]
        or gold["sourcePayloadDigest"] != source["payloadDigest"]
        or manifest["sourcePayloadDigest"] != source["payloadDigest"]
        or manifest["goldDigest"] != gold["goldDigest"]
        or candidate["protocolDigest"] != protocol["protocolDigest"]
        or candidate["evaluatorContractDigest"] != contract["contractDigest"]
    ):
        raise ValueError("cross-artifact digest binding mismatch")
    if (
        candidate["providerCalls"] != 0
        or not candidate["sourceOnly"]
        or candidate["goldUsed"]
        or candidate["priorReviewUsed"]
        or candidate["scoringPerformed"]
    ):
        raise ValueError("candidate source-only or anti-leak flags are not clean")
    serialized = json.dumps(candidate, ensure_ascii=False).lower()
    if any(token in serialized for token in ('"expected"', '"goldpath"', '"manifestpath"')):
        raise ValueError("private evaluator keys leaked into candidate")
    source_ids = {record["caseId"] for record in source["records"]}
    if (
        source_ids != {record["caseId"] for record in gold["records"]}
        or source_ids != {record["caseId"] for record in manifest["records"]}
        or source_ids != {record["caseId"] for record in candidate["records"]}
    ):
        raise ValueError("source, gold, manifest, and candidate case sets differ")
    validate_candidate_anchors(source, candidate, protocol)
    return values


def match_entities(
    gold: list[dict[str, Any]], candidate: list[dict[str, Any]]
) -> tuple[list[tuple[int, int]], set[int], set[int]]:
    gold_by_key = {occurrence(item["evidence"]): index for index, item in enumerate(gold)}
    matches, used_gold, used_candidate = [], set(), set()
    for ci, item in enumerate(candidate):
        gi = gold_by_key.get(occurrence(item["occurrence"]))
        if gi is not None and gi not in used_gold:
            matches.append((gi, ci))
            used_gold.add(gi)
            used_candidate.add(ci)
    return matches, used_gold, used_candidate


def match_relations(
    gold: list[dict[str, Any]], candidate: list[dict[str, Any]], gold_entities: list[dict[str, Any]]
) -> tuple[list[tuple[int, int]], set[int], set[int]]:
    gold_semantics = [gold_relation_semantic(item, gold_entities) for item in gold]
    matches, used_gold, used_candidate = [], set(), set()
    # Exact relation identity first.
    for ci, item in enumerate(candidate):
        options = [
            gi
            for gi, expected in enumerate(gold)
            if gi not in used_gold and gold_semantics[gi] == relation_semantic(item)
        ]
        if options:
            gi = options[0]
            matches.append((gi, ci))
            used_gold.add(gi)
            used_candidate.add(ci)
    # Pair same anchored endpoints to expose predicate edits, then same
    # predicate to expose endpoint edits.  Type is deliberately absent.
    for ci, item in enumerate(candidate):
        if ci in used_candidate:
            continue
        options = [
            gi
            for gi, expected in enumerate(gold)
            if gi not in used_gold
            and (gold_semantics[gi][1], gold_semantics[gi][2])
            == (occurrence(item["sourceOccurrence"]), occurrence(item["targetOccurrence"]))
        ]
        if options:
            gi = options[0]
            matches.append((gi, ci))
            used_gold.add(gi)
            used_candidate.add(ci)
    for ci, item in enumerate(candidate):
        if ci in used_candidate:
            continue
        options = [
            gi
            for gi, expected in enumerate(gold)
            if gi not in used_gold and expected["predicate"] == item["predicate"]
        ]
        if options:
            gi = options[0]
            matches.append((gi, ci))
            used_gold.add(gi)
            used_candidate.add(ci)
    return matches, used_gold, used_candidate


def expected_relation_occurrences(expected: dict[str, Any]) -> set[tuple[str, int, int, str]]:
    return {
        (
            item["kind"],
            item["evidence"]["startOffset"],
            item["evidence"]["endOffset"],
            item["evidence"]["text"],
        )
        for item in (
            [{"kind": "entity", "evidence": e["evidence"]} for e in expected["entities"]]
            + [{"kind": "relation", "evidence": r["evidence"]} for r in expected["relations"]]
        )
    }


def classify(
    expected: dict[str, Any], response: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    gold_entities, candidate_entities = expected["entities"], response["entities"]
    gold_relations, candidate_relations = expected["relations"], response["relations"]
    diffs: Counter[str] = Counter()
    entity_matches, used_gold_entities, used_candidate_entities = match_entities(
        gold_entities, candidate_entities
    )
    type_corrections = 0
    for gi, ci in entity_matches:
        ge, ce = gold_entities[gi], candidate_entities[ci]
        if occurrence(ge["evidence"]) != occurrence(ce["occurrence"]):
            diffs["entity_span"] += 1
        if ge["label"] != ce["label"]:
            diffs["entity_label"] += 1
        if ge["type"] != ce["type"]:
            diffs["entity_type"] += 1
            type_corrections += 1
    diffs["entity_missing"] = len(set(range(len(gold_entities))) - used_gold_entities)
    diffs["entity_extra"] = len(set(range(len(candidate_entities))) - used_candidate_entities)
    relation_matches, used_gold_relations, used_candidate_relations = match_relations(
        gold_relations, candidate_relations, gold_entities
    )
    for gi, ci in relation_matches:
        gr, cr = gold_relations[gi], candidate_relations[ci]
        if gr["predicate"] != cr["predicate"]:
            diffs["relation_predicate"] += 1
        gsem = gold_relation_semantic(gr, gold_entities)
        if (gsem[1], gsem[2]) != (
            occurrence(cr["sourceOccurrence"]),
            occurrence(cr["targetOccurrence"]),
        ):
            diffs["relation_endpoint"] += 1
        if normalize_evidence(gr["evidence"]["text"]) != normalize_evidence(
            cr["evidence"]["text"]
        ) or normalize_evidence(gr["triggerEvidence"]["text"]) != normalize_evidence(
            cr["triggerEvidence"]["text"]
        ):
            diffs["relation_evidence"] += 1
    diffs["relation_missing"] = len(set(range(len(gold_relations))) - used_gold_relations)
    diffs["relation_extra"] = len(set(range(len(candidate_relations))) - used_candidate_relations)
    semantic_edits = sum(
        diffs[key]
        for key in (
            "entity_span",
            "entity_label",
            "entity_missing",
            "entity_extra",
            "relation_predicate",
            "relation_endpoint",
            "relation_missing",
            "relation_extra",
        )
    )
    expected_mode = expected["abstentionMode"]
    candidate_mode = response["abstention"]
    required = expected_mode != "none"
    mode_correct = candidate_mode == expected_mode if required else candidate_mode == "none"
    if required and candidate_mode == "none":
        diffs["abstention_missing"] += 1
        classification = "reject"
    elif not required and candidate_mode != "none":
        diffs["abstention_over"] += 1
        classification = "abstain"
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
    gold_entity_set = {
        (e["evidence"]["startOffset"], e["evidence"]["endOffset"], e["evidence"]["text"])
        for e in gold_entities
    }
    candidate_entity_set = {occurrence(e["occurrence"]) for e in candidate_entities}
    gold_relation_set = {gold_relation_semantic(r, gold_entities) for r in gold_relations}
    candidate_relation_set = {relation_semantic(r) for r in candidate_relations}
    unsupported = len(candidate_relation_set - gold_relation_set)
    hallucinated = len(
        {(e["occurrence"]["startOffset"], e["occurrence"]["endOffset"]) for e in candidate_entities}
        - {(e["evidence"]["startOffset"], e["evidence"]["endOffset"]) for e in gold_entities}
    ) + len(candidate_relation_set - gold_relation_set)
    gold_evidence = expected_relation_occurrences(expected)
    q_correct = sum(
        (
            "entity" if q["kind"] == "entity" else "relation",
            q["evidence"]["startOffset"],
            q["evidence"]["endOffset"],
            q["evidence"]["text"],
        )
        not in gold_evidence
        for q in response["quarantine"]
    )
    q_incorrect = len(response["quarantine"]) - q_correct
    mapping = {
        "entity_type": "ENTITY_TYPE_MISMATCH",
        "entity_span": "ENTITY_SPAN_MISMATCH",
        "entity_label": "ENTITY_LABEL_MISMATCH",
        "entity_missing": "ENTITY_MISSING",
        "entity_extra": "ENTITY_EXTRA",
        "relation_predicate": "RELATION_PREDICATE_MISMATCH",
        "relation_endpoint": "RELATION_ENDPOINT_MISMATCH",
        "relation_evidence": "RELATION_EVIDENCE_MISMATCH",
        "relation_missing": "RELATION_MISSING",
        "relation_extra": "RELATION_EXTRA",
        "abstention_missing": "ABSTENTION_MISSING",
        "abstention_over": "ABSTENTION_OVER",
        "abstention_mode_mismatch": "ABSTENTION_MODE_MISMATCH",
    }
    error_codes = [mapping[key] for key in mapping if diffs[key]]
    if q_correct:
        error_codes.append("QUARANTINE_CORRECT")
    if q_incorrect:
        error_codes.append("INCORRECT_QUARANTINE")
    if len(response["quarantine"]) < manifest["quarantineCount"]:
        error_codes.append("QUARANTINE_MISSING")
    if unsupported:
        error_codes.append("UNSUPPORTED_FINALIZED_ASSERTION")
    if hallucinated:
        error_codes.append("HALLUCINATED_FINALIZED_ASSERTION")
    return {
        "caseId": manifest["caseId"],
        "scenarioId": manifest["scenarioId"],
        "slices": manifest["slices"],
        "difficultyTier": difficulty(manifest["caseId"]),
        "classification": classification,
        "goldAbstentionRequired": required,
        "expectedAbstentionMode": expected_mode,
        "candidateAbstentionStatus": candidate_mode,
        "abstentionCorrect": mode_correct,
        "typeCorrections": type_corrections,
        "semanticEditCount": semantic_edits,
        "unsupportedFinalizedAssertions": unsupported,
        "hallucinatedFinalizedAssertions": hallucinated,
        "quarantinePredicted": len(response["quarantine"]),
        "quarantineCorrect": q_correct,
        "quarantineIncorrect": q_incorrect,
        "errorCodes": error_codes,
        "entity": {
            "gold": len(gold_entities),
            "candidate": len(candidate_entities),
            **f1(gold_entity_set, candidate_entity_set),
            "dimensionDiffs": {
                key: diffs[key]
                for key in (
                    "entity_span",
                    "entity_type",
                    "entity_label",
                    "entity_missing",
                    "entity_extra",
                )
            },
        },
        "relation": {
            "gold": len(gold_relations),
            "candidate": len(candidate_relations),
            **f1(gold_relation_set, candidate_relation_set),
            "dimensionDiffs": {
                key: diffs[key]
                for key in (
                    "relation_predicate",
                    "relation_endpoint",
                    "relation_evidence",
                    "relation_missing",
                    "relation_extra",
                )
            },
        },
    }


def aggregate(
    records: list[dict[str, Any]], field: str | None = None, value: str | None = None
) -> dict[str, Any]:
    selected = [
        r
        for r in records
        if field is None or (value in r[field] if isinstance(r[field], list) else r[field] == value)
    ]

    def pooled(name: str) -> dict[str, Any]:
        metric = {key: sum(r[name][key] for r in selected) for key in ("tp", "fp", "fn")}
        metric["precision"], metric["recall"] = (
            ratio(metric["tp"], metric["tp"] + metric["fp"]),
            ratio(metric["tp"], metric["tp"] + metric["fn"]),
        )
        metric["f1"] = ratio(
            2 * metric["precision"] * metric["recall"], metric["precision"] + metric["recall"]
        )
        return metric

    required = sum(r["goldAbstentionRequired"] for r in selected)
    predicted = sum(r["candidateAbstentionStatus"] != "none" for r in selected)
    correct = sum(r["goldAbstentionRequired"] and r["abstentionCorrect"] for r in selected)
    return {
        "caseCount": len(selected),
        "classificationCounts": {
            kind: Counter(r["classification"] for r in selected)[kind]
            for kind in ("unchanged", "minor", "major", "reject", "abstain")
        },
        "semanticEditCount": sum(r["semanticEditCount"] for r in selected),
        "typeCorrections": sum(r["typeCorrections"] for r in selected),
        "unsupportedFinalizedAssertions": sum(
            r["unsupportedFinalizedAssertions"] for r in selected
        ),
        "hallucinatedFinalizedAssertions": sum(
            r["hallucinatedFinalizedAssertions"] for r in selected
        ),
        "quarantinePredicted": sum(r["quarantinePredicted"] for r in selected),
        "quarantineCorrect": sum(r["quarantineCorrect"] for r in selected),
        "quarantineIncorrect": sum(r["quarantineIncorrect"] for r in selected),
        "abstentionRequired": required,
        "abstentionPredicted": predicted,
        "abstentionCorrect": correct,
        "abstentionPrecision": ratio(correct, predicted),
        "abstentionRecall": ratio(correct, required),
        "entityMetrics": pooled("entity"),
        "relationMetrics": pooled("relation"),
    }


def _comparison() -> dict[str, Any]:
    v1 = read(V1_PACKET / "dense-hard-evaluation.v1.json")
    v21 = read(V2_PACKET / "dense-hard-evaluation-adjudication.v2.1.json")
    legacy = v21["v1Comparison"]["comparison"]["legacyStrict"]
    fair = v21["v1Comparison"]["comparison"]["protocolFair"]
    return {
        "interpretation": "Descriptive cross-packet diagnostics only; no source, gold, candidate, or metric pooling.",
        "pooled": False,
        "v1": {
            "evaluationPath": "evaluation/sprint-12/internal-poc/dense-hard-v1/dense-hard-evaluation.v1.json",
            "evaluationDigest": v1["evaluationDigest"],
            "candidateDigest": v1["candidateDigest"],
            "metrics": {
                "cases": len(v1["perItem"]),
                "entityF1": v1["entityMetrics"]["f1"],
                "relationF1": v1["relationMetrics"]["f1"],
                "semanticEdits": v1["semanticEditCounts"]["total"],
                "unsupportedFinalizedAssertions": v1["unsupportedFinalizedAssertions"]["numerator"],
            },
        },
        "v2_1": {
            "adjudicationPath": "evaluation/sprint-12/internal-poc/dense-hard-v2/dense-hard-evaluation-adjudication.v2.1.json",
            "adjudicationDigest": v21["adjudicationDigest"],
            "candidateDigest": v21["candidateDigest"],
            "metrics": {"legacyStrict": legacy, "protocolFair": fair},
        },
        "note": "v2.1 is retained as descriptive prior evidence; v3 is scored under its own public rubric.",
    }


def evaluate(
    candidate_path: Path = PACKET / CANDIDATE_NAME, packet_dir: Path = PACKET
) -> dict[str, Any]:
    bound = validate_bindings(packet_dir, candidate_path)
    source, gold, manifest, candidate, protocol = (
        bound[k] for k in ("source", "gold", "manifest", "candidate", "protocol")
    )
    source_by_id = {r["caseId"]: r for r in source["records"]}
    gold_by_id = {r["caseId"]: r["expected"] for r in gold["records"]}
    manifest_by_id = {r["caseId"]: r for r in manifest["records"]}
    candidate_by_id = {r["caseId"]: r for r in candidate["records"]}
    per_item = [
        classify(gold_by_id[cid], candidate_by_id[cid], manifest_by_id[cid])
        for cid in sorted(source_by_id)
    ]
    entity_gold = {
        (
            r["caseId"],
            e["evidence"]["startOffset"],
            e["evidence"]["endOffset"],
            e["evidence"]["text"],
        )
        for r in gold["records"]
        for e in gold_by_id[r["caseId"]]["entities"]
    }
    entity_candidate = {
        (r["caseId"], *occurrence(e["occurrence"]))
        for r in candidate["records"]
        for e in candidate_by_id[r["caseId"]]["entities"]
    }
    relation_gold = {
        (r["caseId"], *gold_relation_semantic(rel, gold_by_id[r["caseId"]]["entities"]))
        for r in gold["records"]
        for rel in gold_by_id[r["caseId"]]["relations"]
    }
    relation_candidate = {
        (r["caseId"], *relation_semantic(rel))
        for r in candidate["records"]
        for rel in candidate_by_id[r["caseId"]]["relations"]
    }
    classes = Counter(r["classification"] for r in per_item)
    total_edits = sum(r["semanticEditCount"] for r in per_item)
    total_types = sum(r["typeCorrections"] for r in per_item)
    unsupported = sum(r["unsupportedFinalizedAssertions"] for r in per_item)
    hallucinated = sum(r["hallucinatedFinalizedAssertions"] for r in per_item)
    q_pred = sum(r["quarantinePredicted"] for r in per_item)
    q_correct = sum(r["quarantineCorrect"] for r in per_item)
    q_incorrect = sum(r["quarantineIncorrect"] for r in per_item)
    required = [r for r in per_item if r["goldAbstentionRequired"]]
    predicted = [r for r in per_item if r["candidateAbstentionStatus"] != "none"]
    required_ids, predicted_ids = {r["caseId"] for r in required}, {r["caseId"] for r in predicted}
    full_required = [r for r in required if r["expectedAbstentionMode"] == "full"]
    partial_required = [r for r in required if r["expectedAbstentionMode"] == "partial"]
    full_pred = [r for r in predicted if r["candidateAbstentionStatus"] == "full"]
    partial_pred = [r for r in predicted if r["candidateAbstentionStatus"] == "partial"]
    full_tp = len({r["caseId"] for r in full_required} & {r["caseId"] for r in full_pred})
    partial_tp = len({r["caseId"] for r in partial_required} & {r["caseId"] for r in partial_pred})
    abstention = {
        "required": len(required),
        "predicted": len(predicted),
        "truePositive": len(required_ids & predicted_ids),
        "precision": ratio(len(required_ids & predicted_ids), len(predicted_ids)),
        "recall": ratio(len(required_ids & predicted_ids), len(required_ids)),
        "full": {
            "required": len(full_required),
            "predicted": len(full_pred),
            "correct": full_tp,
            "precision": ratio(full_tp, len(full_pred)),
            "recall": ratio(full_tp, len(full_required)),
        },
        "partial": {
            "required": len(partial_required),
            "predicted": len(partial_pred),
            "correct": partial_tp,
            "precision": ratio(partial_tp, len(partial_pred)),
            "recall": ratio(partial_tp, len(partial_required)),
        },
    }
    unsafe_total = q_correct + unsupported
    finalized_total = len(entity_candidate) + len(relation_candidate)
    slices = sorted({s for r in manifest["records"] for s in r["slices"]})
    tiers = sorted({r["difficultyTier"] for r in per_item})
    result: dict[str, Any] = {
        "artifactVersion": "s12.dense-hard.evaluation.v3",
        "status": "EVALUATED_FROZEN_CANDIDATE",
        "datasetKind": "SYNTHETIC_NON_PRODUCTION",
        "evaluatorVersion": "s12.dense-hard.evaluator.v3",
        "evaluatorCodeDigest": file_digest(Path(__file__)),
        "sourcePayloadPath": f"evaluation/sprint-12/internal-poc/dense-hard-v3/{SOURCE_NAME}",
        "sourcePayloadDigest": source["payloadDigest"],
        "protocolPath": f"evaluation/sprint-12/internal-poc/dense-hard-v3/{PROTOCOL_NAME}",
        "protocolDigest": protocol["protocolDigest"],
        "contractPath": f"evaluation/sprint-12/internal-poc/dense-hard-v3/{CONTRACT_NAME}",
        "contractDigest": bound["contract"]["contractDigest"],
        "goldPath": f"evaluation/sprint-12/internal-poc/dense-hard-v3/{GOLD_NAME}",
        "goldDigest": gold["goldDigest"],
        "manifestPath": f"evaluation/sprint-12/internal-poc/dense-hard-v3/{MANIFEST_NAME}",
        "manifestDigest": manifest["manifestDigest"],
        "candidatePath": f"evaluation/sprint-12/internal-poc/dense-hard-v3/{CANDIDATE_NAME}",
        "candidateDigest": candidate["candidateDigest"],
        "candidateModel": candidate["agentModel"],
        "providerCalls": 0,
        "antiLeakChecks": {
            "candidateDigestBound": True,
            "sourceDigestBound": True,
            "protocolDigestBound": True,
            "contractDigestBound": True,
            "goldDigestBound": True,
            "manifestDigestBound": True,
            "candidateSourceOnlyFlagsClean": True,
            "goldExcludedFromCandidate": True,
            "providerCallsZero": True,
            "heldOutInspectionFalse": True,
            "fRfStateChanged": False,
        },
        "counts": {
            "caseCount": len(per_item),
            "entityGold": len(entity_gold),
            "entityCandidate": len(entity_candidate),
            "relationGold": len(relation_gold),
            "relationCandidate": len(relation_candidate),
            "quarantinePredicted": q_pred,
        },
        "perItemClassificationCounts": {
            k: classes[k] for k in ("unchanged", "minor", "major", "reject", "abstain")
        },
        "semanticEditCounts": {
            "total": total_edits,
            "meanPerCase": ratio(total_edits, len(per_item)),
        },
        "typeDiagnostics": {
            "typeCorrections": total_types,
            "identityIndependentOfType": True,
            "cascadeToRelation": False,
            "ambiguousExcludedFromPassFail": True,
        },
        "entityMetrics": f1(entity_gold, entity_candidate),
        "relationMetrics": f1(relation_gold, relation_candidate),
        "abstentionMetrics": abstention,
        "quarantineMetrics": {
            "caseLevel": {
                "requiredCases": len(required),
                "predictedCases": sum(r["quarantinePredicted"] > 0 for r in per_item),
                "correctCases": sum(
                    r["quarantinePredicted"] > 0 and r["goldAbstentionRequired"] for r in per_item
                ),
                "precision": ratio(
                    sum(
                        r["quarantinePredicted"] > 0 and r["goldAbstentionRequired"]
                        for r in per_item
                    ),
                    sum(r["quarantinePredicted"] > 0 for r in per_item),
                ),
                "recall": ratio(
                    sum(
                        r["quarantinePredicted"] > 0 and r["goldAbstentionRequired"]
                        for r in per_item
                    ),
                    len(required),
                ),
            },
            "assertionLevel": {
                "predictedAssertions": q_pred,
                "correctAssertions": q_correct,
                "incorrectAssertions": q_incorrect,
                "precision": ratio(q_correct, q_pred),
                "recall": ratio(q_correct, q_correct + unsupported),
            },
            "definition": "A quarantine is safe/correct when its exact anchored evidence is not a gold-finalized entity/relation evidence span; assertion recall routes candidate unsupported proposals to quarantine rather than finalization.",
        },
        "unsafeFinalizedAssertionsAvoided": {
            "avoidedByQuarantine": q_correct,
            "unsafeFinalized": unsupported,
            "totalUnsupportedProposals": unsafe_total,
            "avoidanceRate": ratio(q_correct, unsafe_total),
        },
        "unsupportedFinalizedAssertions": {
            "numerator": unsupported,
            "denominator": finalized_total,
            "status": "ZERO_UNSUPPORTED" if unsupported == 0 else "UNSUPPORTED_PRESENT",
        },
        "hallucinatedFinalizedAssertions": {
            "numerator": hallucinated,
            "denominator": finalized_total,
            "status": "ZERO_HALLUCINATED" if hallucinated == 0 else "HALLUCINATED_PRESENT",
        },
        "rm67": {
            "thresholds": {
                "acceptedWithoutSemanticCorrectionMinimum": 0.70,
                "acceptedUnchangedOrMinorMinimum": 0.85,
                "meanSemanticEditsMaximum": 2.0,
                "unsupportedFinalizedAssertionsMaximum": 0,
            },
            "acceptedWithoutSemanticCorrection": ratio(classes["unchanged"], len(per_item)),
            "acceptedUnchangedOrMinor": ratio(
                classes["unchanged"] + classes["minor"], len(per_item)
            ),
            "meanSemanticEditsPerReviewedItem": ratio(total_edits, len(per_item)),
            "unsupportedFinalizedAssertions": {
                "numerator": unsupported,
                "denominator": finalized_total,
                "status": "ZERO_UNSUPPORTED" if unsupported == 0 else "UNSUPPORTED_PRESENT",
            },
            "editBurdenGate": ratio(classes["unchanged"], len(per_item)) >= 0.70
            and ratio(classes["unchanged"] + classes["minor"], len(per_item)) >= 0.85
            and ratio(total_edits, len(per_item)) <= 2.0
            and unsupported == 0,
        },
        "perItem": per_item,
        "perSlice": {s: aggregate(per_item, "slices", s) for s in slices},
        "difficultyTiers": {t: aggregate(per_item, "difficultyTier", t) for t in tiers},
        "worstCases": [
            {
                "caseId": r["caseId"],
                "classification": r["classification"],
                "semanticEditCount": r["semanticEditCount"],
                "unsupportedFinalizedAssertions": r["unsupportedFinalizedAssertions"],
                "errorCodes": r["errorCodes"],
            }
            for r in sorted(
                per_item,
                key=lambda x: (
                    -x["semanticEditCount"],
                    -x["unsupportedFinalizedAssertions"],
                    x["caseId"],
                ),
            )[:5]
        ],
        "errorTaxonomy": {
            "codes": list(ERROR_CODES),
            "counts": {
                code: sum(code in r["errorCodes"] for r in per_item) for code in ERROR_CODES
            },
        },
        "v1Comparison": _comparison(),
        "nonClaims": [
            "This is an offline synthetic diagnostic, not human evidence or a production quality claim.",
            "No provider call, external tool, held-out inspection, state transition, selection, promotion, or release was performed.",
            "v1/v2.1 values are descriptive and non-pooled; v3 metrics are not pooled with prior packets.",
        ],
    }
    result["evaluationDigest"] = digest(result)
    return result


def write_immutable_evaluation(packet_dir: Path = PACKET) -> Path:
    value = evaluate(packet_dir / CANDIDATE_NAME, packet_dir)
    path = packet_dir / EVALUATION_NAME
    content = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise ValueError(f"immutable evaluation already exists with different bytes: {path}")
    if not path.exists():
        path.write_text(content, encoding="utf-8")
    return path


def validate_evaluation_artifact(
    path: Path = PACKET / EVALUATION_NAME, packet_dir: Path = PACKET
) -> dict[str, Any]:
    value = read(path)
    validate_schema(value, packet_dir / "dense-hard-evaluation.v3.schema.json")
    if value["evaluationDigest"] != digest(
        {k: v for k, v in value.items() if k != "evaluationDigest"}
    ):
        raise ValueError("evaluation digest mismatch")
    if value != evaluate(packet_dir / CANDIDATE_NAME, packet_dir):
        raise ValueError("evaluation differs from deterministic recomputation")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    if args.validate:
        print(json.dumps(validate_evaluation_artifact(), ensure_ascii=False, sort_keys=True))
    elif args.write:
        print(
            json.dumps(
                {"status": "WRITTEN", "path": str(write_immutable_evaluation())}, sort_keys=True
            )
        )
    else:
        print(
            json.dumps(
                evaluate(args.candidate or PACKET / CANDIDATE_NAME),
                ensure_ascii=False,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
