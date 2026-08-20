"""Versioned offline contracts and deterministic scoring for S12-f-12."""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

ENTITY_TYPES = frozenset(
    {
        "Requirement",
        "Decision",
        "Question",
        "Task",
        "Risk",
        "Assumption",
        "Constraint",
        "ProgressClaim",
        "ResearchFinding",
    }
)
PREDICATES = frozenset(
    {
        "implements",
        "blocks",
        "dependsOn",
        "supports",
        "answers",
        "resolves",
        "constrainedBy",
    }
)
SEMANTIC_BUCKETS = (
    "exactMatch",
    "wrongPredicate",
    "reversedEndpoint",
    "wrongEndpoint",
    "missingRelation",
    "extraRelation",
)
EVIDENCE_BUCKETS = (
    "exact",
    "supportedNonExact",
    "unsupported",
    "missing",
    "notApplicable",
)
STAGE1_VERSION = "s12-f-12.stage1.entity-envelope.v2"
STAGE2_VERSION = "s12-f-12.stage2.relation-envelope.v2"


class ContractViolation(ValueError):
    """Raised when a response crosses a server-owned boundary."""


@dataclass(frozen=True, slots=True)
class EntityCandidate:
    candidate_id: str
    entity_type: str
    start: int
    end: int
    confidence: Decimal


@dataclass(frozen=True, slots=True)
class RelationCandidate:
    predicate: str
    source_entity_id: str
    target_entity_id: str
    confidence: Decimal
    evidence_start: int | None = None
    evidence_end: int | None = None
    trigger_quote: str | None = None


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContractViolation(f"{field} must be a non-empty string")
    return value


def _span(payload: Mapping[str, object], field: str) -> tuple[int, int]:
    start = payload.get("startOffset")
    end = payload.get("endOffset")
    if (
        not isinstance(start, int)
        or not isinstance(end, int)
        or start < 0
        or start >= end
    ):
        raise ContractViolation(f"{field} span is not a valid half-open range")
    return start, end


def _confidence(value: object, field: str) -> Decimal:
    try:
        confidence = Decimal(str(value))
    except (ArithmeticError, ValueError) as error:
        raise ContractViolation(f"{field} confidence is invalid") from error
    if confidence < 0 or confidence > 1:
        raise ContractViolation(f"{field} confidence is outside [0, 1]")
    return confidence


def _abstention(
    payload: object, *, has_items: bool, field: str
) -> tuple[bool, str | None]:
    if not isinstance(payload, Mapping) or set(payload) != {"required", "reason"}:
        raise ContractViolation(f"{field} must contain exactly required and reason")
    required = payload.get("required")
    reason = payload.get("reason")
    if not isinstance(required, bool) or (
        reason is not None and not isinstance(reason, str)
    ):
        raise ContractViolation(f"{field} has invalid values")
    if has_items and (required or reason is not None):
        raise ContractViolation(f"{field} cannot abstain when items are present")
    if not has_items and (not required or not reason):
        raise ContractViolation(f"{field} must explain an empty response")
    return required, reason


def validate_stage1_candidates(
    payload: Sequence[Mapping[str, object]], *, source_length: int
) -> tuple[EntityCandidate, ...]:
    """Validate model-proposed stage-1 spans."""

    candidates: list[EntityCandidate] = []
    seen_ids: set[str] = set()
    seen_spans: set[tuple[str, int, int]] = set()
    for index, item in enumerate(payload):
        if set(item) - {
            "candidateId",
            "type",
            "startOffset",
            "endOffset",
            "confidence",
        }:
            raise ContractViolation("stage-1 response contains server-owned fields")
        candidate_id = _text(item.get("candidateId"), f"entities[{index}].candidateId")
        entity_type = _text(item.get("type"), f"entities[{index}].type")
        if entity_type not in ENTITY_TYPES:
            raise ContractViolation(f"entities[{index}].type is not allowlisted")
        start, end = _span(item, f"entities[{index}]")
        if end > source_length:
            raise ContractViolation(f"entities[{index}] exceeds source length")
        if candidate_id in seen_ids or (entity_type, start, end) in seen_spans:
            raise ContractViolation("stage-1 candidate identities must be unique")
        seen_ids.add(candidate_id)
        seen_spans.add((entity_type, start, end))
        candidates.append(
            EntityCandidate(
                candidate_id,
                entity_type,
                start,
                end,
                _confidence(item.get("confidence"), f"entities[{index}]"),
            )
        )
    return tuple(candidates)


def validate_stage1_response(
    payload: Mapping[str, object], *, source_length: int
) -> tuple[tuple[EntityCandidate, ...], bool]:
    """Validate a complete stage-1 envelope, including no-entity abstention."""

    if set(payload) != {"schemaVersion", "entities", "abstention"}:
        raise ContractViolation("stage-1 envelope has unbound fields")
    if payload.get("schemaVersion") != STAGE1_VERSION:
        raise ContractViolation("stage-1 envelope version is not bound")
    entities = payload.get("entities")
    if not isinstance(entities, Sequence) or isinstance(entities, (str, bytes)):
        raise ContractViolation("stage-1 entities must be an array")
    candidates = validate_stage1_candidates(entities, source_length=source_length)
    required, _ = _abstention(
        payload.get("abstention"),
        has_items=bool(candidates),
        field="stage-1 abstention",
    )
    return candidates, required


def validate_stage2_relations(
    payload: Sequence[Mapping[str, object]],
    *,
    candidate_table: Sequence[EntityCandidate],
    source_length: int | None = None,
) -> tuple[RelationCandidate, ...]:
    """Validate stage-2 relation items without permitting entity mutation."""

    allowed_ids = {candidate.candidate_id for candidate in candidate_table}
    relations: list[RelationCandidate] = []
    seen: set[tuple[str, str, str]] = set()
    for index, item in enumerate(payload):
        if set(item) - {
            "predicate",
            "sourceEntityId",
            "targetEntityId",
            "confidence",
            "evidence",
            "triggerQuote",
        }:
            raise ContractViolation(
                "stage-2 response attempts to mutate the candidate table"
            )
        predicate = _text(item.get("predicate"), f"relations[{index}].predicate")
        if predicate not in PREDICATES:
            raise ContractViolation(f"relations[{index}].predicate is not allowlisted")
        source_id = _text(
            item.get("sourceEntityId"), f"relations[{index}].sourceEntityId"
        )
        target_id = _text(
            item.get("targetEntityId"), f"relations[{index}].targetEntityId"
        )
        if (
            source_id not in allowed_ids
            or target_id not in allowed_ids
            or source_id == target_id
        ):
            raise ContractViolation("stage-2 relation references an invalid candidate")
        identity = (predicate, source_id, target_id)
        if identity in seen:
            raise ContractViolation("stage-2 relation identities must be unique")
        seen.add(identity)
        trigger_quote = _text(
            item.get("triggerQuote"), f"relations[{index}].triggerQuote"
        )
        evidence = item.get("evidence")
        evidence_start: int | None = None
        evidence_end: int | None = None
        if evidence is not None:
            if not isinstance(evidence, Mapping) or set(evidence) != {
                "startOffset",
                "endOffset",
            }:
                raise ContractViolation(f"relations[{index}].evidence is invalid")
            evidence_start, evidence_end = _span(
                evidence, f"relations[{index}].evidence"
            )
            if source_length is not None and evidence_end > source_length:
                raise ContractViolation(
                    f"relations[{index}].evidence exceeds source length"
                )
        relations.append(
            RelationCandidate(
                predicate,
                source_id,
                target_id,
                _confidence(item.get("confidence"), f"relations[{index}]"),
                evidence_start,
                evidence_end,
                trigger_quote,
            )
        )
    return tuple(relations)


def validate_stage2_response(
    payload: Mapping[str, object],
    *,
    candidate_table: Sequence[EntityCandidate],
    source_length: int,
) -> tuple[tuple[RelationCandidate, ...], bool]:
    """Validate a complete stage-2 envelope, including no-relation abstention."""

    if set(payload) != {"schemaVersion", "relations", "abstention"}:
        raise ContractViolation("stage-2 envelope has unbound fields")
    if payload.get("schemaVersion") != STAGE2_VERSION:
        raise ContractViolation("stage-2 envelope version is not bound")
    relations = payload.get("relations")
    if not isinstance(relations, Sequence) or isinstance(relations, (str, bytes)):
        raise ContractViolation("stage-2 relations must be an array")
    parsed = validate_stage2_relations(
        relations, candidate_table=candidate_table, source_length=source_length
    )
    required, _ = _abstention(
        payload.get("abstention"), has_items=bool(parsed), field="stage-2 abstention"
    )
    return parsed, required


def _f1(true_positive: int, predicted: int, gold: int) -> float:
    precision = true_positive / predicted if predicted else (1.0 if not gold else 0.0)
    recall = true_positive / gold if gold else (1.0 if not predicted else 0.0)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def score_entity_candidates(
    gold: Sequence[Mapping[str, object]], predicted: Sequence[EntityCandidate]
) -> dict[str, Any]:
    """Score typed entity spans, macro F1, span exactness and hallucination."""

    gold_keys = [(str(item.get("type")), _span(item, "gold entity")) for item in gold]
    predicted_keys = [(item.entity_type, (item.start, item.end)) for item in predicted]
    gold_counter = Counter(gold_keys)
    predicted_counter = Counter(predicted_keys)
    true_positive = sum((gold_counter & predicted_counter).values())
    types = sorted({key[0] for key in set(gold_counter) | set(predicted_counter)})
    by_type: dict[str, dict[str, Any]] = {}
    for entity_type in types:
        type_gold = sum(
            count
            for (candidate_type, _), count in gold_counter.items()
            if candidate_type == entity_type
        )
        type_predicted = sum(
            count
            for (candidate_type, _), count in predicted_counter.items()
            if candidate_type == entity_type
        )
        type_tp = sum(
            (gold_counter & predicted_counter)[key]
            for key in (set(gold_counter) | set(predicted_counter))
            if key[0] == entity_type
        )
        by_type[entity_type] = {
            "gold": type_gold,
            "predicted": type_predicted,
            "truePositive": type_tp,
            "f1": _f1(type_tp, type_predicted, type_gold),
        }
    macro = (
        sum(item["f1"] for item in by_type.values()) / len(by_type)
        if by_type
        else "not-applicable"
    )
    gold_count = len(gold)
    predicted_count = len(predicted)
    return {
        "gold": gold_count,
        "predicted": predicted_count,
        "truePositive": true_positive,
        "entityF1": _f1(true_positive, predicted_count, gold_count),
        "entityMacroF1": macro,
        "byType": by_type,
        "spanExact": sum(
            1
            for item in gold
            if _span(item, "gold entity")
            in {(candidate.start, candidate.end) for candidate in predicted}
        )
        / gold_count
        if gold_count
        else "not-applicable",
        "hallucinationRate": (predicted_count - true_positive) / predicted_count
        if predicted_count
        else 0.0,
        "denominatorReconciled": true_positive <= gold_count
        and true_positive <= predicted_count,
    }


def score_abstention_records(records: Sequence[tuple[bool, bool]]) -> dict[str, Any]:
    """Aggregate abstention precision, recall and F1 from paired cases."""

    true_positive = sum(gold and predicted for gold, predicted in records)
    false_positive = sum((not gold) and predicted for gold, predicted in records)
    false_negative = sum(gold and (not predicted) for gold, predicted in records)
    predicted_count = true_positive + false_positive
    gold_count = true_positive + false_negative
    precision = (
        true_positive / predicted_count
        if predicted_count
        else (1.0 if not gold_count else 0.0)
    )
    recall = (
        true_positive / gold_count
        if gold_count
        else (1.0 if not predicted_count else 0.0)
    )
    return {
        "gold": gold_count,
        "predicted": predicted_count,
        "truePositive": true_positive,
        "falsePositive": false_positive,
        "falseNegative": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0,
    }


def _signature(
    relation: Mapping[str, object] | RelationCandidate,
    entities: Mapping[str, tuple[int, int, str]],
) -> tuple[object, ...]:
    if isinstance(relation, RelationCandidate):
        predicate, source_id, target_id = (
            relation.predicate,
            relation.source_entity_id,
            relation.target_entity_id,
        )
    else:
        predicate, source_id, target_id = (
            str(relation.get("predicate")),
            str(relation.get("sourceEntityId")),
            str(relation.get("targetEntityId")),
        )
    return predicate, entities.get(source_id), entities.get(target_id)


def _evidence_bucket(
    gold_relation: Mapping[str, object],
    predicted: RelationCandidate,
    *,
    gold_entities: Mapping[str, tuple[int, int, str]],
) -> str:
    if (
        predicted.evidence_start is None
        or predicted.evidence_end is None
        or predicted.trigger_quote is None
    ):
        return "missing"
    trigger_digest = str(gold_relation.get("triggerDigest", ""))
    trigger_supported = hashlib.sha256(
        predicted.trigger_quote.encode()
    ).hexdigest() == trigger_digest.removeprefix("sha256:")
    source_span = gold_entities.get(str(gold_relation.get("sourceEntityId")))
    target_span = gold_entities.get(str(gold_relation.get("targetEntityId")))
    if source_span is None or target_span is None or not trigger_supported:
        return "unsupported"
    evidence_span = (predicted.evidence_start, predicted.evidence_end)
    supports_endpoints = (
        evidence_span[0] <= source_span[0]
        and evidence_span[1] >= source_span[1]
        and evidence_span[0] <= target_span[0]
        and evidence_span[1] >= target_span[1]
    )
    if not supports_endpoints:
        return "unsupported"
    return (
        "exact"
        if evidence_span == _span(gold_relation, "gold relation")
        else "supportedNonExact"
    )


def score_relations(
    gold: Sequence[Mapping[str, object]],
    predicted: Sequence[RelationCandidate],
    *,
    gold_entities: Mapping[str, tuple[int, int, str]],
    predicted_entities: Mapping[str, tuple[int, int, str]],
) -> dict[str, Any]:
    """Score approved semantic/evidence axes and all named relation metrics."""

    remaining_gold = set(range(len(gold)))
    remaining_predicted = set(range(len(predicted)))
    semantic = Counter()
    evidence = Counter({bucket: 0 for bucket in EVIDENCE_BUCKETS})
    pairs: list[tuple[int, int]] = []
    gold_signatures = [_signature(item, gold_entities) for item in gold]
    predicted_signatures = [_signature(item, predicted_entities) for item in predicted]

    def pair(gold_index: int, predicted_index: int, bucket: str) -> None:
        remaining_gold.remove(gold_index)
        remaining_predicted.remove(predicted_index)
        semantic[bucket] += 1
        pairs.append((gold_index, predicted_index))

    for gold_index in sorted(remaining_gold):
        match = next(
            (
                index
                for index in sorted(remaining_predicted)
                if gold_signatures[gold_index] == predicted_signatures[index]
            ),
            None,
        )
        if match is not None:
            pair(gold_index, match, "exactMatch")
    for gold_index in sorted(remaining_gold):
        match = next(
            (
                index
                for index in sorted(remaining_predicted)
                if gold_signatures[gold_index][1] == predicted_signatures[index][2]
                and gold_signatures[gold_index][2] == predicted_signatures[index][1]
                and gold_signatures[gold_index][0] == predicted_signatures[index][0]
            ),
            None,
        )
        if match is not None:
            pair(gold_index, match, "reversedEndpoint")
    for gold_index in sorted(remaining_gold):
        match = next(
            (
                index
                for index in sorted(remaining_predicted)
                if gold_signatures[gold_index][1:] == predicted_signatures[index][1:]
                and gold_signatures[gold_index][0] != predicted_signatures[index][0]
            ),
            None,
        )
        if match is not None:
            pair(gold_index, match, "wrongPredicate")
    for gold_index in sorted(remaining_gold):
        match = next(
            (
                index
                for index in sorted(remaining_predicted)
                if gold_signatures[gold_index][0] == predicted_signatures[index][0]
            ),
            None,
        )
        if match is not None:
            pair(gold_index, match, "wrongEndpoint")
    semantic["missingRelation"] = len(remaining_gold)
    semantic["extraRelation"] = len(remaining_predicted)
    for gold_index, predicted_index in pairs:
        if (
            semantic["exactMatch"]
            and gold_signatures[gold_index] == predicted_signatures[predicted_index]
        ):
            evidence[
                _evidence_bucket(
                    gold[gold_index],
                    predicted[predicted_index],
                    gold_entities=gold_entities,
                )
            ] += 1
        else:
            evidence["notApplicable"] += 1

    predicate_counts: dict[str, dict[str, Any]] = {}
    for predicate in sorted(
        {str(item.get("predicate")) for item in gold}
        | {item.predicate for item in predicted}
    ):
        gold_count = sum(item.get("predicate") == predicate for item in gold)
        predicted_count = sum(item.predicate == predicate for item in predicted)
        true_positive = sum(
            gold[g].get("predicate") == predicate
            and predicted[p].predicate == predicate
            and gold_signatures[g] == predicted_signatures[p]
            for g, p in pairs
        )
        predicate_counts[predicate] = {
            "gold": gold_count,
            "predicted": predicted_count,
            "truePositive": true_positive,
            "f1": _f1(true_positive, predicted_count, gold_count),
        }
    macro = (
        sum(item["f1"] for item in predicate_counts.values()) / len(predicate_counts)
        if predicate_counts
        else "not-applicable"
    )
    predicate_correct = sum(
        gold[g].get("predicate") == predicted[p].predicate for g, p in pairs
    )
    predicate_comparable = len(pairs)
    direction_correct = semantic["exactMatch"]
    direction_comparable = sum(
        gold[g].get("predicate") == predicted[p].predicate for g, p in pairs
    )
    semantic_gold = len(gold)
    semantic_predicted = len(predicted)
    semantic_tp = semantic["exactMatch"]
    evidence_applicable = sum(
        evidence[bucket] for bucket in EVIDENCE_BUCKETS if bucket != "notApplicable"
    )
    return {
        "semantic": {
            "counts": {bucket: semantic[bucket] for bucket in SEMANTIC_BUCKETS},
            "gold": semantic_gold,
            "predicted": semantic_predicted,
            "truePositive": semantic_tp,
            "microF1": 2 * semantic_tp / (semantic_gold + semantic_predicted)
            if semantic_gold + semantic_predicted
            else "not-applicable",
            "macroF1": macro,
            "byPredicate": predicate_counts,
            "predicateAccuracy": predicate_correct / predicate_comparable
            if predicate_comparable
            else "not-applicable",
            "endpointDirectionAccuracy": direction_correct / direction_comparable
            if direction_comparable
            else "not-applicable",
            "missingEndpointRate": semantic["wrongEndpoint"] / semantic_gold
            if semantic_gold
            else "not-applicable",
            "reversedEndpointRate": semantic["reversedEndpoint"] / semantic_gold
            if semantic_gold
            else "not-applicable",
            "hallucinationRate": (semantic_predicted - semantic_tp) / semantic_predicted
            if semantic_predicted
            else 0.0,
            "goldReconciled": sum(semantic[bucket] for bucket in SEMANTIC_BUCKETS[:5])
            == semantic_gold,
            "predictedReconciled": semantic["exactMatch"]
            + semantic["wrongPredicate"]
            + semantic["reversedEndpoint"]
            + semantic["wrongEndpoint"]
            + semantic["extraRelation"]
            == semantic_predicted,
        },
        "evidence": {
            "counts": {bucket: evidence[bucket] for bucket in EVIDENCE_BUCKETS},
            "semanticTruePositiveDenominator": semantic_tp,
            "applicable": evidence_applicable,
            "reconciled": evidence_applicable == semantic_tp,
            "supportRate": (evidence["exact"] + evidence["supportedNonExact"])
            / semantic_tp
            if semantic_tp
            else "not-applicable",
            "exactRate": evidence["exact"] / semantic_tp
            if semantic_tp
            else "not-applicable",
        },
    }
