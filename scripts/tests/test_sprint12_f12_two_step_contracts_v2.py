import pytest
from sprint12_f12_two_step_contracts_v2 import (
    ContractViolation,
    score_abstention_records,
    score_entity_candidates,
    score_relations,
    validate_stage1_response,
    validate_stage2_response,
)


def _entities():
    return [
        {
            "candidateId": "e1",
            "type": "Task",
            "startOffset": 0,
            "endOffset": 5,
            "confidence": 1.0,
        },
        {
            "candidateId": "e2",
            "type": "Requirement",
            "startOffset": 20,
            "endOffset": 30,
            "confidence": 1.0,
        },
    ]


def _stage1():
    return {
        "schemaVersion": "s12-f-12.stage1.entity-envelope.v2",
        "entities": _entities(),
        "abstention": {"required": False, "reason": None},
    }


def _stage2():
    return {
        "schemaVersion": "s12-f-12.stage2.relation-envelope.v2",
        "relations": [
            {
                "predicate": "supports",
                "sourceEntityId": "e1",
                "targetEntityId": "e2",
                "confidence": 1.0,
                "triggerQuote": "supports",
                "evidence": {"startOffset": 0, "endOffset": 30},
            }
        ],
        "abstention": {"required": False, "reason": None},
    }


def test_envelopes_validate_and_preserve_abstention_contract():
    candidates, abstained = validate_stage1_response(_stage1(), source_length=40)
    relations, relation_abstained = validate_stage2_response(
        _stage2(), candidate_table=candidates, source_length=40
    )
    assert len(relations) == 1 and not abstained and not relation_abstained
    empty = {
        "schemaVersion": "s12-f-12.stage1.entity-envelope.v2",
        "entities": [],
        "abstention": {"required": True, "reason": "none"},
    }
    assert validate_stage1_response(empty, source_length=40)[1]


def test_envelope_rejects_relation_without_trigger_quote():
    response = _stage2()
    response["relations"][0]["triggerQuote"] = ""
    candidates, _ = validate_stage1_response(_stage1(), source_length=40)
    with pytest.raises(ContractViolation):
        validate_stage2_response(response, candidate_table=candidates, source_length=40)


def test_entity_score_reports_macro_by_type_and_abstention_metrics():
    candidates, _ = validate_stage1_response(_stage1(), source_length=40)
    score = score_entity_candidates(
        [{**item, "id": item["candidateId"]} for item in _entities()], candidates
    )
    assert score["entityMacroF1"] == 1.0
    assert set(score["byType"]) == {"Task", "Requirement"}
    assert score_abstention_records([(True, True), (False, False)])["f1"] == 1.0


def test_relation_score_requires_predicate_trigger_for_evidence_support():
    candidates, _ = validate_stage1_response(_stage1(), source_length=40)
    relations, _ = validate_stage2_response(
        _stage2(), candidate_table=candidates, source_length=40
    )
    entities = {"e1": (0, 5, "Task"), "e2": (20, 30, "Requirement")}
    gold = [
        {
            "predicate": "supports",
            "sourceEntityId": "e1",
            "targetEntityId": "e2",
            "startOffset": 0,
            "endOffset": 30,
            "triggerDigest": "sha256:66312e5e57ebd0b4fff4ef544c5a4abd86f89a0e2f003d9209dad1a641694bca",
        }
    ]
    score = score_relations(
        gold, relations, gold_entities=entities, predicted_entities=entities
    )
    assert score["semantic"]["macroF1"] == 1.0
    assert score["evidence"]["counts"]["exact"] == 1
