"""Offline RM-20D remediation for reusable endpoint maps and source proof."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sprint12_f12_two_step_contracts_v4 import (
    ContractViolation,
    EntityCandidate,
    RelationCandidate,
    score_abstention_records,
    score_entity_candidates,
    validate_stage1_candidates,
    validate_stage1_response,
    validate_stage2_relations,
    validate_stage2_response,
)
from sprint12_f12_two_step_contracts_v4 import (
    EvidenceContext as V4EvidenceContext,
)
from sprint12_f12_two_step_contracts_v4 import (
    TriggerOccurrence as V4TriggerOccurrence,
)
from sprint12_f12_two_step_contracts_v4 import (
    score_relations as _score_relations_v4,
)

__all__ = [
    "ContractViolation",
    "EntityCandidate",
    "EvidenceContext",
    "RelationCandidate",
    "TriggerOccurrence",
    "materialize_evidence_context",
    "materialize_trigger_occurrence",
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
    """Runtime-only source plus sanitized occurrence and boundary metadata."""

    source_length: int
    source_digest: str
    source_text: str
    trigger_occurrences: tuple[TriggerOccurrence, ...]
    sentence: tuple[int, int]
    clause: tuple[int, int]


def materialize_trigger_occurrence(
    source_text: str, start: int, end: int
) -> TriggerOccurrence | None:
    """Derive sanitized occurrence metadata from the runtime source slice."""

    if not 0 <= start < end <= len(source_text):
        return None
    source_slice = source_text[start:end]
    return TriggerOccurrence(
        start, end, "sha256:" + hashlib.sha256(source_slice.encode()).hexdigest()
    )


def materialize_evidence_context(
    source_text: str,
    occurrence_spans: Sequence[tuple[int, int]],
    *,
    sentence: tuple[int, int],
    clause: tuple[int, int],
) -> EvidenceContext:
    """Create custody metadata without persisting raw source text in reports."""

    occurrences = tuple(
        occurrence
        for start, end in occurrence_spans
        if (occurrence := materialize_trigger_occurrence(source_text, start, end))
        is not None
    )
    return EvidenceContext(
        len(source_text),
        "sha256:" + hashlib.sha256(source_text.encode()).hexdigest(),
        source_text,
        occurrences,
        sentence,
        clause,
    )


def _source_proof(context: EvidenceContext, trigger_quote: str | None) -> bool:
    if trigger_quote is None or len(context.source_text) != context.source_length:
        return False
    if (
        "sha256:" + hashlib.sha256(context.source_text.encode()).hexdigest()
        != context.source_digest
    ):
        return False
    if (
        not 0 <= context.sentence[0] < context.sentence[1] <= context.source_length
        or not 0 <= context.clause[0] < context.clause[1] <= context.source_length
    ):
        return False
    for occurrence in context.trigger_occurrences:
        if not 0 <= occurrence.start < occurrence.end <= context.source_length:
            return False
        source_slice = context.source_text[occurrence.start : occurrence.end]
        if source_slice != trigger_quote or occurrence.end - occurrence.start != len(
            trigger_quote
        ):
            continue
        digest = "sha256:" + hashlib.sha256(source_slice.encode()).hexdigest()
        if occurrence.quote_digest == digest:
            return True
    return False


def _endpoint_resolution(
    gold: Sequence[Mapping[str, object]],
    *,
    gold_entities: Mapping[str, tuple[int, int, str]],
    predicted_entities: Mapping[str, tuple[int, int, str]],
) -> dict[str, Any]:
    """Map distinct gold entities once, then reuse that map for every slot."""

    typed_spans: dict[tuple[int, int, str], list[str]] = {}
    for candidate_id, signature in predicted_entities.items():
        typed_spans.setdefault(signature, []).append(candidate_id)
    statuses: dict[str, str] = {}
    for gold_id, expected in gold_entities.items():
        matches = typed_spans.get(expected, [])
        if len(matches) == 1:
            statuses[gold_id] = "resolved"
        elif (
            matches
            or gold_id in predicted_entities
            or any(
                candidate[2] == expected[2] or candidate[:2] == expected[:2]
                for candidate in predicted_entities.values()
            )
        ):
            statuses[gold_id] = "wrong"
        else:
            statuses[gold_id] = "missing"
    resolved = wrong = missing = 0
    for relation in gold:
        for field in ("sourceEntityId", "targetEntityId"):
            status = statuses.get(str(relation.get(field)), "missing")
            if status == "resolved":
                resolved += 1
            elif status == "wrong":
                wrong += 1
            else:
                missing += 1
    denominator = 2 * len(gold)
    return {
        "resolved": resolved,
        "wrong": wrong,
        "missing": missing,
        "denominator": denominator,
        "mappingEntityCount": len(statuses),
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
    """Score using reusable identity mapping and source-derived occurrence proof."""

    safe_contexts: dict[tuple[str, str, str], V4EvidenceContext] = {}
    for relation in predicted:
        key = (relation.predicate, relation.source_entity_id, relation.target_entity_id)
        context = evidence_contexts.get(key)
        if context is None or not _source_proof(context, relation.trigger_quote):
            continue
        safe_contexts[key] = V4EvidenceContext(
            context.source_length,
            tuple(
                V4TriggerOccurrence(item.start, item.end, item.quote_digest)
                for item in context.trigger_occurrences
            ),
            context.sentence,
            context.clause,
        )
    result = _score_relations_v4(
        gold,
        predicted,
        gold_entities=gold_entities,
        predicted_entities=predicted_entities,
        evidence_contexts=safe_contexts,
    )
    endpoint_resolution = _endpoint_resolution(
        gold, gold_entities=gold_entities, predicted_entities=predicted_entities
    )
    result["endpointResolution"] = endpoint_resolution
    result["semantic"]["missingEndpointRate"] = endpoint_resolution[
        "missingEndpointRate"
    ]
    return result
