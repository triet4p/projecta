"""RM-40 versioned offline runtime remediation path.

This module is deliberately separate from the issued v8 runner.  It fixes the
diagnostic domain mismatch found by RM-38 without changing the frozen runner,
v8 schema/authentication artifacts, RM-36 execution evidence, or any provider
boundary.  Its only runtime input is a repository-visible case plus a
deterministic score result produced by the caller.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import run_sprint12_f12_stage_a_v2 as v2
import run_sprint12_f12_stage_a_v4 as v4
from s12_f12_rm30_diagnostic_remediation import (
    EVIDENCE_REASON_CODES,
    SanitizedReason,
    diagnose_evidence_failure,
)
from sprint12_f12_two_step_contracts_v2 import _signature

VERSION = "s12-f-12.rm40.offline-runtime.v1"
EXPECTED_PROVIDER_CALLS = 144
EXPECTED_RELATION_BRANCH_OUTPUTS = 96


class RM40ReconciliationError(RuntimeError):
    """Raised when finite diagnostics do not match the scorer denominator."""


def _zero_counts() -> dict[str, int]:
    return {code: 0 for code in EVIDENCE_REASON_CODES}


def project_entity_spans(
    candidates: Sequence[Any],
    gold_candidates: Sequence[Mapping[str, object]],
    *,
    is_gold_arm: bool,
) -> dict[str, tuple[int, int]]:
    """Project typed entity metadata to the two-coordinate classifier shape."""

    if is_gold_arm:
        return {
            str(item["candidateId"]): (
                int(item["startOffset"]),
                int(item["endOffset"]),
            )
            for item in gold_candidates
        }
    return {
        str(item.candidate_id): (int(item.start), int(item.end))
        for item in candidates
    }


def _entity_signatures(
    candidates: Sequence[Any],
    gold_candidates: Sequence[Mapping[str, object]],
    *,
    is_gold_arm: bool,
) -> dict[str, tuple[int, int, str]]:
    if is_gold_arm:
        return {
            str(item["candidateId"]): (
                int(item["startOffset"]),
                int(item["endOffset"]),
                str(item["type"]),
            )
            for item in gold_candidates
        }
    return {
        str(item.candidate_id): (int(item.start), int(item.end), str(item.entity_type))
        for item in candidates
    }


def exact_semantic_pairs(
    case: Mapping[str, Any],
    relations: Sequence[Any],
    predicted_entities: Sequence[Any],
    gold_candidates: Sequence[Mapping[str, object]],
    *,
    is_gold_arm: bool,
) -> tuple[tuple[int, int], ...]:
    """Reproduce score_relations' greedy exact-pair domain, without scoring twice."""

    gold_relations = v4._normalize_gold_relations(case)
    gold_entities = v2._gold_entity_map(case)
    predicted_map = _entity_signatures(
        predicted_entities, gold_candidates, is_gold_arm=is_gold_arm
    )
    remaining_gold = set(range(len(gold_relations)))
    remaining_predicted = set(range(len(relations)))
    pairs: list[tuple[int, int]] = []
    for gold_index in sorted(remaining_gold):
        gold = gold_relations[gold_index]
        gold_signature = _signature(gold, gold_entities)
        match = next(
            (
                index
                for index in sorted(remaining_predicted)
                if gold_signature == _signature(relations[index], predicted_map)
            ),
            None,
        )
        if match is not None:
            remaining_gold.remove(gold_index)
            remaining_predicted.remove(match)
            pairs.append((gold_index, match))
    return tuple(pairs)


def _relation_key(relation: Any) -> tuple[str, str, str]:
    return (
        str(relation.predicate),
        str(relation.source_entity_id),
        str(relation.target_entity_id),
    )


def diagnose_arm(
    case: Mapping[str, Any],
    *,
    relations: Sequence[Any],
    predicted_entities: Sequence[Any],
    gold_candidates: Sequence[Mapping[str, object]],
    is_gold_arm: bool,
    score_result: Mapping[str, Any],
) -> dict[str, Any]:
    """Diagnose only exact semantic pairs and reconcile against the scorer."""

    pairs = exact_semantic_pairs(
        case,
        relations,
        predicted_entities,
        gold_candidates,
        is_gold_arm=is_gold_arm,
    )
    contexts = v4._contexts(case)
    spans = project_entity_spans(
        predicted_entities, gold_candidates, is_gold_arm=is_gold_arm
    )
    counts = _zero_counts()
    for _, predicted_index in pairs:
        relation = relations[predicted_index]
        reason = diagnose_evidence_failure(
            relation,
            context=contexts.get(_relation_key(relation)),
            endpoint_spans=(
                spans.get(str(relation.source_entity_id)),
                spans.get(str(relation.target_entity_id)),
            ),
        )
        if reason is not None:
            counts[reason.code] += 1

    evidence_counts = score_result["relation"]["evidence"]["counts"]
    invalid_evidence = int(evidence_counts.get("unsupported", 0)) + int(
        evidence_counts.get("missing", 0)
    )
    diagnostic_total = sum(counts.values())
    if diagnostic_total != invalid_evidence:
        raise RM40ReconciliationError(
            "evidence reason counts do not reconcile with exact-pair arm materializer failures"
        )
    return {
        "version": VERSION,
        "exactSemanticPairCount": len(pairs),
        "exactSemanticPairs": [list(pair) for pair in pairs],
        "materializerInvalidEvidenceCount": invalid_evidence,
        "evidenceReasonCounts": counts,
        "reasonCountsReconciled": True,
        "rawDataIncluded": False,
    }


def prospective_custody(*, output_exists_before: bool = False) -> dict[str, Any]:
    """Return a zero-provider custody contract for the future implementation."""

    if output_exists_before:
        raise RM40ReconciliationError("refusing to overwrite an existing output")
    return {
        "version": VERSION,
        "providerCalls": 0,
        "plannedProviderCalls": EXPECTED_PROVIDER_CALLS,
        "plannedRelationBranchOutputs": EXPECTED_RELATION_BRANCH_OUTPUTS,
        "retryCount": 0,
        "persistCount": 1,
        "overwriteRejected": True,
        "rawProviderPayloadIncluded": False,
        "rawSourceTextIncluded": False,
        "rawValidationDetailIncluded": False,
        "providerExecutionAuthorized": False,
    }


def allowed_reason_codes() -> tuple[str, ...]:
    return EVIDENCE_REASON_CODES
