"""Offline contract, oracle and bucket-scorer tests for S12-f-12."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sprint12_f12_two_step_contracts import (
    ContractViolation,
    score_entity_candidates,
    score_relations,
    validate_stage1_candidates,
    validate_stage2_relations,
)

FIXTURES = ROOT / "evaluation/sprint-12/harness/s12-f-12-oracle-fixtures.v1.json"


def _fixture(fixture_id: str) -> dict[str, object]:
    payload = json.loads(FIXTURES.read_text(encoding="utf-8"))
    return next(item for item in payload["fixtures"] if item["id"] == fixture_id)


def _entities(items: list[dict[str, object]]) -> dict[str, tuple[int, int, str]]:
    return {
        str(item["id"]): (
            int(item["startOffset"]),
            int(item["endOffset"]),
            str(item["type"]),
        )
        for item in items
    }


def test_gold_relations_integrity_control_is_exact_and_zero_failure() -> None:
    fixture = _fixture("gold-relations-integrity")
    candidates = validate_stage1_candidates(fixture["candidateTable"], source_length=40)
    predicted = validate_stage2_relations(
        fixture["predictedRelations"], candidate_table=candidates, source_length=40
    )
    result = score_relations(
        fixture["goldRelations"],
        predicted,
        gold_entities=_entities(fixture["goldEntities"]),
        predicted_entities={
            item.candidate_id: (item.start, item.end, item.entity_type)
            for item in candidates
        },
    )
    assert result["semantic"]["microF1"] == 1.0
    assert result["semantic"]["goldReconciled"] is True
    assert result["semantic"]["predictedReconciled"] is True
    assert result["evidence"]["counts"] == {
        "exact": 1,
        "supportedNonExact": 0,
        "unsupported": 0,
        "missing": 0,
        "notApplicable": 0,
    }
    assert result["evidence"]["reconciled"] is True


def test_semantic_and_evidence_axes_are_mutually_reconciled() -> None:
    fixture = _fixture("semantic-buckets")
    candidates = validate_stage1_candidates(
        fixture["candidateTable"], source_length=100
    )
    result = score_relations(
        fixture["goldRelations"],
        validate_stage2_relations(
            fixture["predictedRelations"], candidate_table=candidates, source_length=100
        ),
        gold_entities=_entities(fixture["goldEntities"]),
        predicted_entities={
            item.candidate_id: (item.start, item.end, item.entity_type)
            for item in candidates
        },
    )
    assert result["semantic"]["counts"] == {
        "exactMatch": 1,
        "wrongPredicate": 1,
        "reversedEndpoint": 1,
        "wrongEndpoint": 1,
        "missingRelation": 0,
        "extraRelation": 1,
    }
    assert result["semantic"]["goldReconciled"] is True
    assert result["semantic"]["predictedReconciled"] is True

    evidence_fixture = _fixture("evidence-buckets")
    evidence_candidates = validate_stage1_candidates(
        evidence_fixture["candidateTable"], source_length=100
    )
    evidence_result = score_relations(
        evidence_fixture["goldRelations"],
        validate_stage2_relations(
            evidence_fixture["predictedRelations"],
            candidate_table=evidence_candidates,
            source_length=100,
        ),
        gold_entities=_entities(evidence_fixture["goldEntities"]),
        predicted_entities={
            item.candidate_id: (item.start, item.end, item.entity_type)
            for item in evidence_candidates
        },
    )
    assert evidence_result["evidence"]["counts"] == {
        "exact": 1,
        "supportedNonExact": 1,
        "unsupported": 1,
        "missing": 1,
        "notApplicable": 0,
    }
    assert evidence_result["evidence"]["reconciled"] is True


def test_entity_scorer_reports_span_and_hallucination_denominators() -> None:
    fixture = _fixture("gold-relations-integrity")
    candidates = validate_stage1_candidates(fixture["candidateTable"], source_length=40)
    result = score_entity_candidates(fixture["goldEntities"], candidates)
    assert result["gold"] == 2
    assert result["predicted"] == 2
    assert result["entityF1"] == 1.0
    assert result["spanExact"] == 1.0
    assert result["hallucinationRate"] == 0.0


@pytest.mark.parametrize(
    "payload",
    [
        [
            {
                "candidateId": "e1",
                "type": "Task",
                "startOffset": 0,
                "endOffset": 2,
                "confidence": 1.0,
                "label": "server-owned",
            }
        ],
        [
            {
                "candidateId": "e1",
                "type": "Task",
                "startOffset": 0,
                "endOffset": 2,
                "confidence": 1.0,
            },
            {
                "candidateId": "e2",
                "type": "Task",
                "startOffset": 0,
                "endOffset": 2,
                "confidence": 1.0,
            },
        ],
    ],
)
def test_stage1_rejects_server_fields_and_duplicate_typed_spans(
    payload: list[dict[str, object]],
) -> None:
    with pytest.raises(ContractViolation):
        validate_stage1_candidates(payload, source_length=10)


def test_stage2_cannot_create_or_mutate_entities_and_has_zero_call_contract() -> None:
    table = validate_stage1_candidates(
        [
            {
                "candidateId": "e1",
                "type": "Task",
                "startOffset": 0,
                "endOffset": 2,
                "confidence": 1.0,
            },
            {
                "candidateId": "e2",
                "type": "Risk",
                "startOffset": 4,
                "endOffset": 6,
                "confidence": 1.0,
            },
        ],
        source_length=10,
    )
    with pytest.raises(ContractViolation, match="mutate"):
        validate_stage2_relations(
            [
                {
                    "predicate": "supports",
                    "sourceEntityId": "e1",
                    "targetEntityId": "e2",
                    "confidence": 1.0,
                    "type": "Task",
                }
            ],
            candidate_table=table,
            source_length=10,
        )
    with pytest.raises(ContractViolation, match="unknown"):
        validate_stage2_relations(
            [
                {
                    "predicate": "supports",
                    "sourceEntityId": "e1",
                    "targetEntityId": "e9",
                    "confidence": 1.0,
                }
            ],
            candidate_table=table,
            source_length=10,
        )
