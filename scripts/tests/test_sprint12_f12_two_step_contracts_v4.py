import hashlib

from sprint12_f12_two_step_contracts_v4 import (
    EvidenceContext,
    RelationCandidate,
    TriggerOccurrence,
    score_relations,
)

GOLD_ENTITIES = {"g1": (0, 5, "Task"), "g2": (20, 30, "Requirement")}
GOLD_RELATION = {
    "predicate": "supports",
    "sourceEntityId": "g1",
    "targetEntityId": "g2",
    "startOffset": 0,
    "endOffset": 30,
    "triggerDigest": "sha256:66312e5e57ebd0b4fff4ef544c5a4abd86f89a0e2f003d9209dad1a641694bca",
}
RENAMED_RELATION = RelationCandidate("supports", "c17", "c42", 1, 0, 30, "supports")
GOOD_CONTEXT = {
    ("supports", "c17", "c42"): EvidenceContext(
        80,
        (
            TriggerOccurrence(
                10,
                18,
                "sha256:66312e5e57ebd0b4fff4ef544c5a4abd86f89a0e2f003d9209dad1a641694bca",
            ),
        ),
        (0, 40),
        (0, 30),
    )
}


def test_endpoint_identity_resolves_by_typed_span_and_is_one_to_one():
    renamed = score_relations(
        [GOLD_RELATION],
        [RENAMED_RELATION],
        gold_entities=GOLD_ENTITIES,
        predicted_entities={"c17": (0, 5, "Task"), "c42": (20, 30, "Requirement")},
        evidence_contexts=GOOD_CONTEXT,
    )
    duplicate = score_relations(
        [GOLD_RELATION],
        [RENAMED_RELATION],
        gold_entities=GOLD_ENTITIES,
        predicted_entities={
            "c17": (0, 5, "Task"),
            "c18": (0, 5, "Task"),
            "c42": (20, 30, "Requirement"),
        },
        evidence_contexts=GOOD_CONTEXT,
    )
    absent = score_relations(
        [GOLD_RELATION],
        [RENAMED_RELATION],
        gold_entities=GOLD_ENTITIES,
        predicted_entities={"c17": (0, 5, "Task")},
        evidence_contexts=GOOD_CONTEXT,
    )
    drift = score_relations(
        [GOLD_RELATION],
        [RENAMED_RELATION],
        gold_entities=GOLD_ENTITIES,
        predicted_entities={"c17": (0, 5, "Task"), "c42": (20, 29, "Requirement")},
        evidence_contexts=GOOD_CONTEXT,
    )
    wrong_type = score_relations(
        [GOLD_RELATION],
        [RENAMED_RELATION],
        gold_entities=GOLD_ENTITIES,
        predicted_entities={"c17": (0, 5, "Task"), "c42": (20, 30, "Decision")},
        evidence_contexts=GOOD_CONTEXT,
    )
    assert (
        renamed["semantic"]["truePositive"] == 1
        and renamed["semantic"]["missingEndpointRate"] == 0.0
    )
    assert duplicate["endpointResolution"]["wrong"] == 1
    assert absent["semantic"]["missingEndpointRate"] == 0.5
    assert drift["endpointResolution"]["wrong"] == 1
    assert wrong_type["endpointResolution"]["wrong"] == 1


def test_occurrence_width_and_digest_are_bound_to_trigger_quote():
    good = score_relations(
        [GOLD_RELATION],
        [RENAMED_RELATION],
        gold_entities=GOLD_ENTITIES,
        predicted_entities={"c17": (0, 5, "Task"), "c42": (20, 30, "Requirement")},
        evidence_contexts=GOOD_CONTEXT,
    )
    width_mismatch = {
        ("supports", "c17", "c42"): EvidenceContext(
            80,
            (
                TriggerOccurrence(
                    10,
                    11,
                    "sha256:66312e5e57ebd0b4fff4ef544c5a4abd86f89a0e2f003d9209dad1a641694bca",
                ),
            ),
            (0, 40),
            (0, 30),
        )
    }
    content_mismatch = {
        ("supports", "c17", "c42"): EvidenceContext(
            80, (TriggerOccurrence(10, 18, "sha256:wrong"),), (0, 40), (0, 30)
        )
    }
    bad_width = score_relations(
        [GOLD_RELATION],
        [RENAMED_RELATION],
        gold_entities=GOLD_ENTITIES,
        predicted_entities={"c17": (0, 5, "Task"), "c42": (20, 30, "Requirement")},
        evidence_contexts=width_mismatch,
    )
    bad_content = score_relations(
        [GOLD_RELATION],
        [RENAMED_RELATION],
        gold_entities=GOLD_ENTITIES,
        predicted_entities={"c17": (0, 5, "Task"), "c42": (20, 30, "Requirement")},
        evidence_contexts=content_mismatch,
    )
    assert good["evidence"]["counts"]["exact"] == 1
    assert bad_width["evidence"]["counts"]["unsupported"] == 1
    assert bad_content["evidence"]["counts"]["unsupported"] == 1


def test_unicode_code_point_policy_accepts_emoji_width_one():
    quote = "🙂"
    digest = "sha256:" + hashlib.sha256(quote.encode()).hexdigest()
    relation = RelationCandidate("supports", "c17", "c42", 1, 0, 30, quote)
    gold = [{**GOLD_RELATION, "triggerDigest": digest}]
    context = {
        ("supports", "c17", "c42"): EvidenceContext(
            80, (TriggerOccurrence(10, 11, digest),), (0, 40), (0, 30)
        )
    }
    score = score_relations(
        gold,
        [relation],
        gold_entities=GOLD_ENTITIES,
        predicted_entities={"c17": (0, 5, "Task"), "c42": (20, 30, "Requirement")},
        evidence_contexts=context,
    )
    assert score["evidence"]["counts"]["exact"] == 1
