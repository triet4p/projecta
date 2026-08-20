from sprint12_f12_two_step_contracts_v3 import (
    EvidenceContext,
    RelationCandidate,
    score_relations,
)

GOLD_ENTITIES = {"e1": (0, 5, "Task"), "e2": (20, 30, "Requirement")}
GOLD_RELATION = {
    "predicate": "supports",
    "sourceEntityId": "e1",
    "targetEntityId": "e2",
    "startOffset": 0,
    "endOffset": 30,
    "triggerDigest": "sha256:66312e5e57ebd0b4fff4ef544c5a4abd86f89a0e2f003d9209dad1a641694bca",
}
PREDICTED_RELATION = RelationCandidate("supports", "e1", "e2", 1, 0, 30, "supports")
GOOD_CONTEXT = {
    ("supports", "e1", "e2"): EvidenceContext(((10, 18),), (0, 40), (0, 30))
}


def test_missing_endpoint_rate_uses_absent_candidate_slots_not_wrong_endpoint():
    drifted = score_relations(
        [GOLD_RELATION],
        [PREDICTED_RELATION],
        gold_entities=GOLD_ENTITIES,
        predicted_entities={"e1": (0, 5, "Task"), "e2": (20, 29, "Requirement")},
        evidence_contexts=GOOD_CONTEXT,
    )
    absent = score_relations(
        [GOLD_RELATION],
        [PREDICTED_RELATION],
        gold_entities=GOLD_ENTITIES,
        predicted_entities={"e1": (0, 5, "Task")},
        evidence_contexts=GOOD_CONTEXT,
    )
    wrong_entity = score_relations(
        [GOLD_RELATION],
        [PREDICTED_RELATION],
        gold_entities=GOLD_ENTITIES,
        predicted_entities={"e1": (0, 5, "Task"), "e2": (40, 48, "Decision")},
        evidence_contexts=GOOD_CONTEXT,
    )
    assert drifted["semantic"]["missingEndpointRate"] == 0.0
    assert drifted["endpointResolution"]["wrong"] == 1
    assert absent["semantic"]["missingEndpointRate"] == 0.5
    assert wrong_entity["endpointResolution"]["wrong"] == 1


def test_reversed_endpoint_is_not_missing_endpoint():
    reversed_relation = RelationCandidate("supports", "e2", "e1", 1, 0, 30, "supports")
    score = score_relations(
        [GOLD_RELATION],
        [reversed_relation],
        gold_entities=GOLD_ENTITIES,
        predicted_entities=GOLD_ENTITIES,
        evidence_contexts={},
    )
    assert score["semantic"]["reversedEndpointRate"] == 1.0
    assert score["semantic"]["missingEndpointRate"] == 0.0


def test_trigger_must_have_one_occurrence_inside_selected_sentence_and_clause():
    good = score_relations(
        [GOLD_RELATION],
        [PREDICTED_RELATION],
        gold_entities=GOLD_ENTITIES,
        predicted_entities=GOLD_ENTITIES,
        evidence_contexts=GOOD_CONTEXT,
    )
    outside_clause = {
        ("supports", "e1", "e2"): EvidenceContext(((35, 43),), (0, 50), (0, 30))
    }
    repeated = {
        ("supports", "e1", "e2"): EvidenceContext(
            ((10, 18), (20, 28)), (0, 40), (0, 30)
        )
    }
    unsupported = score_relations(
        [GOLD_RELATION],
        [PREDICTED_RELATION],
        gold_entities=GOLD_ENTITIES,
        predicted_entities=GOLD_ENTITIES,
        evidence_contexts=outside_clause,
    )
    ambiguous = score_relations(
        [GOLD_RELATION],
        [PREDICTED_RELATION],
        gold_entities=GOLD_ENTITIES,
        predicted_entities=GOLD_ENTITIES,
        evidence_contexts=repeated,
    )
    missing_trigger = score_relations(
        [GOLD_RELATION],
        [RelationCandidate("supports", "e1", "e2", 1, 0, 30, None)],
        gold_entities=GOLD_ENTITIES,
        predicted_entities=GOLD_ENTITIES,
        evidence_contexts=GOOD_CONTEXT,
    )
    assert good["evidence"]["counts"]["exact"] == 1
    assert unsupported["evidence"]["counts"]["unsupported"] == 1
    assert ambiguous["evidence"]["counts"]["unsupported"] == 1
    assert missing_trigger["evidence"]["counts"]["missing"] == 1
