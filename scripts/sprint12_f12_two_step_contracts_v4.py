"""Offline RM-20C remediation for typed identity and materialized triggers."""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sprint12_f12_two_step_contracts_v2 import (
    EVIDENCE_BUCKETS,
    SEMANTIC_BUCKETS,
    ContractViolation,
    EntityCandidate,
    RelationCandidate,
    _f1,
    _signature,
    _span,
    score_abstention_records,
    score_entity_candidates,
    validate_stage1_candidates,
    validate_stage1_response,
    validate_stage2_relations,
    validate_stage2_response,
)

__all__ = [
    "ContractViolation",
    "EntityCandidate",
    "EvidenceContext",
    "RelationCandidate",
    "TriggerOccurrence",
    "score_abstention_records",
    "score_entity_candidates",
    "score_relations",
    "validate_stage1_candidates",
    "validate_stage1_response",
    "validate_stage2_relations",
    "validate_stage2_response",
]


@dataclass(frozen=True, slots=True)
class TriggerOccurrence:
    start: int
    end: int
    quote_digest: str


@dataclass(frozen=True, slots=True)
class EvidenceContext:
    """Server-owned occurrence and selected-boundary metadata."""

    source_length: int
    trigger_occurrences: tuple[TriggerOccurrence, ...]
    sentence: tuple[int, int]
    clause: tuple[int, int]


def _inside(inner: tuple[int, int], outer: tuple[int, int]) -> bool:
    return outer[0] <= inner[0] and inner[1] <= outer[1]


def _valid_boundary(span: tuple[int, int], source_length: int) -> bool:
    return 0 <= span[0] < span[1] <= source_length


def _trigger_supported(
    gold_relation: Mapping[str, object],
    predicted: RelationCandidate,
    context: EvidenceContext | None,
) -> bool:
    if predicted.trigger_quote is None or context is None:
        return False
    quote_digest = hashlib.sha256(predicted.trigger_quote.encode()).hexdigest()
    expected_digest = str(gold_relation.get("triggerDigest", "")).removeprefix(
        "sha256:"
    )
    if (
        quote_digest != expected_digest
        or not _valid_boundary(context.sentence, context.source_length)
        or not _valid_boundary(context.clause, context.source_length)
        or not _inside(context.clause, context.sentence)
    ):
        return False
    evidence = (predicted.evidence_start, predicted.evidence_end)
    if (
        evidence[0] is None
        or evidence[1] is None
        or not _valid_boundary((evidence[0], evidence[1]), context.source_length)
    ):
        return False
    valid_occurrences = []
    for occurrence in context.trigger_occurrences:
        occurrence_span = (occurrence.start, occurrence.end)
        if not _valid_boundary(occurrence_span, context.source_length):
            continue
        if occurrence.end - occurrence.start != len(predicted.trigger_quote):
            continue
        if occurrence.quote_digest.removeprefix("sha256:") != quote_digest:
            continue
        if (
            _inside(occurrence_span, context.sentence)
            and _inside(occurrence_span, context.clause)
            and _inside(occurrence_span, evidence)
        ):
            valid_occurrences.append(occurrence)
    return len(valid_occurrences) == 1


def _evidence_bucket(
    gold_relation: Mapping[str, object],
    predicted: RelationCandidate,
    *,
    gold_entities: Mapping[str, tuple[int, int, str]],
    context: EvidenceContext | None,
) -> str:
    if (
        predicted.evidence_start is None
        or predicted.evidence_end is None
        or predicted.trigger_quote is None
    ):
        return "missing"
    if not _trigger_supported(gold_relation, predicted, context):
        return "unsupported"
    source_span = gold_entities.get(str(gold_relation.get("sourceEntityId")))
    target_span = gold_entities.get(str(gold_relation.get("targetEntityId")))
    evidence_span = (predicted.evidence_start, predicted.evidence_end)
    if (
        source_span is None
        or target_span is None
        or not (
            _inside(source_span, evidence_span) and _inside(target_span, evidence_span)
        )
    ):
        return "unsupported"
    return (
        "exact"
        if evidence_span == _span(gold_relation, "gold relation")
        else "supportedNonExact"
    )


def _endpoint_resolution(
    gold: Sequence[Mapping[str, object]],
    *,
    gold_entities: Mapping[str, tuple[int, int, str]],
    predicted_entities: Mapping[str, tuple[int, int, str]],
) -> dict[str, Any]:
    typed_spans: dict[tuple[int, int, str], list[str]] = {}
    for candidate_id, signature in predicted_entities.items():
        typed_spans.setdefault(signature, []).append(candidate_id)
    used: set[str] = set()
    resolved = 0
    missing = 0
    wrong = 0
    for relation in gold:
        for field in ("sourceEntityId", "targetEntityId"):
            gold_id = str(relation.get(field))
            expected = gold_entities.get(gold_id)
            matches = typed_spans.get(expected, []) if expected is not None else []
            if len(matches) == 1 and matches[0] not in used:
                used.add(matches[0])
                resolved += 1
            elif (
                matches
                or gold_id in predicted_entities
                or (
                    expected is not None
                    and (
                        any(
                            candidate[2] == expected[2]
                            for candidate in predicted_entities.values()
                        )
                        or any(
                            candidate[0:2] == expected[0:2]
                            for candidate in predicted_entities.values()
                        )
                    )
                )
            ):
                wrong += 1
            else:
                missing += 1
    denominator = 2 * len(gold)
    return {
        "resolved": resolved,
        "wrong": wrong,
        "missing": missing,
        "denominator": denominator,
        "missingEndpointRate": missing / denominator
        if denominator
        else "not-applicable",
        "wrongEndpointRate": wrong / denominator if denominator else "not-applicable",
        "reconciled": resolved + wrong + missing == denominator,
    }


def score_relations(
    gold: Sequence[Mapping[str, object]],
    predicted: Sequence[RelationCandidate],
    *,
    gold_entities: Mapping[str, tuple[int, int, str]],
    predicted_entities: Mapping[str, tuple[int, int, str]],
    evidence_contexts: Mapping[tuple[str, str, str], EvidenceContext],
) -> dict[str, Any]:
    """Score relations with local-ID-independent identity and occurrence custody."""

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
                if gold_signatures[gold_index][0] == predicted_signatures[index][0]
                and gold_signatures[gold_index][1] == predicted_signatures[index][2]
                and gold_signatures[gold_index][2] == predicted_signatures[index][1]
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
            relation = predicted[predicted_index]
            key = (
                relation.predicate,
                relation.source_entity_id,
                relation.target_entity_id,
            )
            evidence[
                _evidence_bucket(
                    gold[gold_index],
                    relation,
                    gold_entities=gold_entities,
                    context=evidence_contexts.get(key),
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
    semantic_gold = len(gold)
    semantic_predicted = len(predicted)
    semantic_tp = semantic["exactMatch"]
    predicate_correct = sum(
        gold[g].get("predicate") == predicted[p].predicate for g, p in pairs
    )
    endpoint_resolution = _endpoint_resolution(
        gold, gold_entities=gold_entities, predicted_entities=predicted_entities
    )
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
            "macroF1": sum(item["f1"] for item in predicate_counts.values())
            / len(predicate_counts)
            if predicate_counts
            else "not-applicable",
            "byPredicate": predicate_counts,
            "predicateAccuracy": predicate_correct / len(pairs)
            if pairs
            else "not-applicable",
            "endpointDirectionAccuracy": semantic["exactMatch"] / predicate_correct
            if predicate_correct
            else "not-applicable",
            "missingEndpointRate": endpoint_resolution["missingEndpointRate"],
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
        "endpointResolution": endpoint_resolution,
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
