"""Offline contracts and deterministic scoring for the approved f12 design."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

ENTITY_TYPES = {
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
PREDICATES = {
    "implements",
    "blocks",
    "dependsOn",
    "supports",
    "answers",
    "resolves",
    "constrainedBy",
}
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


class ContractViolation(ValueError):
    """Raised when an arm attempts to cross a server-owned boundary."""


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


def validate_stage1_candidates(
    payload: Sequence[Mapping[str, object]], *, source_length: int
) -> tuple[EntityCandidate, ...]:
    """Validate model-proposed stage-1 spans before server materialization."""

    candidates: list[EntityCandidate] = []
    seen: set[str] = set()
    seen_spans: set[tuple[str, int, int]] = set()
    for index, item in enumerate(payload):
        unexpected = set(item) - {
            "candidateId",
            "type",
            "startOffset",
            "endOffset",
            "confidence",
        }
        if unexpected:
            raise ContractViolation("stage-1 response contains server-owned fields")
        candidate_id = _text(item.get("candidateId"), f"entities[{index}].candidateId")
        entity_type = _text(item.get("type"), f"entities[{index}].type")
        if entity_type not in ENTITY_TYPES:
            raise ContractViolation(f"entities[{index}].type is not allowlisted")
        start, end = _span(item, f"entities[{index}]")
        if end > source_length:
            raise ContractViolation(f"entities[{index}] span exceeds source length")
        if candidate_id in seen:
            raise ContractViolation("stage-1 candidateId values must be unique")
        if (entity_type, start, end) in seen_spans:
            raise ContractViolation("stage-1 typed spans must be unique")
        seen.add(candidate_id)
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


def validate_stage2_relations(
    payload: Sequence[Mapping[str, object]],
    *,
    candidate_table: Sequence[EntityCandidate],
    source_length: int | None = None,
) -> tuple[RelationCandidate, ...]:
    """Validate stage-2 references without permitting entity mutation."""

    allowed_ids = {candidate.candidate_id for candidate in candidate_table}
    relations: list[RelationCandidate] = []
    seen_relations: set[tuple[str, str, str]] = set()
    for index, item in enumerate(payload):
        unexpected = set(item) - {
            "predicate",
            "sourceEntityId",
            "targetEntityId",
            "confidence",
            "evidence",
        }
        if unexpected:
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
        if source_id not in allowed_ids or target_id not in allowed_ids:
            raise ContractViolation(
                "stage-2 relation references an unknown candidateId"
            )
        if source_id == target_id:
            raise ContractViolation("stage-2 self-relations are not permitted")
        relation_key = (predicate, source_id, target_id)
        if relation_key in seen_relations:
            raise ContractViolation("stage-2 relation identities must be unique")
        seen_relations.add(relation_key)
        evidence = item.get("evidence")
        evidence_start: int | None = None
        evidence_end: int | None = None
        if evidence is not None:
            if not isinstance(evidence, Mapping):
                raise ContractViolation(
                    f"relations[{index}].evidence must be an object"
                )
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
            )
        )
    return tuple(relations)


def score_entity_candidates(
    gold: Sequence[Mapping[str, object]],
    predicted: Sequence[EntityCandidate],
) -> dict[str, Any]:
    """Score exact typed spans and return reconciled denominators."""

    gold_keys = [(str(item.get("type")), _span(item, "gold entity")) for item in gold]
    predicted_keys = [(item.entity_type, (item.start, item.end)) for item in predicted]
    gold_counter = Counter(gold_keys)
    predicted_counter = Counter(predicted_keys)
    true_positive = sum((gold_counter & predicted_counter).values())
    predicted_count = len(predicted)
    gold_count = len(gold)
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
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    span_exact = sum(
        1
        for gold_item in gold
        if _span(gold_item, "gold entity")
        in {(item.start, item.end) for item in predicted}
    )
    return {
        "gold": gold_count,
        "predicted": predicted_count,
        "truePositive": true_positive,
        "entityF1": f1,
        "spanExact": span_exact / gold_count if gold_count else "not-applicable",
        "hallucinationRate": (predicted_count - true_positive) / predicted_count
        if predicted_count
        else 0.0,
        "denominatorReconciled": true_positive <= gold_count
        and true_positive <= predicted_count,
    }


def score_abstention(
    *, gold_required: bool, predicted_required: bool
) -> dict[str, Any]:
    """Return one-case abstention evidence; aggregate externally by case."""

    return {
        "goldRequired": gold_required,
        "predictedRequired": predicted_required,
        "correct": gold_required == predicted_required,
    }


def _endpoint_signature(
    relation: Mapping[str, object] | RelationCandidate,
    entities: Mapping[str, tuple[int, int, str]],
) -> tuple[object, ...]:
    if isinstance(relation, RelationCandidate):
        source_id = relation.source_entity_id
        target_id = relation.target_entity_id
        predicate = relation.predicate
    else:
        source_id = str(relation.get("sourceEntityId"))
        target_id = str(relation.get("targetEntityId"))
        predicate = str(relation.get("predicate"))
    return (
        predicate,
        entities.get(source_id),
        entities.get(target_id),
    )


def _evidence_bucket(
    gold_relation: Mapping[str, object],
    predicted_relation: RelationCandidate,
    *,
    gold_entities: Mapping[str, tuple[int, int, str]],
) -> str:
    if (
        predicted_relation.evidence_start is None
        or predicted_relation.evidence_end is None
    ):
        return "missing"
    gold_span = _span(gold_relation, "gold relation")
    if gold_span == (
        predicted_relation.evidence_start,
        predicted_relation.evidence_end,
    ):
        return "exact"
    source_span = gold_entities.get(str(gold_relation.get("sourceEntityId")))
    target_span = gold_entities.get(str(gold_relation.get("targetEntityId")))
    if source_span is None or target_span is None:
        return "unsupported"
    supports_endpoints = (
        predicted_relation.evidence_start <= source_span[0]
        and predicted_relation.evidence_end >= source_span[1]
        and predicted_relation.evidence_start <= target_span[0]
        and predicted_relation.evidence_end >= target_span[1]
    )
    return "supportedNonExact" if supports_endpoints else "unsupported"


def score_relations(
    gold: Sequence[Mapping[str, object]],
    predicted: Sequence[RelationCandidate],
    *,
    gold_entities: Mapping[str, tuple[int, int, str]],
    predicted_entities: Mapping[str, tuple[int, int, str]],
) -> dict[str, Any]:
    """Score mutually exclusive semantic buckets and independent evidence buckets."""

    remaining_gold = set(range(len(gold)))
    remaining_predicted = set(range(len(predicted)))
    semantic = Counter()
    evidence = Counter({bucket: 0 for bucket in EVIDENCE_BUCKETS})
    pairs: list[tuple[int, int]] = []

    def pair(gold_index: int, predicted_index: int, bucket: str) -> None:
        remaining_gold.remove(gold_index)
        remaining_predicted.remove(predicted_index)
        semantic[bucket] += 1
        pairs.append((gold_index, predicted_index))

    gold_signatures = [_endpoint_signature(item, gold_entities) for item in gold]
    predicted_signatures = [
        _endpoint_signature(item, predicted_entities) for item in predicted
    ]

    for gold_index in sorted(remaining_gold):
        match = next(
            (
                predicted_index
                for predicted_index in sorted(remaining_predicted)
                if gold_signatures[gold_index] == predicted_signatures[predicted_index]
            ),
            None,
        )
        if match is not None:
            pair(gold_index, match, "exactMatch")
    for gold_index in sorted(remaining_gold):
        match = next(
            (
                predicted_index
                for predicted_index in sorted(remaining_predicted)
                if gold[gold_index].get("predicate")
                == predicted[predicted_index].predicate
                and gold_signatures[gold_index][1]
                == predicted_signatures[predicted_index][2]
                and gold_signatures[gold_index][2]
                == predicted_signatures[predicted_index][1]
            ),
            None,
        )
        if match is not None:
            pair(gold_index, match, "reversedEndpoint")
    for gold_index in sorted(remaining_gold):
        match = next(
            (
                predicted_index
                for predicted_index in sorted(remaining_predicted)
                if gold_signatures[gold_index][1:]
                == predicted_signatures[predicted_index][1:]
                and gold[gold_index].get("predicate")
                != predicted[predicted_index].predicate
            ),
            None,
        )
        if match is not None:
            pair(gold_index, match, "wrongPredicate")
    for gold_index in sorted(remaining_gold):
        match = next(
            (
                predicted_index
                for predicted_index in sorted(remaining_predicted)
                if gold[gold_index].get("predicate")
                == predicted[predicted_index].predicate
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
            "goldReconciled": sum(semantic[bucket] for bucket in SEMANTIC_BUCKETS[:5])
            == semantic_gold,
            "predictedReconciled": sum(
                semantic[bucket]
                for bucket in SEMANTIC_BUCKETS[:1] + SEMANTIC_BUCKETS[1:5]
            )
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
