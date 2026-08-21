from sprint12_f12_two_step_contracts_v5 import (
    EvidenceContext,
    RelationCandidate,
    materialize_evidence_context,
    score_relations,
)

SOURCE = "A" * 10 + "supports" + "B" * 12 + "supports" + "C" * 10 + "D" * 32
GOLD_ENTITIES = {
    "g1": (0, 5, "Task"),
    "g2": (20, 30, "Requirement"),
    "g3": (40, 48, "Decision"),
}
GOLD_RELATIONS = [
    {
        "predicate": "supports",
        "sourceEntityId": "g1",
        "targetEntityId": "g2",
        "startOffset": 0,
        "endOffset": 30,
        "triggerDigest": "sha256:66312e5e57ebd0b4fff4ef544c5a4abd86f89a0e2f003d9209dad1a641694bca",
    },
    {
        "predicate": "supports",
        "sourceEntityId": "g1",
        "targetEntityId": "g3",
        "startOffset": 0,
        "endOffset": 48,
        "triggerDigest": "sha256:66312e5e57ebd0b4fff4ef544c5a4abd86f89a0e2f003d9209dad1a641694bca",
    },
]
PREDICTED = [
    RelationCandidate("supports", "c1", "c2", 1, 0, 30, "supports"),
    RelationCandidate("supports", "c1", "c3", 1, 0, 48, "supports"),
]
PREDICTED_ENTITIES = {
    "c1": (0, 5, "Task"),
    "c2": (20, 30, "Requirement"),
    "c3": (40, 48, "Decision"),
}
CONTEXTS = {
    ("supports", "c1", "c2"): materialize_evidence_context(
        SOURCE, [(10, 18)], sentence=(0, 60), clause=(0, 48)
    ),
    ("supports", "c1", "c3"): materialize_evidence_context(
        SOURCE, [(30, 38)], sentence=(0, 60), clause=(0, 48)
    ),
}


def test_shared_source_endpoint_reuse_resolves_every_relation_slot():
    score = score_relations(
        GOLD_RELATIONS,
        PREDICTED,
        gold_entities=GOLD_ENTITIES,
        predicted_entities=PREDICTED_ENTITIES,
        evidence_contexts=CONTEXTS,
    )
    assert score["semantic"]["truePositive"] == 2
    assert score["endpointResolution"]["resolved"] == 4
    assert score["endpointResolution"]["wrong"] == 0
    assert score["evidence"]["counts"]["exact"] == 2


def test_relation_cycle_reuses_the_same_entity_mapping():
    gold = [{**GOLD_RELATIONS[0], "sourceEntityId": "g2", "targetEntityId": "g1"}]
    predicted = [RelationCandidate("supports", "c2", "c1", 1, 0, 30, "supports")]
    score = score_relations(
        gold,
        predicted,
        gold_entities=GOLD_ENTITIES,
        predicted_entities=PREDICTED_ENTITIES,
        evidence_contexts={},
    )
    assert score["semantic"]["truePositive"] == 1
    assert score["endpointResolution"]["resolved"] == 2


def test_source_slice_is_the_custody_root_for_occurrence_digest():
    tampered_source = EvidenceContext(
        CONTEXTS[("supports", "c1", "c2")].source_length,
        CONTEXTS[("supports", "c1", "c2")].source_digest,
        "X" * 80,
        CONTEXTS[("supports", "c1", "c2")].trigger_occurrences,
        (0, 60),
        (0, 48),
    )
    bad_metadata = EvidenceContext(
        CONTEXTS[("supports", "c1", "c2")].source_length,
        CONTEXTS[("supports", "c1", "c2")].source_digest,
        SOURCE,
        (
            type(CONTEXTS[("supports", "c1", "c2")].trigger_occurrences[0])(
                10, 18, "sha256:wrong"
            ),
        ),
        (0, 60),
        (0, 48),
    )
    score_source = score_relations(
        [GOLD_RELATIONS[0]],
        [PREDICTED[0]],
        gold_entities=GOLD_ENTITIES,
        predicted_entities=PREDICTED_ENTITIES,
        evidence_contexts={("supports", "c1", "c2"): tampered_source},
    )
    score_metadata = score_relations(
        [GOLD_RELATIONS[0]],
        [PREDICTED[0]],
        gold_entities=GOLD_ENTITIES,
        predicted_entities=PREDICTED_ENTITIES,
        evidence_contexts={("supports", "c1", "c2"): bad_metadata},
    )
    assert score_source["evidence"]["counts"]["unsupported"] == 1
    assert score_metadata["evidence"]["counts"]["unsupported"] == 1
